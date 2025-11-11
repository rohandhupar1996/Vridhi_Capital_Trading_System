"""
Calculate Win/Loss Streaks from Backtest Results
"""
import pandas as pd
import numpy as np

# Load trades
df = pd.read_csv('banknifty_trades_no_volume.csv')

# Calculate streaks
df['is_win'] = df['pnl_pct'] > 0
streaks = []
current_streak = 0
streak_type = None

for idx, row in df.iterrows():
    is_win = row['is_win']
    
    if streak_type is None:
        streak_type = 'win' if is_win else 'loss'
        current_streak = 1
    elif (is_win and streak_type == 'win') or (not is_win and streak_type == 'loss'):
        current_streak += 1
    else:
        streaks.append({'type': streak_type, 'length': current_streak})
        streak_type = 'win' if is_win else 'loss'
        current_streak = 1

# Add last streak
if current_streak > 0:
    streaks.append({'type': streak_type, 'length': current_streak})

streaks_df = pd.DataFrame(streaks)

print("="*60)
print("WIN/LOSS STREAK ANALYSIS")
print("="*60)

# Win streaks
win_streaks = streaks_df[streaks_df['type'] == 'win']['length']
loss_streaks = streaks_df[streaks_df['type'] == 'loss']['length']

print(f"\n📈 WIN STREAKS:")
print(f"  Max consecutive wins: {win_streaks.max()}")
print(f"  Avg win streak:       {win_streaks.mean():.2f}")
print(f"  Median win streak:    {win_streaks.median():.0f}")

print(f"\n📉 LOSS STREAKS:")
print(f"  Max consecutive losses: {loss_streaks.max()}")
print(f"  Avg loss streak:        {loss_streaks.mean():.2f}")
print(f"  Median loss streak:     {loss_streaks.median():.0f}")

# Distribution
print(f"\n📊 STREAK DISTRIBUTION:")
for length in range(1, max(win_streaks.max(), loss_streaks.max()) + 1):
    win_count = len(win_streaks[win_streaks == length])
    loss_count = len(loss_streaks[loss_streaks == length])
    print(f"  {length} trades: {win_count} win streaks, {loss_count} loss streaks")

print(f"\n💡 INSIGHTS:")
print(f"  Total streaks: {len(streaks_df)}")
print(f"  Alternating vs Clustering: {len(streaks_df) / len(df) * 100:.1f}% alternation rate")