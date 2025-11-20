"""
Gap Detection Module
Detects adverse gaps using FUTURES prices and exits positions immediately to prevent large losses.

IMPORTANT: We're trading OPTIONS, but gap is calculated using FUTURES prices:
- Gap = futures_today_open - futures_previous_close
- NOT option entry price

Rules:
- LONG position + Gap DOWN (adverse) → Exit immediately if > threshold
- LONG position + Gap UP (favorable) → Continue normally, exit on 4-bar or volume
- SHORT position + Gap UP (adverse) → Exit immediately if > threshold
- SHORT position + Gap DOWN (favorable) → Continue normally, exit on 4-bar or volume
"""

from __future__ import annotations

from typing import Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from ..oms.order_manager import OrderManager, PositionType
from ..data.zerodha_candle_aggregator import RunningCandle
from ..logging import ComponentLogger

DEFAULT_GAP_THRESHOLD = 300  # points (e.g., 300 points = ~0.5% loss for BankNifty)


@dataclass
class GapResult:
    """Result of gap check"""
    gap_points: float  # Gap in points (futures_today_open - futures_previous_close)
    gap_percent: float  # Gap as percentage
    is_adverse: bool  # True if gap is adverse for current position
    should_exit: bool  # True if gap exceeds threshold and is adverse
    exit_price: Optional[float]  # Exit price if should_exit is True


class GapDetector:
    """
    Detects adverse gaps using FUTURES prices and determines if position should exit.
    
    IMPORTANT: Gap is calculated using FUTURES prices, not option entry price.
    This ensures accurate gap measurement for stop loss protection.
    """
    
    def __init__(
        self,
        gap_threshold: float = DEFAULT_GAP_THRESHOLD,
        logger: Optional[ComponentLogger] = None
    ):
        """
        Initialize gap detector
        
        Args:
            gap_threshold: Gap threshold in points (default: 300)
            logger: Optional logger instance
        """
        self.gap_threshold = gap_threshold
        self.logger = logger or ComponentLogger.get_logger("gap_detector")
    
    def check_gap(
        self,
        running_candle: RunningCandle,
        futures_previous_close: float,
        position_type: PositionType
    ) -> GapResult:
        """
        Check gap up/down using FUTURES prices and determine if position should exit.
        
        Args:
            running_candle: Current running candle (futures price)
            futures_previous_close: Previous day's close (futures price)
            position_type: Current position type (LONG, SHORT, or NONE)
            
        Returns:
            GapResult with gap details and exit recommendation
        """
        # Get futures current open (from running candle - this is futures price)
        futures_current_open = running_candle.open  # Futures open price
        
        # Calculate gap using FUTURES prices (not option entry price)
        gap_points = futures_current_open - futures_previous_close
        gap_percent = (gap_points / futures_previous_close) * 100 if futures_previous_close > 0 else 0.0
        
        # No position → Calculate gap but don't exit
        if position_type == PositionType.NONE:
            return GapResult(
                gap_points=gap_points,
                gap_percent=gap_percent,
                is_adverse=False,
                should_exit=False,
                exit_price=None
            )
        
        # Determine if gap is adverse for current position
        is_adverse = False
        should_exit = False
        exit_price = None
        
        if position_type == PositionType.LONG:
            # LONG position: Gap DOWN is adverse (bad), Gap UP is favorable (good)
            if gap_points < -self.gap_threshold:  # Gap DOWN exceeds threshold
                is_adverse = True
                should_exit = True
                exit_price = futures_current_open  # Exit at futures open price
                
                self.logger.critical(
                    f"⚠️ GAP DOWN DETECTED (LONG): {abs(gap_points):.2f} points ({abs(gap_percent):.2f}%) - "
                    f"Previous Close={futures_previous_close:.2f}, Today Open={futures_current_open:.2f} - "
                    f"Exiting position immediately"
                )
            else:
                # Gap up (favorable) OR small gap down → Continue normally
                is_adverse = False
                should_exit = False
                
        elif position_type == PositionType.SHORT:
            # SHORT position: Gap UP is adverse (bad), Gap DOWN is favorable (good)
            if gap_points > self.gap_threshold:  # Gap UP exceeds threshold
                is_adverse = True
                should_exit = True
                exit_price = futures_current_open  # Exit at futures open price
                
                self.logger.critical(
                    f"⚠️ GAP UP DETECTED (SHORT): {gap_points:.2f} points ({gap_percent:.2f}%) - "
                    f"Previous Close={futures_previous_close:.2f}, Today Open={futures_current_open:.2f} - "
                    f"Exiting position immediately"
                )
            else:
                # Gap down (favorable) OR small gap up → Continue normally
                is_adverse = False
                should_exit = False
        
        return GapResult(
            gap_points=gap_points,
            gap_percent=gap_percent,
            is_adverse=is_adverse,
            should_exit=should_exit,
            exit_price=exit_price
        )
    
    def should_exit_on_gap(
        self,
        running_candle: RunningCandle,
        futures_previous_close: float,
        position_type: PositionType
    ) -> Tuple[bool, Optional[float]]:
        """
        Simplified method: Returns (should_exit, exit_price) tuple.
        
        Args:
            running_candle: Current running candle (futures price)
            futures_previous_close: Previous day's close (futures price)
            position_type: Current position type (LONG, SHORT, or NONE)
            
        Returns:
            Tuple of (should_exit: bool, exit_price: Optional[float])
        """
        result = self.check_gap(running_candle, futures_previous_close, position_type)
        return result.should_exit, result.exit_price

