import os
import asyncio
from flask import Flask, jsonify, render_template, request, Response
from flask_cors import CORS
import logging
import sqlite3
from datetime import datetime
from .auth import require_auth, authenticate

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
        
        # 装饰器工厂
        def auth_decorator(view_func):
            return require_auth(self.auth_user, self.auth_pass)(view_func)

        @self.app.route('/')
        @auth_decorator
        def index():
            """首页"""
            return render_template('index.html')

        @self.app.route('/api/status')
        @auth_decorator
        def get_status():
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

        @self.app.route('/api/strategy')
        def get_strategy_status():
            """获取策略状态"""
            bot = self.trading_bot
            status = bot.strategy_engine.get_status()
            return jsonify(status)

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

        @self.app.route('/health')
        def health():
            """健康检查"""
            return jsonify({'status': 'ok'})

    def run(self):
        """启动看板服务"""
        logger.info(f"启动 Dashboard: http://{self.host}:{self.port}")
        self.app.run(host=self.host, port=self.port, debug=False, threaded=True)

