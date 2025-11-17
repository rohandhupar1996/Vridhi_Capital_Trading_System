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
    Can use actual expiry from Zerodha instruments or calculated last Thursday.
    """

    def __init__(
        self,
        config: Optional[DynamicTimeframeConfig] = None,
        logger: Optional[ComponentLogger] = None,
        kite=None,  # Optional KiteConnect instance for actual expiry lookup
    ) -> None:
        self.config = config or DynamicTimeframeConfig()
        self.logger = logger or ComponentLogger.get_logger("dynamic_timeframe")
        self.kite = kite
        self._cached_expiry_date: Optional[date] = None  # Cache expiry date for the day

    def _get_actual_expiry_date(self, dt: datetime) -> Optional[date]:
        """
        Get actual current expiry date from Zerodha instruments dynamically.
        Gets the nearest (current) expiry, not just current month - handles expiry transitions.
        Returns None if not available, falls back to calculated last Thursday.
        """
        if not self.kite:
            return None
        
        try:
            from datetime import date
            # Get all BankNifty options from Zerodha
            instruments = self.kite.instruments("NFO")
            
            # Find all active (non-expired) expiry dates for BankNifty options
            today = dt.date()
            
            expiry_dates = set()
            for inst in instruments:
                if (inst.get('name') == 'BANKNIFTY' and 
                    inst.get('instrument_type') in ['CE', 'PE']):
                    expiry = inst.get('expiry')
                    if expiry:
                        try:
                            # Handle different expiry formats
                            if isinstance(expiry, str):
                                exp_date = datetime.strptime(expiry, '%Y-%m-%d').date()
                            elif isinstance(expiry, datetime):
                                exp_date = expiry.date()
                            elif isinstance(expiry, date):
                                exp_date = expiry
                            else:
                                continue
                            
                            # Only include non-expired contracts
                            if exp_date >= today:
                                expiry_dates.add(exp_date)
                        except (ValueError, TypeError):
                            continue
            
            if expiry_dates:
                # Get the nearest (earliest) expiry date (current expiry contract)
                nearest_expiry = min(expiry_dates)
                self.logger.info(
                    f"Found current expiry from Zerodha: {nearest_expiry}",
                    expiry_date=nearest_expiry.isoformat(),
                    days_until_expiry=(nearest_expiry - today).days
                )
                return nearest_expiry
            
        except Exception as e:
            self.logger.warning(f"Error getting expiry from Zerodha: {e}")
        
        return None

    def is_expiry_day(self, dt: datetime) -> bool:
        """
        Return True if dt falls on the monthly expiry date.
        Uses actual expiry from Zerodha if available, otherwise calculates last Thursday.
        """
        if not self.config.enable_expiry_switch:
            return False
        
        # Check cache first (expiry date doesn't change during the day)
        if self._cached_expiry_date and dt.date() == self._cached_expiry_date:
            return True
        
        # Try to get actual expiry from Zerodha
        actual_expiry = self._get_actual_expiry_date(dt)
        if actual_expiry:
            self._cached_expiry_date = actual_expiry
            return dt.date() == actual_expiry
        
        # Fallback to calculated last Thursday
        expiry = _last_thursday(dt.year, dt.month)
        self._cached_expiry_date = expiry
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


