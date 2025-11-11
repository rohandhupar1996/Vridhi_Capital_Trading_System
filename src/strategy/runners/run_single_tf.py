"""
Simple Single Timeframe Backtest Runner
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.backtest_engine import MasterBacktester, BacktestConfig

config = BacktestConfig(
    db_path="/Users/rohan/Downloads/Virdhi_Captial_trading_system/banknifty_trading_system/scripts/data/banknifty_data.db",
    default_exit_bars=4,
    track_drawdown=True
)

if __name__ == "__main__":
    backtester = MasterBacktester(config)
    results = backtester.run()