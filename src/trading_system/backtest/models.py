"""Backtest-related dataclasses and enums."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class ExitReason(str, Enum):
    DEFAULT = "default"
    BARS = "bars"
    END_OF_DATA = "end_of_data"
    SIGNAL_FLIP = "signal_flip"


@dataclass(slots=True)
class Trade:
    entry_bar: int
    entry_time: datetime
    entry_price: float
    direction: int
    timeframe: str

    exit_bar: Optional[int] = None
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: str = ""
    bars_held: int = 0

    pnl_pct: float = 0.0
    max_favorable_pct: float = 0.0
    max_adverse_pct: float = 0.0

