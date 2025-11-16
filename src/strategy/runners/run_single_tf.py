"""
FIXED Single Timeframe Backtest Runner
start_bar=96 to match TradingView's May 22, 2025 start
"""
import sys
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_PATH):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from src.trading_system.backtest import SingleTimeframeBacktester
from src.trading_system.config import AppConfig


def _print_detailed_summary(metrics: dict, trades: List) -> None:
    if not trades:
        print("No trades to summarize.")
        return

    pnl_values = [t.pnl_pct for t in trades]
    mfe_values = [t.max_favorable_pct for t in trades]
    mae_values = [abs(t.max_adverse_pct) for t in trades]

    winners = [t for t in trades if t.pnl_pct > 0]
    losers = [t for t in trades if t.pnl_pct <= 0]

    best_trade = max(pnl_values)
    worst_trade = min(pnl_values)

    avg_win = metrics.get("avg_win", 0.0)
    avg_loss = abs(metrics.get("avg_loss", 0.0))

    avg_mfe = sum(mfe_values) / len(mfe_values)
    avg_mae = sum(mae_values) / len(mae_values)

    if winners:
        winners_mfe = sum(t.max_favorable_pct for t in winners) / len(winners)
        winners_mae = sum(abs(t.max_adverse_pct) for t in winners) / len(winners)
    else:
        winners_mfe = winners_mae = 0.0

    if losers:
        losers_mfe = sum(t.max_favorable_pct for t in losers) / len(losers)
        losers_mae = sum(abs(t.max_adverse_pct) for t in losers) / len(losers)
    else:
        losers_mfe = losers_mae = 0.0

    total_longs = sum(1 for t in trades if t.direction == 1)
    total_shorts = len(trades) - total_longs
    long_wins = sum(1 for t in trades if t.direction == 1 and t.pnl_pct > 0)
    short_wins = sum(1 for t in trades if t.direction == -1 and t.pnl_pct > 0)
    long_win_rate = (long_wins / total_longs * 100) if total_longs else 0.0
    short_win_rate = (short_wins / total_shorts * 100) if total_shorts else 0.0

    # Win/Loss streaks
    current_streak = 0
    max_win_streak = 0
    max_loss_streak = 0
    for pnl in pnl_values:
        if pnl > 0:
            current_streak = current_streak + 1 if current_streak > 0 else 1
            max_win_streak = max(max_win_streak, current_streak)
        else:
            current_streak = current_streak - 1 if current_streak < 0 else -1
            max_loss_streak = max(max_loss_streak, abs(current_streak))

    # Drawdown duration from equity curve
    equity_curve = metrics.get("equity_curve", [])
    max_dd_duration = 0
    if equity_curve is not None:
        peak = equity_curve[0]
        duration = 0
        for eq in equity_curve[1:]:
            if eq >= peak:
                peak = eq
                duration = 0
            else:
                duration += 1
                max_dd_duration = max(max_dd_duration, duration)

    print("\n" + "=" * 70)
    print("BACKTEST RESULTS")
    print("=" * 70)
    print("\n📊 PERFORMANCE:")
    print(f"  Total Trades:      {metrics.get('total_trades', 0)}")
    print(f"  Win Rate:          {metrics.get('win_rate', 0.0):.2f}%")
    print(f"  Profit Factor:     {metrics.get('profit_factor', 0.0):.2f}")
    print(f"  Total Return:      {metrics.get('total_return', 0.0):.2f}%")
    print(f"  Sharpe Ratio:      {metrics.get('sharpe_ratio', 0.0):.2f}")

    print("\n💰 RETURNS:")
    print(f"  Avg Win:           {avg_win:.2f}%")
    print(f"  Avg Loss:          -{avg_loss:.2f}%")
    print(f"  Best Trade:        {best_trade:.2f}%")
    print(f"  Worst Trade:       {worst_trade:.2f}%")
    print(f"  Final Equity:      ${metrics.get('final_equity', 0.0):,.2f}")

    print("\n📉 DRAWDOWN:")
    print(f"  Max Drawdown:      {metrics.get('max_drawdown', 0.0):.2f}%")
    print(f"  DD Duration:       {max_dd_duration} trades")

    print("\n🔥 STREAKS:")
    print(f"  Max Win Streak:    {max_win_streak}")
    print(f"  Max Loss Streak:   {max_loss_streak}")

    print("\n💥 MFE/MAE ANALYSIS:")
    print(f"  Avg MFE:           {avg_mfe:.2f}%")
    print(f"  Avg MAE:           {avg_mae:.2f}%")
    print(f"  Winners MFE:       {winners_mfe:.2f}%")
    print(f"  Winners MAE:       {winners_mae:.2f}%")
    print(f"  Losers MFE:        {losers_mfe:.2f}%")
    print(f"  Losers MAE:        {losers_mae:.2f}%")

    print("\n📈 DIRECTION BREAKDOWN:")
    print(f"  Total LONG:        {total_longs} ({long_win_rate:.1f}% win)")
    print(f"  Total SHORT:       {total_shorts} ({short_win_rate:.1f}% win)")

    print()


if __name__ == "__main__":
    app_config = AppConfig()

    backtester = SingleTimeframeBacktester(
        config=app_config.backtest,
        db_path=app_config.resolve_path(app_config.data.db_path),
    )
    results = backtester.run()

    if results:
        metrics = results["metrics"]
        trades = results["trades"]
        _print_detailed_summary(metrics, trades)
       