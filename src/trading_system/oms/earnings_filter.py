"""
Earnings Season Filter

Port of the simple month/day logic:
- Earnings months (YELLOW): Jan, Apr, Jul, Oct
- 60D Before (BLUE): Feb, May, Aug, Nov
- 45D Before (GREEN): Mar, Jun, Sep, Dec

Blocked periods:
- First N days of BLUE zone (e.g., Feb day<=N, May day<=N, Aug day<=N, Nov day<=N)
- N days after YELLOW zone ends → also first N days of the following BLUE month
  (Effectively the same month/day window as above)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..logging import ComponentLogger


@dataclass(slots=True)
class EarningsFilterConfig:
    use_filter: bool = True
    block_first_days_blue: int = 15
    block_after_yellow: int = 15


class EarningsSeasonFilter:
    def __init__(
        self,
        config: Optional[EarningsFilterConfig] = None,
        logger: Optional[ComponentLogger] = None,
    ) -> None:
        self.config = config or EarningsFilterConfig()
        self.logger = logger or ComponentLogger.get_logger("earnings_filter")

    @staticmethod
    def _is_earnings_month(month: int) -> bool:
        # Jan, Apr, Jul, Oct
        return month in (1, 4, 7, 10)

    @staticmethod
    def _is_60d_before_month(month: int) -> bool:
        # Feb, May, Aug, Nov
        return month in (2, 5, 8, 11)

    @staticmethod
    def _is_45d_before_month(month: int) -> bool:
        # Mar, Jun, Sep, Dec
        return month in (3, 6, 9, 12)

    def is_blocked(self, now: Optional[datetime] = None) -> bool:
        """
        Returns True if trading should be blocked due to earnings season filter.
        """
        if not self.config.use_filter:
            return False

        now = now or datetime.now()
        m = now.month
        d = now.day

        is_60d_before = self._is_60d_before_month(m)
        # First N days of BLUE zone
        is_early_blue_zone = is_60d_before and d <= self.config.block_first_days_blue

        # N days after YELLOW ends: first N days of the BLUE month
        is_post_yellow_block = is_60d_before and d <= self.config.block_after_yellow

        blocked = is_early_blue_zone or is_post_yellow_block
        if blocked:
            self.logger.info(
                "Earnings filter active: blocking trades",
                month=m,
                day=d,
                block_first_days_blue=self.config.block_first_days_blue,
                block_after_yellow=self.config.block_after_yellow,
            )
        return blocked


