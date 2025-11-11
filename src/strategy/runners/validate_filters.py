"""
Debug kernel timing - Sept 29 analysis
"""
import numpy as np
import pandas as pd
import sqlite3
from pathlib import Path
import sys

sys.path.append('/Users/rohan/Downloads/Virdhi_Captial_trading_system/banknifty_trading_system/src/strategy')
from core.trading_system import LorentzianTradingSystem, TradingSettings
from core.ml_extension import filter_volatility, regime_filter

# Load data
db_path = Path.home() / '/Users/rohan/Downloads/Virdhi_Captial_trading_system/banknifty_trading_system/scripts/data/banknifty_data.db'
conn = sqlite3.connect(db_path)
df = pd.read_sql_query("SELECT * FROM ohlcv WHERE timeframe = '15min' ORDER BY timestamp DESC LIMIT 3000", conn)
conn.close()

df = df.iloc[::-1].reset_index(drop=True)
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s').dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')

# Sept 29 bars
sep29 = df[df['timestamp'].dt.date == pd.to_datetime('2025-09-29').date()]
start_idx = sep29.index[0]
end_idx = sep29.index[-1]

# Run system
settings = TradingSettings(neighbors_count=8, reentry_window_start=0)
system = LorentzianTradingSystem(settings)

high, low, close = df['high'].values, df['low'].values, df['close'].values
results = system.generate_signals(high, low, close, start_bar=100)

print("\n" + "="*80)
print("SEPT 29 BAR-BY-BAR BREAKDOWN")
print("="*80)

for idx in range(start_idx, end_idx + 1):
    time = df.loc[idx, 'timestamp'].strftime('%H:%M')
    
    # Extract all components
    ml_signal = results['signals'][idx]
    prediction = results['predictions'][idx]
    filter_pass = results['filter_all'][idx]
    kernel_bull = results['kernel_estimate'][idx] > results['kernel_estimate'][idx-1] if idx > 0 else False
    kernel_bear = results['kernel_estimate'][idx] < results['kernel_estimate'][idx-1] if idx > 0 else False
    
    vol_filter = filter_volatility(high, low, close, 1, 10)[idx]
    reg_filter = regime_filter(high, low, close, -0.1)[idx]
    
    entry_long = results['start_long'][idx]
    entry_short = results['start_short'][idx]
    
    # Only print if ML has signal
    if ml_signal != 0:
        print(f"\n{time} | Bar {idx}")
        print(f"  ML Signal: {ml_signal:+d} | Prediction: {prediction:+.1f}")
        print(f"  Kernel: {'🟢 Bull' if kernel_bull else '🔴 Bear' if kernel_bear else '⚪ Flat'}")
        print(f"  Vol Filter: {'✅' if vol_filter else '❌'}")
        print(f"  Regime Filter: {'✅' if reg_filter else '❌'}")
        print(f"  Combined Filter: {'✅' if filter_pass else '❌'}")
        print(f"  Entry: {'🟢 LONG' if entry_long else '🔴 SHORT' if entry_short else '❌ None'}")
        
        if not entry_long and not entry_short and ml_signal != 0:
            print(f"  ⚠️  SIGNAL BLOCKED:")
            if not filter_pass:
                if not vol_filter: print(f"     - Volatility filter")
                if not reg_filter: print(f"     - Regime filter")
            if ml_signal == 1 and not kernel_bull:
                print(f"     - Kernel not bullish")
            if ml_signal == -1 and not kernel_bear:
                print(f"     - Kernel not bearish")

print("\n" + "="*80)
print("TRADINGVIEW EXPECTED (add manually):")
print("  11:15 - SHORT entry")
print("="*80)