"""
BankNifty Real Data Test - NO Volume Exits
"""
import sqlite3
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trading_system import LorentzianTradingSystem, TradingSettings
from backtest_novolume import Backtester

DB_PATH = "/Users/rohan/Downloads/Virdhi_Captial_trading_system/banknifty_trading_system/scripts/data/banknifty_data.db"

print("="*70)
print("BANKNIFTY BACKTEST - NO VOLUME EXITS")
print("="*70)

# Load data
conn = sqlite3.connect(DB_PATH)
df = pd.read_sql_query("""
    SELECT timestamp, open, high, low, close, volume
    FROM ohlcv WHERE timeframe = '15min'
    ORDER BY timestamp DESC LIMIT 5000
""", conn)
conn.close()

df = df.iloc[::-1].reset_index(drop=True)
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
df['timestamp'] = df['timestamp'].dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')
print(f"\n✅ {len(df)} bars: {df['timestamp'].min()} to {df['timestamp'].max()}\n")

# Backtest settings
settings = TradingSettings(
    neighbors_count=5,
    max_bars_back=2000,
    feature_count=5,
    use_kernel_filter=True,
    kernel_lookback=8,
    kernel_relative_weight=8.0,
    use_volatility_filter=True,
    use_regime_filter=True,
    regime_threshold=-0.1,
    enable_reentry=True,
    reentry_window_start=3,
    reentry_window_end=50
)

system = LorentzianTradingSystem(settings)
backtester = Backtester(system)
results = backtester.run_backtest(df['high'].values, df['low'].values, df['close'].values)

# Print results
backtester.print_results(results)

# Save trades
if not results['trades'].empty:
    trades = results['trades'].copy()
    trades['entry_time'] = trades['entry_bar'].apply(lambda x: df.loc[x, 'timestamp'])
    trades['exit_time'] = trades['exit_bar'].apply(lambda x: df.loc[x, 'timestamp'])
    trades.to_csv('banknifty_trades_no_volume.csv', index=False)
    print(f"\n💾 Saved: banknifty_trades_no_volume.csv")

# Extract signals
signals = []
r = results['results']
for i in range(len(df)):
    if r['start_long'][i]:
        signals.append((i, df.loc[i, 'timestamp'], 'LONG ENTRY', df.loc[i, 'close']))
    if r['start_short'][i]:
        signals.append((i, df.loc[i, 'timestamp'], 'SHORT ENTRY', df.loc[i, 'close']))
    if r['end_long'][i]:
        signals.append((i, df.loc[i, 'timestamp'], 'LONG EXIT', df.loc[i, 'close']))
    if r['end_short'][i]:
        signals.append((i, df.loc[i, 'timestamp'], 'SHORT EXIT', df.loc[i, 'close']))

if signals:
    pd.DataFrame(signals, columns=['candle', 'timestamp', 'signal', 'price']).to_csv('signals_no_volume.csv', index=False)
    print(f"💾 Saved: signals_no_volume.csv")

print(f"\n{'='*70}")
print("COMPARISON SUMMARY")
print(f"{'='*70}")
m = results['metrics']
print(f"\nTotal Return:     {m['total_return']:.2f}%")
print(f"Max Drawdown:     {m['max_drawdown']:.2f}%")
print(f"Win Rate:         {m['win_rate']:.2f}%")
print(f"Profit Factor:    {m['profit_factor']:.2f}")
print(f"Sharpe Ratio:     {m['sharpe_ratio']:.2f}")
print(f"\nAvg MFE:          {m['avg_mfe']:.2f}%")
print(f"Avg MAE:          {m['avg_mae']:.2f}%")
print(f"Winner MAE:       {m['avg_win_mae']:.2f}%")
print(f"Loser MAE:        {m['avg_loss_mae']:.2f}%")    