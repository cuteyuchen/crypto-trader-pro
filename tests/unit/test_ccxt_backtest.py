"""
CCXTBacktestEngine 单元测试（无需真实交易所连接）
"""
import os
import sys
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import pytest

# 添加项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 在导入 ccxt_backtest 之前模拟 ccxt 模块
sys.modules['ccxt'] = MagicMock()

from src.backtest.ccxt_backtest import CCXTBacktestEngine


class TestCCXTBacktestEngine:
    """测试 CCXT 回测引擎"""

    def setup_method(self):
        """每个测试前的设置"""
        import tempfile
        self.temp_cache_dir = Path(tempfile.mkdtemp(prefix="ccxt_test_"))
        self.engine = CCXTBacktestEngine(cache_dir=str(self.temp_cache_dir))

    def teardown_method(self):
        """每个测试后的清理"""
        self.engine.close()
        # 清理缓存文件
        import shutil
        try:
            shutil.rmtree(self.temp_cache_dir)
        except:
            pass

    def test_cache_filename_generation(self):
        """测试缓存文件名生成"""
        filename = self.engine._get_cache_filename('binance', 'BTC/USDT', 1704067200000, 1706745600000)
        # 文件名应该是 hash 值
        assert filename.name.endswith('.pkl')
        assert len(filename.name) == 20  # 16 hex chars + .pkl

    def test_fetch_historical_data_with_mock(self):
        """使用模拟数据测试 fetch_historical_data"""
        # 创建模拟的 OHLCV 数据
        mock_ohlcv = [
            [1704067200000, 50000.0, 50100.0, 49900.0, 50050.0, 100.0],
            [1704070800000, 50050.0, 50200.0, 50000.0, 50150.0, 150.0],
            [1704074400000, 50150.0, 50300.0, 50100.0, 50200.0, 120.0],
        ]

        # 模拟 ccxt 交易所
        with patch('ccxt.binance') as MockExchange:
            mock_exchange = Mock()
            mock_exchange.fetch_ohlcv.return_value = mock_ohlcv
            mock_exchange.load_markets = Mock()
            MockExchange.return_value = mock_exchange

            # 第一次调用应该下载数据
            start = datetime(2024, 1, 1)
            end = datetime(2024, 1, 2)
            df = self.engine.fetch_historical_data(
                exchange='binance',
                symbol='BTC/USDT',
                start_time=start,
                end_time=end,
                timeframe='1h',
                use_cache=False
            )

            assert not df.empty
            assert len(df) == 3
            assert list(df.columns) == ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            # 验证数据类型
            assert df['timestamp'].dtype == 'datetime64[ns]'
            assert df['close'].dtype == 'float64'

    def test_cache_and_reuse(self):
        """测试缓存保存和复用"""
        # 创建模拟数据
        mock_ohlcv = [
            [1704067200000, 50000.0, 50100.0, 49900.0, 50050.0, 100.0],
        ]

        with patch('ccxt.binance') as MockExchange:
            mock_exchange = Mock()
            mock_exchange.fetch_ohlcv.return_value = mock_ohlcv
            mock_exchange.load_markets = Mock()
            MockExchange.return_value = mock_exchange

            start = datetime(2024, 1, 1)
            end = datetime(2024, 1, 2)

            # 第一次下载
            df1 = self.engine.fetch_historical_data(
                exchange='binance',
                symbol='BTC/USDT',
                start_time=start,
                end_time=end,
                use_cache=True
            )
            assert len(df1) == 1

            # 验证缓存文件存在
            cache_files = list(self.temp_cache_dir.glob("*.pkl"))
            assert len(cache_files) == 1

            # 重置 mock，第二次应该使用缓存而不是调用 fetch_ohlcv
            mock_exchange.fetch_ohlcv.reset_mock()
            df2 = self.engine.fetch_historical_data(
                exchange='binance',
                symbol='BTC/USDT',
                start_time=start,
                end_time=end,
                use_cache=True
            )
            assert len(df2) == 1
            assert mock_exchange.fetch_ohlcv.call_count == 0  # 没有调用 API

    def test_pagination(self):
        """测试分页逻辑（超过1000条数据）"""
        # 创建超过 limit 的数据模拟
        mock_ohlcv_page1 = [[1704067200000 + i*3600000, 50000.0 + i, 50100.0 + i, 49900.0 + i, 50050.0 + i, 100.0] for i in range(1000)]
        mock_ohlcv_page2 = [[1704074400000 + i*3600000, 51000.0 + i, 51100.0 + i, 50900.0 + i, 51050.0 + i, 100.0] for i in range(100)]

        with patch('ccxt.binance') as MockExchange:
            mock_exchange = Mock()
            # 第一次调用返回1000条，第二次返回100条，第三次返回空（结束）
            mock_exchange.fetch_ohlcv.side_effect = [mock_ohlcv_page1, mock_ohlcv_page2, []]
            mock_exchange.load_markets = Mock()
            MockExchange.return_value = mock_exchange

            start = datetime(2024, 1, 1)
            end = datetime(2024, 1, 20)  # 足够长的时间范围

            df = self.engine.fetch_historical_data(
                exchange='binance',
                symbol='BTC/USDT',
                start_time=start,
                end_time=end,
                timeframe='1h',
                use_cache=False
            )

            assert len(df) == 1100  # 两页合计
            assert mock_exchange.fetch_ohlcv.call_count == 2  # 两次调用

    def test_data_sorting_and_deduplication(self):
        """测试数据排序和去重"""
        # 模拟乱序数据（模拟交易所返回可能不严格按时间排序）
        mock_ohlcv = [
            [1704070800000, 50050.0, 50200.0, 50000.0, 50150.0, 150.0],  # 第2根
            [1704067200000, 50000.0, 50100.0, 49900.0, 50050.0, 100.0],  # 第1根
            [1704067200000, 50000.0, 50100.0, 49900.0, 50050.0, 100.0],  # 重复的第1根
        ]

        with patch('ccxt.binance') as MockExchange:
            mock_exchange = Mock()
            mock_exchange.fetch_ohlcv.return_value = mock_ohlcv
            mock_exchange.load_markets = Mock()
            MockExchange.return_value = mock_exchange

            start = datetime(2024, 1, 1)
            end = datetime(2024, 1, 2)

            df = self.engine.fetch_historical_data(
                exchange='binance',
                symbol='BTC/USDT',
                start_time=start,
                end_time=end,
                use_cache=False
            )

            # 应该只有2条去重后的数据，且按时间排序
            assert len(df) == 2
            assert df.iloc[0]['timestamp'] < df.iloc[1]['timestamp']

    def test_unsupported_exchange(self):
        """测试不支持的交易所"""
        with pytest.raises(ValueError, match="不支持的交易所"):
            self.engine.fetch_historical_data(
                exchange='huobi',  # 不在支持列表
                symbol='BTC/USDT',
                start_time=datetime.now(),
                end_time=datetime.now()
            )

    def test_supported_exchanges(self):
        """测试支持的交易所列表"""
        assert 'binance' in self.engine.supported_exchanges
        assert 'okx' in self.engine.supported_exchanges


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
