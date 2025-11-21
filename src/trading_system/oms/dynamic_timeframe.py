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
    Uses actual expiry from Zerodha option chain (SOURCE OF TRUTH).
    NO FALLBACKS - If option chain data unavailable, returns base timeframe.
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
        Get actual current expiry date from Zerodha option chain (SOURCE OF TRUTH).
        Gets expiry from BANKNIFTY CE/PE options - this is the actual expiry date.
        Monthly options and futures expire on SAME DATE.
        
        IMPORTANT: NO FALLBACKS - Returns None if option chain data unavailable.
        Option chain is the ONLY source of truth for expiry dates.
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
        Uses actual expiry from Zerodha option chain (SOURCE OF TRUTH).
        
        IMPORTANT: NO FALLBACKS - If option chain data unavailable, returns False.
        Option chain is the ONLY source of truth for expiry dates.
        """
        if not self.config.enable_expiry_switch:
            return False
        
        # Check cache first (expiry date doesn't change during the day)
        if self._cached_expiry_date and dt.date() == self._cached_expiry_date:
            return True
        
        # Get actual expiry from Zerodha option chain (ONLY SOURCE OF TRUTH)
        actual_expiry = self._get_actual_expiry_date(dt)
        if actual_expiry:
            self._cached_expiry_date = actual_expiry
            return dt.date() == actual_expiry
        
        # NO FALLBACK - If option chain unavailable, cannot determine expiry
        self.logger.warning(
            f"Cannot determine expiry day: Option chain data unavailable",
            date=dt.date().isoformat()
        )
        return False

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


