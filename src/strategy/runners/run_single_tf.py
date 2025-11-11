"""
FIXED Single Timeframe Backtest Runner
start_bar=96 to match TradingView's May 22, 2025 start
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.backtest_engine import MasterBacktester, BacktestConfig

config = BacktestConfig(
    db_path="/Users/rohan/Downloads/Virdhi_Captial_trading_system/banknifty_trading_system/scripts/data/banknifty_data.db",
    default_exit_bars=4,
    track_drawdown=True,
    start_bar=200  # ✅ FIXED: Match TradingView's May 22 start (bar 96)
)

if __name__ == "__main__":
    backtester = MasterBacktester(config)
    results = backtester.run()
    
    if results:
        total_trades = results['metrics']['total_trades']
       