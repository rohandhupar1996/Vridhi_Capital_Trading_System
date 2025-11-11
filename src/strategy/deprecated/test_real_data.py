"""BankNifty 15min - TradingView Signal Comparison"""
import sqlite3
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trading_system import LorentzianTradingSystem, TradingSettings
from backtest import Backtester

DB_PATH = "/Users/rohan/Downloads/Virdhi_Captial_trading_system/banknifty_trading_system/scripts/data/banknifty_data.db"

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
# Convert to IST (UTC+5:30)
df['timestamp'] = df['timestamp'].dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')
print(f"✅ {len(df)} bars: {df['timestamp'].min()} to {df['timestamp'].max()}\n")

# Backtest
settings = TradingSettings(
    neighbors_count=5, max_bars_back=2000, feature_count=5,
    use_kernel_filter=True, kernel_lookback=8, kernel_relative_weight=8.0,
    use_volatility_filter=True, use_regime_filter=True, regime_threshold=-0.1,
    enable_reentry=True, reentry_window_start=3, reentry_window_end=50
)

system = LorentzianTradingSystem(settings)
backtester = Backtester(system)
results = backtester.run_backtest(df['high'].values, df['low'].values, df['close'].values)

# Extract signals with timestamps
signals = []
for i in range(len(df)):
    r = results['results']
    if r['start_long'][i]:
        signals.append((i, df.loc[i, 'timestamp'], 'LONG ENTRY', df.loc[i, 'close']))
    if r['start_short'][i]:
        signals.append((i, df.loc[i, 'timestamp'], 'SHORT ENTRY', df.loc[i, 'close']))
    if r['end_long'][i]:
        signals.append((i, df.loc[i, 'timestamp'], 'LONG EXIT', df.loc[i, 'close']))
    if r['end_short'][i]:
        signals.append((i, df.loc[i, 'timestamp'], 'SHORT EXIT', df.loc[i, 'close']))

print("="*90)
print("SIGNALS (for TradingView comparison)")
print("="*90 + "\n")

if signals:
    for candle, time, sig, price in signals:
        print(f"Candle #{candle:4d} | {time} | {sig:12s} @ {price:.2f}")
    
    pd.DataFrame(signals, columns=['candle', 'timestamp', 'signal', 'price']).to_csv('signals.csv', index=False)
    print(f"\n💾 signals.csv saved")
else:
    print("⚠️  No signals")

backtester.print_results(results)

if not results['trades'].empty:
    t = results['trades'].copy()
    t['entry_time'] = t['entry_bar'].apply(lambda x: df.loc[x, 'timestamp'])
    t['exit_time'] = t['exit_bar'].apply(lambda x: df.loc[x, 'timestamp'])
    t.to_csv('trades.csv', index=False)
    print(f"💾 trades.csv saved")