"""
Debug Missing Signals - Find where 40 signals are being blocked
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import sqlite3
import pandas as pd
import numpy as np
from core.trading_system import LorentzianTradingSystem, TradingSettings

# Configuration
DB_PATH = "/Users/rohan/Downloads/Virdhi_Captial_trading_system/banknifty_trading_system/scripts/data/banknifty_data.db"

print("="*80)
print("🔍 DEBUGGING MISSING SIGNALS")
print("="*80)

# Load data
conn = sqlite3.connect(DB_PATH)
df = pd.read_sql_query("""
    SELECT timestamp, open, high, low, close, volume
    FROM ohlcv WHERE timeframe = '15min'
    ORDER BY timestamp DESC LIMIT 3000
""", conn)
conn.close()

df = df.iloc[::-1].reset_index(drop=True)
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s').dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')

print(f"\n✅ Loaded {len(df)} bars")
print(f"   From: {df['timestamp'].min()}")
print(f"   To:   {df['timestamp'].max()}\n")

# Test 4 configurations
configs = [
    ("CURRENT (All Filters)", TradingSettings(
        neighbors_count=5, max_bars_back=2000,
        use_kernel_filter=True, use_volatility_filter=True, 
        use_regime_filter=True, enable_reentry=True
    )),
    ("NO KERNEL", TradingSettings(
        neighbors_count=5, max_bars_back=2000,
        use_kernel_filter=False, use_volatility_filter=True, 
        use_regime_filter=True, enable_reentry=True
    )),
    ("NO VOL/REGIME", TradingSettings(
        neighbors_count=5, max_bars_back=2000,
        use_kernel_filter=True, use_volatility_filter=False, 
        use_regime_filter=False, enable_reentry=True
    )),
    ("NO FILTERS", TradingSettings(
        neighbors_count=5, max_bars_back=2000,
        use_kernel_filter=False, use_volatility_filter=False, 
        use_regime_filter=False, enable_reentry=True
    ))
]

print("="*80)
print("📊 TESTING FILTER CONFIGURATIONS")
print("="*80)

for name, settings in configs:
    system = LorentzianTradingSystem(settings)
    results = system.generate_signals(
        df['high'].values, df['low'].values, df['close'].values, start_bar=100
    )
    
    long = np.sum(results['start_long'])
    short = np.sum(results['start_short'])
    total = long + short
    
    print(f"\n{name:20s}: {total:3d} trades (L:{long:3d} S:{short:3d})")

# Detailed analysis with current settings
print("\n" + "="*80)
print("🔎 DETAILED BLOCKING ANALYSIS (Current Settings)")
print("="*80)

system = LorentzianTradingSystem(configs[0][1])
results = system.generate_signals(
    df['high'].values, df['low'].values, df['close'].values, start_bar=100
)

predictions = results['predictions']
signals = results['signals']

# Detect kernel trend
kernel_estimate = results['kernel_estimate']
kernel_bullish = np.zeros(len(kernel_estimate), dtype=bool)
kernel_bearish = np.zeros(len(kernel_estimate), dtype=bool)
kernel_bullish[1:] = kernel_estimate[1:] > kernel_estimate[:-1]
kernel_bearish[1:] = kernel_estimate[1:] < kernel_estimate[:-1]

filter_all = results['filter_all']

# Count at each stage
ml_long = np.sum(predictions > 0)
ml_short = np.sum(predictions < 0)

kernel_long = np.sum((predictions > 0) & kernel_bullish)
kernel_short = np.sum((predictions < 0) & kernel_bearish)

filtered_long = np.sum((predictions > 0) & kernel_bullish & filter_all)
filtered_short = np.sum((predictions < 0) & kernel_bearish & filter_all)

final_long = np.sum(results['start_long'])
final_short = np.sum(results['start_short'])

print(f"\nLONG Pipeline:")
print(f"  ML Predictions:     {ml_long}")
print(f"  After Kernel:       {kernel_long} (blocked: {ml_long - kernel_long})")
print(f"  After Filters:      {filtered_long} (blocked: {kernel_long - filtered_long})")
print(f"  Final Entries:      {final_long} (blocked: {filtered_long - final_long})")

print(f"\nSHORT Pipeline:")
print(f"  ML Predictions:     {ml_short}")
print(f"  After Kernel:       {kernel_short} (blocked: {ml_short - kernel_short})")
print(f"  After Filters:      {filtered_short} (blocked: {kernel_short - filtered_short})")
print(f"  Final Entries:      {final_short} (blocked: {filtered_short - final_short})")

print(f"\n{'='*80}")
print(f"TOTAL: {final_long + final_short} trades (Target: 178)")
print(f"MISSING: {178 - (final_long + final_short)} signals")
print(f"{'='*80}")

# Find blocked signals
blocked = []
for i in range(100, len(df)):
    if predictions[i] > 0:
        direction = "LONG"
        kernel_ok = kernel_bullish[i]
    elif predictions[i] < 0:
        direction = "SHORT"
        kernel_ok = kernel_bearish[i]
    else:
        continue
    
    filter_ok = filter_all[i]
    is_entry = results['start_long'][i] if direction == "LONG" else results['start_short'][i]
    
    if not is_entry:
        reason = []
        if not kernel_ok: reason.append("KERNEL")
        if not filter_ok: reason.append("FILTER")
        if kernel_ok and filter_ok: reason.append("REENTRY")
        
        blocked.append({
            'date': df.loc[i, 'timestamp'],
            'dir': direction,
            'price': df.loc[i, 'close'],
            'reason': '+'.join(reason)
        })

print(f"\n📋 First 15 Blocked Signals:")
for b in blocked[:15]:
    print(f"  {b['date']} | {b['dir']:5s} @ {b['price']:8.2f} | {b['reason']}")

# Count reasons
from collections import Counter
reasons = Counter([b['reason'] for b in blocked])
print(f"\n📊 Blocking Reasons:")
for r, c in reasons.most_common():
    print(f"  {r:15s}: {c:3d}")

print(f"\n💡 SOLUTION:")
if reasons.get('KERNEL', 0) > 30:
    print("  → KERNEL FILTER blocking most signals")
    print("  → Set use_kernel_filter=False in BacktestConfig")
elif reasons.get('FILTER', 0) > 30:
    print("  → VOL/REGIME FILTERS blocking most signals")
    print("  → Set use_volatility_filter=False, use_regime_filter=False")
else:
    print("  → RE-ENTRY logic blocking signals")
    print("  → Adjust reentry_window_start/end parameters")

print("\n✅ Debug complete")