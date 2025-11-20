"""Modular backtest engine for single-timeframe strategies."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import pytz

from src.strategy.core.trading_system import (  # type: ignore[import]
    LorentzianTradingSystem,
    TradingSettings,
)
from src.strategy.backtest.metrics import MetricsCalculator  # type: ignore[import]
from src.strategy.backtest.volume_node_exit import VolumeNodeExitStrategy  # type: ignore[import]
from src.trading_system.config import BacktestConfig
from src.trading_system.backtest.models import ExitReason, Trade

# Asia/Kolkata timezone
KOLKATA_TZ = pytz.timezone("Asia/Kolkata")


class ExitController:
    """Encapsulate exit decisions (default: fixed number of bars)."""

    def __init__(self, bars: int) -> None:
        self._bars = bars

    def should_exit(self, trade: Trade, current_bar: int) -> tuple[bool, str]:
        held = current_bar - trade.entry_bar
        if held >= self._bars:
            return True, f"{self._bars}_bars"
        return False, ""
    
    def should_exit_with_price(
        self, trade: Trade, current_bar: int, historical_data: pd.DataFrame
    ) -> tuple[bool, str, Optional[float]]:
        """Check exit with optional price override (for volume exits)."""
        held = current_bar - trade.entry_bar
        if held >= self._bars:
            return True, f"{self._bars}_bars", None
        return False, "", None


class SingleTimeframeBacktester:
    """Self-contained backtest runner for Lorentzian strategy."""

    def __init__(self, config: BacktestConfig, db_path: Path) -> None:
        self.config = config
        self.db_path = Path(db_path)
        self._trades: List[Trade] = []
        self._current_trade: Optional[Trade] = None
        self._data: Optional[pd.DataFrame] = None

        # Initialize exit strategy based on config
        # Support both new and legacy exit mode names
        exit_mode = getattr(config, 'exit_mode', 'default')
        
        # Map legacy names to new names
        legacy_map = {
            'default': '4bar_only',
            'volume_both': '4bar_with_volume',
            'volume_long': '4bar_with_volume_long',
            'volume_short': '4bar_with_volume_short',
        }
        if exit_mode in legacy_map:
            exit_mode = legacy_map[exit_mode]
        
        if exit_mode == '4bar_only':
            # Default 4-bar exit only (no volume exit)
            self._exit = ExitController(config.default_exit_bars)
            self._volume_exit = None
        else:
            # 4-bar exit + volume peak exit (whichever triggers first)
            use_volume_both = exit_mode == '4bar_with_volume'
            use_volume_long = exit_mode == '4bar_with_volume_long'
            use_volume_short = exit_mode == '4bar_with_volume_short'
            
            self._exit = None
            self._volume_exit = VolumeNodeExitStrategy(
                default_exit_bars=config.default_exit_bars,
                use_volume_exit=use_volume_both,
                volume_exit_long=use_volume_long,
                volume_exit_short=use_volume_short,
                volume_lookback=getattr(config, 'volume_exit_lookback', 240),  # Optimized default (Pine Script: 360)
                volume_num_rows=getattr(config, 'volume_exit_num_rows', 60),   # Optimized default (Pine Script: 100)
                volume_value_area=getattr(config, 'volume_exit_value_area', 0.7),
                volume_peak_percent=getattr(config, 'volume_exit_peak_percent', 0.09),
                volume_trough_percent=getattr(config, 'volume_exit_trough_percent', 0.07),
                volume_threshold=getattr(config, 'volume_exit_threshold', 0.01),
            )
        
        self._system = LorentzianTradingSystem(
            TradingSettings(
                neighbors_count=getattr(config, 'neighbors_count', 5),
                max_bars_back=getattr(config, 'max_bars_back', config.lookback_bars if hasattr(config, 'lookback_bars') else 3000),
                use_kernel_filter=getattr(config, 'use_kernel_filter', True),
                use_volatility_filter=getattr(config, 'use_volatility_filter', True),
                use_regime_filter=getattr(config, 'use_regime_filter', True),
                enable_reentry=getattr(config, 'enable_reentry', True),
            )
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self) -> Dict:
        self._load_data()
        if self._data is None:
            raise RuntimeError("No data available for backtest run")

        signals = self._system.generate_signals(
            self._data["high"].values,
            self._data["low"].values,
            self._data["close"].values,
            start_bar=self.config.start_bar,
        )

        total_bars = len(self._data) - self.config.start_bar
        progress_interval = max(100, total_bars // 10)  # Print progress every 10% or every 100 bars
        
        try:
            for bar_idx, bar in enumerate(range(self.config.start_bar, len(self._data))):
                # Check for keyboard interrupt periodically (every bar for responsiveness)
                if bar_idx % 10 == 0:  # Check every 10 bars
                    import signal
                    signal.siginterrupt(signal.SIGINT, False)  # Make interruptible
                
                # Print progress for long-running backtests
                if bar_idx % progress_interval == 0 and self._volume_exit:
                    progress = (bar_idx / total_bars) * 100
                    print(f"⏳ Progress: {bar_idx}/{total_bars} bars ({progress:.1f}%)")
                
                if self._current_trade and self.config.track_drawdown:
                    self._update_trade_drawdown(bar)

                if self._current_trade:
                    # Check exit based on strategy
                    if self._volume_exit:
                        # Volume exit strategy (includes default + volume)
                        # Pass entire DataFrame reference, not slice - detector will handle slicing internally
                        row = self._data.loc[bar]
                        should_exit, reason, exit_price = self._volume_exit.should_exit(
                            trade_direction=self._current_trade.direction,
                            entry_bar=self._current_trade.entry_bar,
                            current_bar=bar,
                            historical_data=self._data,  # Pass full DataFrame - detector handles slicing
                            current_high=float(row["high"]),
                            current_low=float(row["low"]),
                            current_close=float(row["close"]),
                            entry_price=self._current_trade.entry_price,  # Pass entry price to filter peaks (targets only)
                        )
                        # Pass entry_bar to check_exit for debug logging
                        if self._volume_exit and self._volume_exit.volume_detector:
                            # The entry_bar is already passed via should_exit -> check_exit, but we need to pass it through
                            pass
                        if should_exit:
                            self._exit_trade(bar, reason, exit_price=exit_price)
                            continue
                    else:
                        # Default exit only
                        should_exit, reason = self._exit.should_exit(self._current_trade, bar)
                        if should_exit:
                            self._exit_trade(bar, reason)
                            continue

                if not self._current_trade:
                    if signals["start_long"][bar]:
                        self._enter_trade(bar, direction=1)
                    elif signals["start_short"][bar]:
                        self._enter_trade(bar, direction=-1)
        except KeyboardInterrupt:
            print("\n\n⚠️  Keyboard interrupt received. Stopping backtest...")
            print(f"   Processed {bar_idx}/{total_bars} bars ({bar_idx/total_bars*100:.1f}%)")
            if self._current_trade:
                print(f"   Exiting current trade at bar {bar}")
                self._exit_trade(bar, "interrupted", exit_price=None)
            raise  # Re-raise to allow cleanup

        if self._current_trade:
            self._exit_trade(len(self._data) - 1, ExitReason.END_OF_DATA.value)

        metrics = MetricsCalculator.calculate_all_metrics(
            self._trades, self.config.initial_capital
        )

        if self.config.save_trades:
            self._save_trades()

        return {
            "trades": self._trades,
            "metrics": metrics,
            "config": self.config,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_data(self) -> None:
        # Use ohlcv_zerodha table if available (for Zerodha data), otherwise ohlcv (TradingView data)
        table_name = getattr(self.config, 'table_name', 'ohlcv')
        # Validate table name to prevent SQL injection (only allow known safe table names)
        allowed_tables = {'ohlcv', 'ohlcv_zerodha'}
        if table_name not in allowed_tables:
            raise ValueError(f"Invalid table name: {table_name}. Allowed: {allowed_tables}")
        
        query = (
            "SELECT timestamp, open, high, low, close, volume "
            f"FROM {table_name} WHERE symbol = ? AND timeframe = ? "
            "ORDER BY timestamp DESC LIMIT ?"
        )
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(
                query,
                conn,
                params=(
                    self.config.symbol,
                    self.config.timeframe,
                    self.config.lookback_bars,
                ),
            )

        if df.empty:
            raise RuntimeError(
                f"No data found for {self.config.symbol} {self.config.timeframe}"
            )

        df = df.iloc[::-1].reset_index(drop=True)
        # Convert Unix timestamp to datetime (UTC), then convert to Asia/Kolkata
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
        df["timestamp"] = df["timestamp"].dt.tz_convert(KOLKATA_TZ)
        self._data = df

    def _enter_trade(self, bar: int, direction: int) -> None:
        assert self._data is not None
        row = self._data.loc[bar]
        entry_price = (row["high"] + row["low"] + row["close"]) / 3
        self._current_trade = Trade(
            entry_bar=bar,
            entry_time=row["timestamp"],
            entry_price=float(entry_price),
            direction=direction,
            timeframe=self.config.timeframe,
        )

    def _exit_trade(self, bar: int, reason: str, exit_price: Optional[float] = None) -> None:
        assert self._data is not None
        if not self._current_trade:
            return

        row = self._data.loc[bar]
        self._current_trade.exit_bar = bar
        # Exit time is the close of the exit candle (timestamp + 15min for 15min timeframe)
        # Timestamp represents candle opening, but we exit on candle close
        exit_candle_open_time = row["timestamp"]
        # Add 15 minutes to get the candle close time (for 15min timeframe)
        from datetime import timedelta
        self._current_trade.exit_time = exit_candle_open_time + timedelta(minutes=15)
        # Use provided exit_price if available (for volume exits), otherwise use close
        self._current_trade.exit_price = float(exit_price) if exit_price is not None else float(row["close"])
        self._current_trade.exit_reason = reason
        self._current_trade.bars_held = bar - self._current_trade.entry_bar

        if self._current_trade.direction == 1:
            pnl = (
                (self._current_trade.exit_price - self._current_trade.entry_price)
                / self._current_trade.entry_price
                * 100
            )
        else:
            pnl = (
                (self._current_trade.entry_price - self._current_trade.exit_price)
                / self._current_trade.entry_price
                * 100
            )
        self._current_trade.pnl_pct = float(pnl)

        if self.config.track_drawdown:
            self._update_trade_drawdown(bar)

        self._trades.append(self._current_trade)
        self._current_trade = None

    def _update_trade_drawdown(self, bar: int) -> None:
        assert self._current_trade is not None
        assert self._data is not None
        price = float(self._data.loc[bar, "close"])
        entry_price = self._current_trade.entry_price

        if self._current_trade.direction == 1:
            favorable = (price - entry_price) / entry_price * 100
            adverse = (entry_price - price) / entry_price * 100
        else:
            favorable = (entry_price - price) / entry_price * 100
            adverse = (price - entry_price) / entry_price * 100

        self._current_trade.max_favorable_pct = max(
            self._current_trade.max_favorable_pct, favorable
        )
        self._current_trade.max_adverse_pct = max(
            self._current_trade.max_adverse_pct, adverse
        )

    def _save_trades(self) -> None:
        if not self._trades:
            return

        # Get output path - resolve relative to project root if needed
        if self.config.trades_output:
            output_path = Path(self.config.trades_output)
        else:
            # Default: save in project root
            # Find project root by looking for common markers
            current = Path(__file__).resolve()
            project_root = None
            for parent in current.parents:
                if (parent / "src" / "trading_system").exists():
                    project_root = parent
                    break
            
            if project_root:
                output_path = project_root / "trades_Single_TF_default.csv"
            else:
                # Fallback: save in current directory
                output_path = Path("trades_Single_TF_default.csv")
        
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        rows = [
            {
                "entry_time": trade.entry_time.strftime("%Y-%m-%d %H:%M:%S %Z") if trade.entry_time else "",
                "exit_time": trade.exit_time.strftime("%Y-%m-%d %H:%M:%S %Z") if trade.exit_time else "",
                "direction": "LONG" if trade.direction == 1 else "SHORT",
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "pnl_pct": trade.pnl_pct,
                "bars_held": trade.bars_held,
                "exit_reason": trade.exit_reason,
                "max_favorable_pct": trade.max_favorable_pct,
                "max_adverse_pct": trade.max_adverse_pct,
            }
            for trade in self._trades
        ]
        df = pd.DataFrame(rows)
        df.to_csv(output_path, index=False)
        print(f"💾 Trades saved to: {output_path} (timestamps in Asia/Kolkata)")


__all__ = ["SingleTimeframeBacktester"]

