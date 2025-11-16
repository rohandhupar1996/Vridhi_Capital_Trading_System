"""
Running-candle signal executor with flicker handling and instant reversal.

Rules implemented:
- Take trades immediately on running-candle signals (before candle close)
- If the signal that triggered entry does NOT exist at candle close → EXIT immediately
- If signal reverses within the same candle → EXIT immediately and ENTER the reversed side
- Candle-close reconciliation keeps the system consistent and continues normally
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Literal
from datetime import datetime

from .order_manager import OrderManager, PositionType
from ..logging import ComponentLogger
from .earnings_filter import EarningsSeasonFilter, EarningsFilterConfig


SignalType = Literal["LONG", "SHORT", "NONE"]


@dataclass
class CandleContext:
    candle_id: str  # unique key per candle (e.g., "2025-11-16 09:15:00_5min")
    opened_at: datetime
    last_signal: SignalType = "NONE"
    entry_signal: SignalType = "NONE"
    entry_candle_id: Optional[str] = None


class RunningSignalExecutor:
    """
    Handles running-candle signals with flicker and same-candle reversal logic.
    Applies earnings season filter to block entries during configured periods.
    """

    def __init__(
        self,
        oms: OrderManager,
        logger: Optional[ComponentLogger] = None,
        earnings_filter: Optional[EarningsSeasonFilter] = None,
    ) -> None:
        self.oms = oms
        self.logger = logger or ComponentLogger.get_logger("running_signal_executor")
        self.ctx: Optional[CandleContext] = None
        self.earnings_filter = earnings_filter or EarningsSeasonFilter()

    def start_new_candle(self, candle_id: str, opened_at: datetime) -> None:
        """Initialize context for a new candle."""
        self.ctx = CandleContext(candle_id=candle_id, opened_at=opened_at)
        self.logger.info("New candle started", candle_id=candle_id, opened_at=opened_at.isoformat())

    def on_running_signal(self, signal: SignalType, candle_id: str, futures_price: float) -> None:
        """
        Handle running-candle signal. Acts immediately:
        - If no position and signal is LONG/SHORT → enter
        - If opposite signal arrives in same candle → exit and reverse
        - If same signal repeats → ignore
        """
        if not self.ctx or self.ctx.candle_id != candle_id:
            # Auto-start candle context if not provided by caller
            self.start_new_candle(candle_id=candle_id, opened_at=datetime.now())

        self.ctx.last_signal = signal

        pos = self.oms.get_position_status()
        pos_type = pos["position_type"]

        if signal == "NONE":
            # Do nothing on NONE during candle; final handling at candle close
            return

        # Ensure OMS has latest futures price
        self.oms.futures_ltp = futures_price

        # No position: enter immediately
        if pos_type == PositionType.NONE.value:
            entered = self._enter_signal(signal)
            if entered:
                self.ctx.entry_signal = signal
                self.ctx.entry_candle_id = candle_id
            return

        # Already in a position
        if pos_type == signal:
            # Same-side signal on same candle → ignore
            return

        # Opposite signal on the same candle → exit and reverse instantly
        self.logger.info("Same-candle reversal detected", from_side=pos_type, to_side=signal, candle_id=candle_id)
        self._exit_all()
        entered = self._enter_signal(signal)
        if entered:
            self.ctx.entry_signal = signal
            self.ctx.entry_candle_id = candle_id

    def on_candle_close(self, final_signal: SignalType, candle_id: str, futures_price: float) -> None:
        """
        Candle-close reconciliation:
        - If a position was opened this candle but signal does NOT exist at close → EXIT immediately (flicker cleanup)
        - If final signal exists and differs from current position → switch to final signal
        - Else keep current position
        """
        if not self.ctx or self.ctx.candle_id != candle_id:
            # If context is missing, still reconcile based on current OMS state
            self.ctx = CandleContext(candle_id=candle_id, opened_at=datetime.now(), last_signal=final_signal)

        pos = self.oms.get_position_status()
        pos_type = pos["position_type"]

        self.oms.futures_ltp = futures_price

        # 1) Flicker exit: entered on this candle but final signal is NONE
        if (
            pos_type != PositionType.NONE.value
            and self.ctx.entry_candle_id == candle_id
            and final_signal == "NONE"
        ):
            self.logger.info("Flicker cleanup: signal missing at close → exiting", candle_id=candle_id)
            self._exit_all()
            # Reset context to avoid side effects
            self.ctx.entry_signal = "NONE"
            self.ctx.entry_candle_id = None
            return

        # 2) Default behavior at close: if final signal exists and differs from current position → switch
        if final_signal in ("LONG", "SHORT"):
            if pos_type != final_signal:
                self.logger.info(
                    "Candle-close switch to final signal",
                    from_side=pos_type,
                    to_side=final_signal,
                    candle_id=candle_id,
                )
                if pos_type != PositionType.NONE.value:
                    self._exit_all()
                self._enter_signal(final_signal)
                self.ctx.entry_signal = final_signal
                self.ctx.entry_candle_id = candle_id
            else:
                # Position already matches final signal; keep as-is
                pass
        else:
            # final_signal == NONE and either no position or existing position from earlier candles → no action
            pass

        # End-of-candle housekeeping
        self.ctx.last_signal = final_signal

    def _enter_signal(self, signal: SignalType) -> bool:
        # Block new entries if earnings filter is active
        if self.earnings_filter.is_blocked():
            self.logger.info("Trade blocked by earnings season filter")
            return False

        if signal == "LONG":
            return self.oms.enter_long(fast_execution=True)
        if signal == "SHORT":
            return self.oms.enter_short(fast_execution=True)
        return False

    def _exit_all(self) -> bool:
        return self.oms.exit_position()


