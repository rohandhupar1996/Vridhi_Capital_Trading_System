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


class SingleTimeframeBacktester:
    """Self-contained backtest runner for Lorentzian strategy."""

    def __init__(self, config: BacktestConfig, db_path: Path) -> None:
        self.config = config
        self.db_path = Path(db_path)
        self._trades: List[Trade] = []
        self._current_trade: Optional[Trade] = None
        self._data: Optional[pd.DataFrame] = None

        self._exit = ExitController(config.default_exit_bars)
        self._system = LorentzianTradingSystem(
            TradingSettings(
                neighbors_count=config.neighbors_count,
                max_bars_back=config.max_bars_back,
                use_kernel_filter=config.use_kernel_filter,
                use_volatility_filter=config.use_volatility_filter,
                use_regime_filter=config.use_regime_filter,
                enable_reentry=config.enable_reentry,
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

        for bar in range(self.config.start_bar, len(self._data)):
            if self._current_trade and self.config.track_drawdown:
                self._update_trade_drawdown(bar)

            if self._current_trade:
                should_exit, reason = self._exit.should_exit(self._current_trade, bar)
                if should_exit:
                    self._exit_trade(bar, reason)
                    continue

            if not self._current_trade:
                if signals["start_long"][bar]:
                    self._enter_trade(bar, direction=1)
                elif signals["start_short"][bar]:
                    self._enter_trade(bar, direction=-1)

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
        query = (
            "SELECT timestamp, open, high, low, close, volume "
            "FROM ohlcv WHERE symbol = ? AND timeframe = ? "
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

    def _exit_trade(self, bar: int, reason: str) -> None:
        assert self._data is not None
        if not self._current_trade:
            return

        row = self._data.loc[bar]
        self._current_trade.exit_bar = bar
        self._current_trade.exit_time = row["timestamp"]
        self._current_trade.exit_price = float(row["close"])
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

