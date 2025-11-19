"""
Run backtest with all 4 exit strategy configurations:
1. Default 4-bar exit only
2. Default 4-bar + volume peak exit (both LONG and SHORT)
3. Default 4-bar + volume peak exit (LONG only)
4. Default 4-bar + volume peak exit (SHORT only)
"""

import sys
from pathlib import Path
from typing import List, Dict

# Fix path: file is at src/strategy/runners/run_backtest_volume_exits.py
# parents[0] = src/strategy/runners
# parents[1] = src/strategy
# parents[2] = src
# parents[3] = project root
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_PATH = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_PATH):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from src.trading_system.backtest import SingleTimeframeBacktester
from src.trading_system.config import AppConfig, BacktestConfig as TradingBacktestConfig
from src.strategy.backtest.config import (
    get_config_single_tf_default,
    get_config_single_tf_volume_both,
    get_config_single_tf_volume_long,
    get_config_single_tf_volume_short,
)


def print_summary(metrics: dict, trades: List, config_name: str) -> None:
    """Print backtest summary"""
    print("\n" + "=" * 70)
    print(f"BACKTEST RESULTS: {config_name}")
    print("=" * 70)
    print(f"\n📊 PERFORMANCE:")
    print(f"  Total Trades:      {metrics.get('total_trades', 0)}")
    print(f"  Win Rate:          {metrics.get('win_rate', 0.0):.2f}%")
    print(f"  Profit Factor:     {metrics.get('profit_factor', 0.0):.2f}")
    print(f"  Total Return:      {metrics.get('total_return', 0.0):.2f}%")
    print(f"  Sharpe Ratio:      {metrics.get('sharpe_ratio', 0.0):.2f}")
    
    print(f"\n💰 RETURNS:")
    print(f"  Avg Win:           {metrics.get('avg_win', 0.0):.2f}%")
    print(f"  Avg Loss:          {metrics.get('avg_loss', 0.0):.2f}%")
    print(f"  Best Trade:        {metrics.get('best_trade', 0.0):.2f}%")
    print(f"  Worst Trade:       {metrics.get('worst_trade', 0.0):.2f}%")
    print(f"  Final Equity:      ${metrics.get('final_equity', 0.0):,.2f}")
    
    print(f"\n📉 DRAWDOWN:")
    max_dd = metrics.get('max_drawdown', 0.0)
    print(f"  Max Drawdown:      {max_dd:.2f}% (raw: {max_dd:.6f}%)")
    print(f"  Max DD Duration:   {metrics.get('max_dd_duration', 0)} trades")
    
    # Exit reason breakdown
    if trades:
        from collections import Counter
        exit_reasons = Counter([t.exit_reason for t in trades])
        print(f"\n🚪 EXIT REASONS:")
        for reason, count in exit_reasons.items():
            pct = (count / len(trades)) * 100
            print(f"  {reason}:         {count} ({pct:.1f}%)")
    
    print()


def main():
    """Run all 4 exit strategy configurations"""
    import time
    import signal
    import sys
    
    # Handle keyboard interrupt gracefully
    def signal_handler(sig, frame):
        print("\n\n⚠️  Keyboard interrupt detected. Exiting gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    app_config = AppConfig()
    
    # All 4 exit strategy configurations (Pine Script defaults, optimized with Numba JIT)
    configs = [
        ("1. 4-Bar Exit Only", get_config_single_tf_default()),
        ("2. 4-Bar + Volume Exit (Both)", get_config_single_tf_volume_both()),
        ("3. 4-Bar + Volume Exit (Long Only)", get_config_single_tf_volume_long()),
        ("4. 4-Bar + Volume Exit (Short Only)", get_config_single_tf_volume_short()),
    ]
    
    results = []
    
    for config_name, strategy_config in configs:
        print(f"\n{'='*70}")
        print(f"RUNNING: {config_name}")
        print(f"{'='*70}")
        print(strategy_config.summary())
        
        config_start_time = time.time()
        try:
            # Check for interrupt before starting
            signal.siginterrupt(signal.SIGINT, False)
            
            # Convert strategy config to trading system config
            trading_config = TradingBacktestConfig(
                symbol="BANKNIFTY1!",
                timeframe=strategy_config.primary_timeframe,
                lookback_bars=strategy_config.lookback_bars,
                start_bar=strategy_config.start_bar,
                default_exit_bars=strategy_config.default_exit_bars,
                neighbors_count=strategy_config.ml_settings.neighbors_count,
                max_bars_back=strategy_config.ml_settings.max_bars_back,
                use_kernel_filter=strategy_config.ml_settings.use_kernel_filter,
                use_volatility_filter=strategy_config.ml_settings.use_volatility_filter,
                use_regime_filter=strategy_config.ml_settings.use_regime_filter,
                enable_reentry=strategy_config.ml_settings.enable_reentry,
                track_drawdown=strategy_config.track_drawdown,
                save_trades=strategy_config.save_trades,
                exit_mode=strategy_config.exit_mode,
                volume_exit_lookback=getattr(strategy_config, 'volume_exit_lookback', 360),
                table_name="ohlcv",
            )
            
            # Create backtester with this config
            backtester = SingleTimeframeBacktester(
                config=trading_config,
                db_path=app_config.resolve_path(app_config.data.db_path),
            )
            
            # Run backtest
            print("\n⏳ Starting backtest...")
            result = backtester.run()
            
            config_elapsed = time.time() - config_start_time
            print(f"✅ Completed in {config_elapsed:.1f}s ({config_elapsed/60:.1f} minutes)")
            
            if result:
                metrics = result["metrics"]
                trades = result["trades"]
                
                # Print summary
                print_summary(metrics, trades, config_name)
                
                # Save results
                results.append({
                    'config_name': config_name,
                    'metrics': metrics,
                    'trades': trades,
                    'exit_mode': strategy_config.exit_mode,
                })
            else:
                print(f"❌ No results for {config_name}")
                
        except Exception as e:
            print(f"❌ Error running {config_name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Print comparison summary
    print("\n" + "=" * 70)
    print("COMPARISON SUMMARY")
    print("=" * 70)
    print(f"\n{'Strategy':<35} {'Trades':<8} {'Win Rate':<10} {'Return':<10} {'PF':<8} {'Max DD':<12}")
    print("-" * 70)
    
    for r in results:
        m = r['metrics']
        # Show more decimal places for Max DD to see actual differences
        max_dd = m.get('max_drawdown', 0.0)
        print(f"{r['config_name']:<35} {m.get('total_trades', 0):<8} "
              f"{m.get('win_rate', 0.0):>8.2f}% {m.get('total_return', 0.0):>8.2f}% "
              f"{m.get('profit_factor', 0.0):>6.2f} {max_dd:>10.4f}%")
    
    print("\n💡 WHY MAX DD MIGHT BE SAME (while other metrics differ):")
    print("   - Exit strategies affect WINNERS more than LOSERS")
    print("   - During losing streaks, both strategies exit similarly → Same max DD")
    print("   - During winning streaks, volume exits lock profits better → Different returns")
    print("   - Max DD = worst losing streak (determined by losers)")
    print("   - Returns/Win Rate = all trades (affected by winners)")
    print("   - Check actual (unrounded) values above - may differ slightly")
    print()


if __name__ == "__main__":
    main()

