"""
CCXT 历史数据回测引擎
"""
import logging
import pickle
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import ccxt

logger = logging.getLogger(__name__)


class CCXTBacktestEngine:
    """
    使用 CCXT 获取真实历史数据的回测引擎
    
    特点：
    - 支持多个交易所（binance, okx）
    - 自动缓存已下载的数据
    - 处理 CCXT 的 limit 限制和分页
    - 返回标准 OHLCV DataFrame
    """

    def __init__(self, cache_dir: str = "data/historical"):
        """
        初始化回测引擎
        
        Args:
            cache_dir: 缓存目录路径，相对于工作目录
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 支持的交易所
        self.supported_exchanges = ['binance', 'okx']
        
        # CCXT exchange 实例缓存
        self._exchange_instances: Dict[str, Any] = {}

    def _get_cache_filename(self, exchange: str, symbol: str, start_time: int, end_time: int) -> Path:
        """
        生成缓存文件名
        
        文件名包含 exchange, symbol, start, end 的哈希，确保唯一性
        """
        key = f"{exchange}_{symbol}_{start_time}_{end_time}"
        # 创建安全的文件名
        safe_key = hashlib.md5(key.encode()).hexdigest()[:16]
        return self.cache_dir / f"{safe_key}.pkl"

    def _get_exchange(self, exchange_id: str) -> Any:
        """
        获取或创建 CCXT exchange 实例
        
        Args:
            exchange_id: 交易所ID（如 'binance', 'okx'）
            
        Returns:
            ccxt exchange 实例
        """
        if exchange_id not in self._exchange_instances:
            if exchange_id not in self.supported_exchanges:
                raise ValueError(f"不支持的交易所: {exchange_id}。支持的交易所: {self.supported_exchanges}")
            
            exchange_class = getattr(ccxt, exchange_id)
            self._exchange_instances[exchange_id] = exchange_class({
                'enableRateLimit': True,
                'timeout': 30000,
            })
            logger.info(f"创建 {exchange_id} exchange 实例")
        
        return self._exchange_instances[exchange_id]

    def fetch_historical_data(
        self, 
        exchange: str, 
        symbol: str, 
        start_time: datetime, 
        end_time: datetime,
        timeframe: str = '1m',
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        获取历史 K 线数据（优先使用缓存）
        
        Args:
            exchange: 交易所名称（'binance', 'okx'）
            symbol: 交易对（如 'BTC/USDT'）
            start_time: 开始时间（datetime 对象）
            end_time: 结束时间（datetime 对象）
            timeframe: 时间周期（默认 '1m'）
            use_cache: 是否使用缓存
            
        Returns:
            pandas DataFrame，列包括：timestamp, open, high, low, close, volume
            索引为 timestamp
        """
        # 转换时间戳为毫秒
        since = int(start_time.timestamp() * 1000)
        until = int(end_time.timestamp() * 1000)
        
        # 检查缓存
        cache_file = self._get_cache_filename(exchange, symbol, since, until)
        if use_cache and cache_file.exists():
            logger.info(f"使用缓存数据: {cache_file}")
            with open(cache_file, 'rb') as f:
                df = pickle.load(f)
            # 验证数据完整性
            if isinstance(df, pd.DataFrame) and not df.empty:
                return df
            logger.warning(f"缓存文件损坏或不完整，将重新下载")
        
        # 从交易所下载
        logger.info(f"从 {exchange} 下载 {symbol} 历史数据: {start_time} -> {end_time}")
        df = self._download_historical_data(exchange, symbol, since, until, timeframe)
        
        # 保存到缓存
        if not df.empty:
            with open(cache_file, 'wb') as f:
                pickle.dump(df, f)
            logger.info(f"数据已缓存到: {cache_file}")
        
        return df

    def _download_historical_data(
        self, 
        exchange: str, 
        symbol: str, 
        since: int, 
        until: int, 
        timeframe: str = '1m'
    ) -> pd.DataFrame:
        """
        从交易所下载历史数据，处理分页
        
        CCXT 限制每次最多返回 1000 条数据，需要循环获取
        """
        ex = self._get_exchange(exchange)
        
        # 确保市场已加载
        try:
            ex.load_markets()
        except Exception as e:
            logger.warning(f"加载市场信息失败（可能已加载）: {e}")
        
        all_ohlcv = []
        current_since = since
        
        # 解析时间周期，计算毫秒间隔
        timeframe_ms = self._parse_timeframe_to_ms(timeframe)
        
        while current_since < until:
            try:
                #  Fetch OHLCV 数据
                # limit 默认为 1000，但可以设置，有些交易所支持更大
                ohlcv = ex.fetch_ohlcv(symbol, timeframe, since=current_since, limit=1000)
                
                if not ohlcv:
                    logger.warning(f"未获取到数据: {symbol} from {datetime.fromtimestamp(current_since/1000)}")
                    break
                
                all_ohlcv.extend(ohlcv)
                logger.debug(f"获取到 {len(ohlcv)} 条数据，总计 {len(all_ohlcv)} 条")
                
                # 更新 since 为最后一根的时间戳 + 时间周期（避免重复）
                last_timestamp = ohlcv[-1][0]
                current_since = last_timestamp + timeframe_ms
                
                # 如果获取的数据不足 limit 条，说明已经到最新数据
                if len(ohlcv) < 1000:
                    break
                    
            except Exception as e:
                logger.error(f"下载历史数据失败: {e}")
                # 重试逻辑？暂时直接退出
                break
        
        # 转换为 DataFrame
        if not all_ohlcv:
            logger.warning("未获取到任何历史数据")
            return pd.DataFrame()
        
        df = pd.DataFrame(
            all_ohlcv, 
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        
        # 时间戳转换为 datetime（保留毫秒精度）
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # 按时间排序
        df.sort_values('timestamp', inplace=True)
        
        # 过滤时间范围（确保在 until 之前）
        df = df[df['timestamp'] < pd.to_datetime(until, unit='ms')]
        
        # 去重（基于 timestamp）
        df.drop_duplicates(subset=['timestamp'], keep='first', inplace=True)
        
        # 重置索引，确保连续
        df.reset_index(drop=True, inplace=True)
        
        logger.info(f"下载完成，共 {len(df)} 条数据")
        return df

    def _parse_timeframe_to_ms(self, timeframe: str) -> int:
        """
        将 CCXT 时间周期字符串转换为毫秒数
        
        例如: '1m' -> 60000, '1h' -> 3600000, '1d' -> 86400000
        """
        if timeframe.endswith('m'):
            return int(timeframe[:-1]) * 60 * 1000
        elif timeframe.endswith('h'):
            return int(timeframe[:-1]) * 60 * 60 * 1000
        elif timeframe.endswith('d'):
            return int(timeframe[:-1]) * 24 * 60 * 60 * 1000
        else:
            # 默认 1 分钟
            return 60 * 1000

    def clear_cache(self, older_than_days: Optional[int] = None):
        """
        清理缓存文件
        
        Args:
            older_than_days: 只删除超过指定天数的缓存，None 表示全部删除
        """
        if not self.cache_dir.exists():
            return
        
        cache_files = list(self.cache_dir.glob("*.pkl"))
        deleted_count = 0
        
        for cache_file in cache_files:
            if older_than_days is not None:
                file_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
                if file_age.days <= older_than_days:
                    continue
            
            cache_file.unlink(missing_ok=True)
            deleted_count += 1
        
        logger.info(f"清理了 {deleted_count} 个缓存文件")
        
    def close(self):
        """关闭所有 exchange 连接"""
        for exchange_id, exchange in self._exchange_instances.items():
            try:
                exchange.close()
                logger.info(f"关闭 {exchange_id} 连接")
            except Exception as e:
                logger.warning(f"关闭 {exchange_id} 时出错: {e}")
        self._exchange_instances.clear()


# 演示用法
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="CCXT 历史数据获取工具")
    parser.add_argument('--exchange', type=str, default='binance', help='交易所名称')
    parser.add_argument('--symbol', type=str, default='BTC/USDT', help='交易对')
    parser.add_argument('--start', type=str, default='2024-01-01', help='开始时间 (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default='2024-12-31', help='结束时间 (YYYY-MM-DD)')
    parser.add_argument('--timeframe', type=str, default='1h', help='时间周期 (如 1m, 5m, 1h, 1d)')
    parser.add_argument('--output', type=str, help='输出 CSV 文件路径')
    parser.add_argument('--no-cache', action='store_true', help='不使用缓存')
    
    args = parser.parse_args()
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建引擎
    engine = CCXTBacktestEngine()
    
    try:
        # 解析时间
        start_dt = datetime.strptime(args.start, '%Y-%m-%d')
        end_dt = datetime.strptime(args.end, '%Y-%m-%d')
        
        # 获取数据
        df = engine.fetch_historical_data(
            exchange=args.exchange,
            symbol=args.symbol,
            start_time=start_dt,
            end_time=end_dt,
            timeframe=args.timeframe,
            use_cache=not args.no_cache
        )
        
        if df.empty:
            print("未获取到数据")
        else:
            print(f"获取到 {len(df)} 条数据")
            print(df.head())
            print(df.tail())
            
            # 保存为 CSV（如果指定了输出路径）
            if args.output:
                df.to_csv(args.output, index=False)
                print(f"数据已保存到: {args.output}")
                
    finally:
        engine.close()
