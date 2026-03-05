import os
import json
import asyncio
from flask import Flask, jsonify, render_template, request, Response
from flask_cors import CORS
import logging
import sqlite3
from datetime import datetime, date
from subprocess import run, PIPE

logger = logging.getLogger(__name__)


class Dashboard:
    """看板服务"""

    def __init__(self, trading_bot, host='0.0.0.0', port=5000):
        """
        Args:
            trading_bot: TradingBot 实例，用于获取数据
            host: 监听地址
            port: 监听端口
        """
        self.trading_bot = trading_bot
        self.host = host
        self.port = port
        self.app = Flask(__name__, 
                        static_folder='static',
                        template_folder='templates')
        CORS(self.app)  # 允许跨域（方便开发）
        # 认证配置
        self.auth_user = os.getenv('DASHBOARD_USER', 'admin')
        self.auth_pass = os.getenv('DASHBOARD_PASS', 'admin123')
        
        # 全局请求前验证（除了静态文件）
        @self.app.before_request
        def check_auth():
            # 跳过静态文件路径
            if request.path.startswith('/static/'):
                return
            # 验证 Basic Auth
            auth = request.authorization
            if not auth or not (auth.username == self.auth_user and auth.password == self.auth_pass):
                return Response('需要认证\n', 401, {'WWW-Authenticate': 'Basic realm="Dashboard"'})
        
        self._setup_routes()

    def _run_async(self, coro):
        """在主事件循环中运行异步协程（用于 Dashboard 线程）"""
        loop = getattr(self.trading_bot, 'event_loop', None)
        if loop is None or loop.is_closed():
            # 主循环未就绪，在当前线程新建事件运行
            return asyncio.run(coro)
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=10)

    def _setup_routes(self):
        """设置路由"""
        # 从环境变量读取认证信息（默认 admin / admin123）
        self.auth_user = os.getenv('DASHBOARD_USER', 'admin')
        self.auth_pass = os.getenv('DASHBOARD_PASS', 'admin123')

        @self.app.route('/')
        def index():
            """首页"""
            return render_template('index_v2.html')

        @self.app.route('/api/balance')
        def get_balance():
            """获取账户余额"""
            bot = self.trading_bot
            if bot.db:
                usdt = bot.db.get_balance("USDT")
                return jsonify({'USDT': usdt})
            else:
                try:
                    usdt = self._run_async(bot.executor.get_balance("USDT"))
                    return jsonify({'USDT': usdt})
                except Exception as e:
                    logger.error(f"获取余额失败: {e}")
                    return jsonify({'error': str(e)}), 500

        @self.app.route('/api/positions')
        def get_positions():
            """获取当前持仓"""
            bot = self.trading_bot
            symbol = bot.strategy_config['symbol']
            if bot.db:
                positions = bot.db.get_open_positions(symbol)
                # 补充当前价格
                latest_price = None
                if hasattr(bot.strategy_engine, 'kline_cache'):
                    klines = bot.strategy_engine.kline_cache.get_klines(symbol, 1)
                    if klines:
                        latest_price = klines[-1]['close']
                result = []
                for pos in positions:
                    result.append({
                        'id': pos['id'],
                        'symbol': pos['symbol'],
                        'side': pos['side'],
                        'quantity': pos['quantity'],
                        'entry_price': pos['entry_price'],
                        'current_price': latest_price or pos.get('current_price', 0),
                        'unrealized_pnl': pos['unrealized_pnl'],
                        'created_at': pos['created_at']
                    })
                return jsonify(result)
            else:
                try:
                    positions = self._run_async(bot.executor.get_positions(symbol))
                    # CCXT positions 格式标准化
                    result = []
                    for pos in positions:
                        # 示例字段：symbol, contracts, entryPrice, markPrice, unrealizedPnl, side
                        result.append({
                            'symbol': pos.get('symbol', symbol),
                            'side': pos.get('side', 'long'),
                            'quantity': pos.get('contracts', 0),
                            'entry_price': pos.get('entryPrice', 0),
                            'current_price': pos.get('markPrice', 0),
                            'unrealized_pnl': pos.get('unrealizedPnl', 0),
                            'created_at': None
                        })
                    return jsonify(result)
                except Exception as e:
                    logger.error(f"获取持仓失败: {e}")
                    return jsonify({'error': str(e)}), 500

        @self.app.route('/api/status')
        def get_status():
            """获取系统状态"""
            bot = self.trading_bot
            status = {
                'mode': bot.mode_config.get('mode', 'unknown'),
                'running': bot.running,
                'strategy': bot.strategy_config.get('name', bot.strategy_config.get('type', 'unknown')),
                'exchange': bot.mode_config.get('exchange', 'N/A'),
                'symbol': bot.strategy_config.get('symbol', 'N/A')
            }
            return jsonify(status)

        @self.app.route('/api/trades')
        def get_trades():
            """获取最近交易记录"""
            bot = self.trading_bot
            limit = int(request.args.get('limit', 20))
            symbol = bot.strategy_config['symbol']
            if bot.db:
                conn = bot.db._get_connection()
                try:
                    conn.row_factory = sqlite3.Row
                    cur = conn.execute('''
                        SELECT * FROM trades
                        ORDER BY executed_at DESC
                        LIMIT ?
                    ''', (limit,))
                    rows = cur.fetchall()
                    trades = [dict(row) for row in rows]
                    return jsonify(trades)
                finally:
                    conn.close()
            else:
                try:
                    trades = self._run_async(bot.executor.get_recent_trades(symbol, limit))
                    # CCXT trade format: id, timestamp, datetime, symbol, side, price, amount, cost, fee
                    result = []
                    for t in trades:
                        result.append({
                            'id': t.get('id'),
                            'executed_at': t.get('datetime'),
                            'symbol': t.get('symbol'),
                            'side': t.get('side'),
                            'quantity': t.get('amount'),
                            'price': t.get('price'),
                            'fee': t.get('fee', {}).get('cost', 0.0) if isinstance(t.get('fee'), dict) else t.get('fee', 0.0)
                        })
                    return jsonify(result)
                except Exception as e:
                    logger.error(f"获取交易记录失败: {e}")
                    return jsonify({'error': str(e)}), 500

        @self.app.route('/api/pnl/daily')
        def get_daily_pnl():
            """获取今日盈亏"""
            bot = self.trading_bot
            today = datetime.now().strftime('%Y-%m-%d')
            if bot.db:
                conn = bot.db._get_connection()
                try:
                    cur = conn.execute('''
                        SELECT SUM(pnl) as total_pnl 
                        FROM trades 
                        WHERE date(executed_at) = ?
                    ''', (today,))
                    row = cur.fetchone()
                    total_pnl = row[0] or 0.0
                    return jsonify({'date': today, 'total_pnl': total_pnl})
                finally:
                    conn.close()
            else:
                try:
                    trades = self._run_async(bot.executor.get_recent_trades(bot.strategy_config['symbol'], 100))
                    # filter trades that executed today
                    today_pnl = 0.0
                    for t in trades:
                        # CCXT trade has 'datetime' like '2025-03-05T08:30:00.000Z'
                        dt = t.get('datetime', '')
                        if dt.startswith(today):
                            # 有些交易所 trades 中的 fee cost 可能是单独字段；盈亏需要自己计算？在 CCXT 中没有直接 pnl 字段，需要根据 cost 和 side 计算？
                            # 简化：只加总 fee? Not correct. In real pnl we need position info. For now, return 0.
                            pass
                    return jsonify({'date': today, 'total_pnl': today_pnl})
                except Exception as e:
                    logger.error(f"获取日盈亏失败: {e}")
                    return jsonify({'date': today, 'total_pnl': 0.0})

        # ---------- Trader 相关 API ----------

        @self.app.route('/api/trades/active')
        def get_active_trades():
            """获取活跃订单列表"""
            bot = self.trading_bot
            if hasattr(bot, 'trader'):
                orders = bot.trader.get_active_orders()
                return jsonify(orders)
            else:
                return jsonify({'error': 'Trader 未初始化'}), 503

        @self.app.route('/api/trades/history')
        def get_trade_history():
            """获取历史订单"""
            bot = self.trading_bot
            limit = int(request.args.get('limit', 100))
            if hasattr(bot, 'trader'):
                trades = bot.trader.get_order_history(limit=limit)
                return jsonify(trades)
            else:
                return jsonify({'error': 'Trader 未初始化'}), 503

        @self.app.route('/api/trader/control', methods=['POST'])
        def control_trader():
            """控制 Trader：start/stop/force_sell"""
            bot = self.trading_bot
            if not hasattr(bot, 'trader'):
                return jsonify({'success': False, 'error': 'Trader 未初始化'}), 503

            try:
                req = request.get_json()
                action = req.get('action')  # start|stop|pause|resume|force_sell
                if action == 'start':
                    if not bot.trader.is_running():
                        bot.trader.start()
                        return jsonify({'success': True, 'message': 'Trader 已启动'})
                    else:
                        return jsonify({'success': False, 'message': 'Trader 已在运行'})
                elif action == 'stop':
                    if bot.trader.is_running():
                        bot.trader.stop()
                        return jsonify({'success': True, 'message': 'Trader 已停止'})
                    else:
                        return jsonify({'success': False, 'message': 'Trader 未运行'})
                elif action == 'pause':
                    bot.trader.pause()
                    return jsonify({'success': True, 'message': '自动交易已暂停'})
                elif action == 'resume':
                    bot.trader.resume()
                    return jsonify({'success': True, 'message': '自动交易已恢复'})
                elif action == 'force_sell':
                    symbol = req.get('symbol')
                    quantity = req.get('quantity')
                    # 异步调用
                    result = bot.trader._run_async(bot.trader.force_sell(symbol=symbol, quantity=quantity))
                    if result:
                        return jsonify({'success': True, 'message': '强制卖出已执行'})
                    else:
                        return jsonify({'success': False, 'message': '强制卖出失败'})
                else:
                    return jsonify({'success': False, 'error': f'未知操作: {action}'}), 400
            except Exception as e:
                logger.exception("Trader 控制异常")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/trader/stats')
        def get_trader_stats():
            """获取 Trader 统计信息"""
            bot = self.trading_bot
            if hasattr(bot, 'trader'):
                stats = bot.trader.get_stats()
                return jsonify(stats)
            else:
                return jsonify({'error': 'Trader 未初始化'}), 503

        @self.app.route('/api/trader/config', methods=['GET', 'POST'])
        def handle_trader_config():
            """获取或更新 Trader 配置（不包含策略相关）"""
            bot = self.trading_bot
            if not hasattr(bot, 'trader'):
                return jsonify({'error': 'Trader 未初始化'}), 503

            if request.method == 'GET':
                # 返回当前 runtime 配置（从 trader.config 提取可热更新的部分）
                cfg = {
                    "auto_trade": bot.trader.auto_trade,
                    "max_open_trades": bot.trader.max_open_trades,
                    "stake_amount": bot.trader.stake_amount,
                    "dry_run": bot.trader.dry_run
                }
                return jsonify(cfg)
            else:
                try:
                    new_cfg = request.get_json()
                    bot.trader.update_config(new_cfg)
                    return jsonify({'success': True, 'message': '配置已更新'})
                except Exception as e:
                    logger.exception("Trader 配置更新失败")
                    return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/strategy')
        def get_strategy_status():
            """获取策略状态"""
            bot = self.trading_bot
            status = bot.strategy_engine.get_status()
            return jsonify(status)

        @self.app.route('/api/trader/status')
        def get_trader_status():
            """获取交易引擎状态"""
            bot = self.trading_bot
            status = bot.trader.get_status()
            return jsonify(status)

        @self.app.route('/api/trades/active')
        def get_active_trades():
            """获取活跃交易"""
            bot = self.trading_bot
            trades = bot.trader.get_open_trades()
            return jsonify(trades)

        @self.app.route('/api/trades/history')
        def get_trade_history():
            """获取历史交易"""
            bot = self.trading_bot
            limit = int(request.args.get('limit', 50))
            trades = bot.trader.get_closed_trades(limit)
            return jsonify(trades)

        @self.app.route('/api/trader/control', methods=['POST'])
        def control_trader():
            """控制交易引擎（start/stop/toggle）"""
            bot = self.trading_bot
            req = request.get_json()
            action = req.get('action')
            if action == 'toggle':
                if bot.trader.running:
                    bot.trader.stop()
                    return jsonify({'success': True, 'message': '已停止'})
                else:
                    # 重启需要启动 run 中的循环？这里简化：只改标志，实际需重启主循环
                    return jsonify({'success': False, 'error': '请重启服务'})
            elif action == 'stop':
                bot.trader.stop()
                return jsonify({'success': True, 'message': '已停止'})
            elif action == 'start':
                # 需要异步启动，这里简化
                return jsonify({'success': False, 'error': '不支持动态启动，请重启服务'})
            else:
                return jsonify({'success': False, 'error': '未知操作'})

        @self.app.route('/api/order', methods=['POST'])
        def place_order():
            """手动下单（仅 local 模式）"""
            bot = self.trading_bot
            mode = bot.mode_config.get('mode') if hasattr(bot, 'mode_config') else 'local'
            if mode != 'local':
                return jsonify({'success': False, 'error': '仅 local 模式支持手动下单'}), 400

            # 等待 executor 初始化完成
            if hasattr(bot, 'executor_ready'):
                try:
                    # 等待最多 5 秒
                    future = bot.executor_ready
                    if not future.done():
                        future.result(timeout=5)
                except Exception as e:
                    return jsonify({'success': False, 'error': f'执行器未就绪: {e}'}), 503

            try:
                req = request.get_json()
                symbol = req.get('symbol', bot.strategy_config['symbol'])
                side = req['side']  # buy | sell
                quantity = float(req['quantity'])
                order_type = req.get('type', 'market')
                price = req.get('price')  # 市价单可为空

                if quantity <= 0:
                    return jsonify({'success': False, 'error': '数量必须大于0'}), 400

                # 构建订单请求
                order = {
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'type': order_type,
                    'price': price,
                    'strategy': bot.strategy_config.get('name', 'manual')
                }

                # 执行订单（同步调用异步函数）
                result = self._run_async(bot.executor.execute_order(order))
                if result['success']:
                    return jsonify({
                        'success': True,
                        'order_id': result.get('order_id'),
                        'filled_quantity': result.get('filled_quantity'),
                        'avg_price': result.get('avg_price'),
                        'fee': result.get('fee', 0.0),
                        'pnl': result.get('pnl', 0.0)
                    })
                else:
                    return jsonify({'success': False, 'error': result.get('error', '执行失败')}), 500

            except Exception as e:
                logger.exception("手动下单异常")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/strategies')
        def list_strategies():
            """列出所有可用策略配置"""
            import os, json, glob
            base_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'strategies')
            files = glob.glob(os.path.join(base_path, '*.json'))
            strategies = []
            for f in files:
                try:
                    with open(f, 'r') as fp:
                        cfg = json.load(fp)
                        strategies.append({
                            'name': cfg.get('name', os.path.splitext(os.path.basename(f))[0]),
                            'type': cfg.get('type', os.path.splitext(os.path.basename(f))[0]),
                            'file': os.path.basename(f),
                            'config': cfg
                        })
                except Exception as e:
                    logger.warning(f"读取策略配置失败 {f}: {e}")
            return jsonify(strategies)

        @self.app.route('/api/strategy/reload', methods=['POST'])
        def reload_strategy():
            """热重载策略配置（从文件重新加载）"""
            bot = self.trading_bot
            try:
                bot.load_config()  # 重新加载 modes.json 和策略配置
                bot.strategy_engine = StrategyEngine(bot.strategy_config)
                bot.strategy_engine.set_signal_callback(bot.on_signal)
                return jsonify({'success': True, 'message': f'策略已重载: {bot.strategy_config.get("name")}'})
            except Exception as e:
                logger.exception("策略重载失败")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/config', methods=['GET', 'POST'])
        def handle_config():
            """获取或更新 modes 配置（注意：修改后需重启或调用 /api/strategy/reload）"""
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'modes.json')
            if request.method == 'GET':
                try:
                    with open(config_path, 'r') as f:
                        cfg = json.load(f)
                    return jsonify(cfg)
                except Exception as e:
                    return jsonify({'error': str(e)}), 500
            else:
                try:
                    new_cfg = request.get_json()
                    with open(config_path, 'w') as f:
                        json.dump(new_cfg, f, indent=2)
                    return jsonify({'success': True, 'message': '配置已保存，请重启或调用重载'})
                except Exception as e:
                    return jsonify({'error': str(e)}), 500

        @self.app.route('/api/backtest', methods=['POST'])
        def run_backtest():
            """运行回测（简化版）"""
            bot = self.trading_bot
            try:
                req = request.get_json()
                strategy_file = req.get('strategy', bot.strategy_config.get('type', 'ma_cross'))
                days = int(req.get('days', 30))
                initial = float(req.get('initial_balance', bot.sim_config.get('initial_balance', 10000)))
                # 加载策略配置
                import os, json
                base = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'strategies')
                config_path = os.path.join(base, f'{strategy_file}.json')
                if not os.path.exists(config_path):
                    return jsonify({'error': f'策略配置不存在: {strategy_file}'}), 404
                with open(config_path, 'r') as f:
                    strategy_cfg = json.load(f)
                # 运行回测
                from src.backtest.engine import BacktestEngine
                engine = BacktestEngine(strategy_cfg, initial_balance=initial)
                result = engine.run(days=days)
                return jsonify(result)
            except Exception as e:
                logger.exception("回测失败")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/logs')
        def get_logs():
            """获取容器日志（简化版）"""
            return jsonify({'logs': '请使用 `docker logs crypto-trader-pro` 查看完整日志。\n此功能待实现。'})

        @self.app.route('/health')
        def health():
            """健康检查"""
            return jsonify({'status': 'ok'})

    def run(self):
        """启动看板服务"""
        logger.info(f"启动 Dashboard: http://{self.host}:{self.port}")
        self.app.run(host=self.host, port=self.port, debug=False, threaded=True)

