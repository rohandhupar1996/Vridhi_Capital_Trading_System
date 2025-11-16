"""
Dynamic timeframe switching for expiry day.

Requirement:
- On the monthly futures/options expiry day, switch signal timeframe to 5min for that day only.
- From the next day, revert to the normal/default timeframe (e.g., 15min).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, date
from typing import Literal, Optional

from ..logging import ComponentLogger


Timeframe = Literal["1min", "3min", "5min", "10min", "15min", "30min", "1hour"]


def _last_thursday(year: int, month: int) -> date:
    """
    Compute the last Thursday of a given month.
    Note: This ignores exchange holiday shifts; production users can extend this
    by injecting an exchange calendar if needed.
    """
    # Start from last day of month, walk backwards to Thursday (weekday 3)
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    last_day = next_month - timedelta(days=1)
    # Python weekday: Monday=0 ... Sunday=6; Thursday=3
    offset = (last_day.weekday() - 3) % 7
    return last_day - timedelta(days=offset)


@dataclass(slots=True)
class DynamicTimeframeConfig:
    """
    Configuration for dynamic timeframe switching.
    """
    base_timeframe: Timeframe = "15min"
    expiry_day_timeframe: Timeframe = "5min"
    enable_expiry_switch: bool = True


class DynamicTimeframeController:
    """
    Determines the effective timeframe for the current day based on monthly expiry.
    """

    def __init__(
        self,
        config: Optional[DynamicTimeframeConfig] = None,
        logger: Optional[ComponentLogger] = None,
    ) -> None:
        self.config = config or DynamicTimeframeConfig()
        self.logger = logger or ComponentLogger.get_logger("dynamic_timeframe")

    def is_expiry_day(self, dt: datetime) -> bool:
        """
        Return True if dt falls on the monthly expiry (last Thursday) date.
        """
        if not self.config.enable_expiry_switch:
            return False
        expiry = _last_thursday(dt.year, dt.month)
        return dt.date() == expiry

    def get_effective_timeframe(self, now: Optional[datetime] = None) -> Timeframe:
        """
        Returns the effective timeframe:
        - expiry day → expiry_day_timeframe (default 5min)
        - otherwise → base_timeframe (default 15min)
        """
        now = now or datetime.now()
        if self.is_expiry_day(now):
            self.logger.info(
                "Expiry day detected: switching timeframe",
                date=now.date().isoformat(),
                timeframe=self.config.expiry_day_timeframe,
            )
            return self.config.expiry_day_timeframe

        return self.config.base_timeframe


