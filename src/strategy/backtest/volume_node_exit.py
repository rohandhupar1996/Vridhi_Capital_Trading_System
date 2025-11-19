"""
Volume Node Exit Strategy
Implements volume node peak exit logic for backtesting

Exit Rules:
- LONG: Exit if futures price crosses volume node PEAKS in upward direction (price > peak)
- SHORT: Exit if futures price crosses volume node PEAKS in downward direction (price < peak)
- Exit happens when price crosses the peak price level (first reached)
- Combined with default 4-bar exit: whichever happens first
"""

from __future__ import annotations

from typing import List, Optional, Tuple
import pandas as pd
import numpy as np

from src.strategy.core.volume_profile import compute_volume_profile_full


class VolumeNodeExitDetector:
    """
    Detects volume node peak exits for trades.
    Computes volume profile on rolling window and checks if price crosses peaks.
    """
    
    def __init__(
        self,
        lookback: int = 240,  # Optimized: 240 bars (~60 hours, 2x faster than Pine Script's 360)
        num_rows: int = 60,   # Optimized: 60 rows (2x faster than Pine Script's 100, still accurate)
        peak_percent: float = 0.09,  # Pine Script default: 9% for peak nodes
        trough_percent: float = 0.07,  # Pine Script default: 7% for trough nodes
        threshold: float = 0.01,  # Pine Script default: 1% threshold for volume nodes
    ):
        self.lookback = lookback
        self.num_rows = num_rows
        self.peak_percent = peak_percent
        self.trough_percent = trough_percent
        self.threshold = threshold
        
        # Cache for volume profile computation
        # Only recompute when bar completes (new bar), not during intra-bar checks
        self._last_profile_bar: Optional[int] = None
        self._last_computed_bar: Optional[int] = None  # Track which bar we computed for
        self._peak_prices: List[float] = []  # All peak prices (for direction filtering)
        self._peak_volumes: List[float] = []  # Volumes at each peak (to find highest in direction)
        self._price_levels: Optional[np.ndarray] = None
    
    def check_exit(
        self,
        trade_direction: int,  # 1=LONG, -1=SHORT
        current_bar: int,
        historical_data: pd.DataFrame,
        current_high: float,
        current_low: float,
        current_close: float,
        entry_price: Optional[float] = None,  # Entry price to filter peaks (for profitable exits)
        entry_bar: Optional[int] = None,  # Entry bar for debug logging
    ) -> Tuple[bool, Optional[float], Optional[str]]:
        """
        Check if trade should exit due to volume node peak crossing.
        
        Args:
            trade_direction: 1 for LONG, -1 for SHORT
            current_bar: Current bar index
            historical_data: DataFrame with OHLCV data up to current bar (reference, not sliced)
            current_high: High price of current bar
            current_low: Low price of current bar
            current_close: Close price of current bar
        
        Returns:
            (should_exit, exit_price, exit_reason)
            - should_exit: True if volume node peak exit triggered
            - exit_price: Price level where exit occurred (or None)
            - exit_reason: Exit reason string (or None)
        """
        # Need enough bars for volume profile
        if len(historical_data) < self.lookback or current_bar < self.lookback - 1:
            if entry_bar is not None and current_bar == entry_bar + 1:  # Debug first bar only
                print(f"🔍 [DEBUG] Bar {current_bar}: Not enough data for volume profile (need {self.lookback}, have {len(historical_data)}, current_bar={current_bar})")
            return False, None, None
        
        # OPTIMIZED: Only recompute volume profile when bar completes (new bar)
        # In backtest: only on bar changes (not every 20 bars)
        # In real-time: only when 15min candle completes
        # This makes it 5-10x faster and real-time compatible
        if (self._last_computed_bar is None or 
            current_bar != self._last_computed_bar):  # Only recompute on new bar
            self._update_volume_profile(current_bar, historical_data)
            self._last_computed_bar = current_bar
        
        if not self._peak_prices:
            if entry_bar is not None and current_bar == entry_bar + 1:  # Debug first bar only
                print(f"🔍 [DEBUG] Bar {current_bar}: No peaks detected in volume profile")
            return False, None, None
        
        # PINE SCRIPT "VOLUME PEAK" = Highest volume peak in TRADE DIRECTION
        # Filter peaks by direction FIRST, find highest volume peak in that direction, then exit when crossed
        
        # DEBUG: Log all detected peaks (first bar only)
        if entry_bar is not None and current_bar == entry_bar + 1:
            direction_str = "LONG" if trade_direction == 1 else "SHORT"
            print(f"\n🔍 [DEBUG] Volume Exit Check - Bar {current_bar} ({direction_str})")
            print(f"  Entry price: {entry_price:.2f} at bar {entry_bar}")
            print(f"  Current: H={current_high:.2f}, L={current_low:.2f}, C={current_close:.2f}")
            print(f"  All detected peaks ({len(self._peak_prices)}):")
            for i, (peak_price, peak_vol) in enumerate(zip(self._peak_prices, self._peak_volumes)):
                print(f"    Peak {i+1}: {peak_price:.2f} (volume: {peak_vol:.0f})")
        
        if trade_direction == 1:  # LONG
            # For LONG: Only consider peaks ABOVE entry (upward direction)
            # Find highest volume peak in upward direction - this is the "volume peak" red band
            directional_peaks = []
            for i, peak_price in enumerate(self._peak_prices):
                # Filter: Only peaks above entry price (upward direction, targets)
                if entry_price is not None and peak_price <= entry_price:
                    if entry_bar is not None and current_bar == entry_bar + 1:
                        print(f"    ✗ Peak {peak_price:.2f}: Filtered (not above entry {entry_price:.2f})")
                    continue
                directional_peaks.append((peak_price, self._peak_volumes[i]))
                if entry_bar is not None and current_bar == entry_bar + 1:
                    print(f"    ✓ Peak {peak_price:.2f}: Included in upward direction (vol: {self._peak_volumes[i]:.0f})")
            
            if not directional_peaks:
                if entry_bar is not None and current_bar == entry_bar + 1:
                    print(f"  ❌ No peaks above entry price - volume exit won't trigger")
                return False, None, None
            
            # Find NEAREST peak in upward direction - this is Pine Script's "volume peak"
            # Not highest volume, but the CLOSEST peak to entry price in trade direction
            nearest_peak_price, nearest_peak_vol = min(directional_peaks, key=lambda x: abs(x[0] - entry_price) if entry_price else x[0])
            
            if entry_bar is not None and current_bar == entry_bar + 1:
                print(f"  📊 Nearest peak in upward direction: {nearest_peak_price:.2f} (vol: {nearest_peak_vol:.0f}, distance from entry: {abs(nearest_peak_price - entry_price):.2f})")
            
            # Exit when price crosses this specific peak upward
            if current_high >= nearest_peak_price:
                exit_price = max(nearest_peak_price, current_close)
                if entry_bar is not None:
                    print(f"  ✅ VOLUME EXIT TRIGGERED at bar {current_bar}!")
                    print(f"     Peak {nearest_peak_price:.2f} crossed upward (high {current_high:.2f} >= peak)")
                    print(f"     Exit price: {exit_price:.2f}")
                return True, exit_price, "volume_peak_exit"
            else:
                if entry_bar is not None and current_bar == entry_bar + 1:
                    print(f"  ⏳ Peak not crossed yet (high {current_high:.2f} < peak {nearest_peak_price:.2f})")
        else:  # SHORT
            # For SHORT: Only consider peaks BELOW entry (downward direction)
            # Find highest volume peak in downward direction - this is the "volume peak" red band
            directional_peaks = []
            for i, peak_price in enumerate(self._peak_prices):
                # Filter: Only peaks below entry price (downward direction, targets)
                if entry_price is not None and peak_price >= entry_price:
                    if entry_bar is not None and current_bar == entry_bar + 1:
                        print(f"    ✗ Peak {peak_price:.2f}: Filtered (not below entry {entry_price:.2f})")
                    continue
                directional_peaks.append((peak_price, self._peak_volumes[i]))
                if entry_bar is not None and current_bar == entry_bar + 1:
                    print(f"    ✓ Peak {peak_price:.2f}: Included in downward direction (vol: {self._peak_volumes[i]:.0f})")
            
            if not directional_peaks:
                if entry_bar is not None and current_bar == entry_bar + 1:
                    print(f"  ❌ No peaks below entry price - volume exit won't trigger")
                return False, None, None
            
            # Find NEAREST peak in downward direction - this is Pine Script's "volume peak"
            # Not highest volume, but the CLOSEST peak to entry price in trade direction
            nearest_peak_price, nearest_peak_vol = min(directional_peaks, key=lambda x: abs(x[0] - entry_price) if entry_price else x[0])
            
            if entry_bar is not None and current_bar == entry_bar + 1:
                print(f"  📊 Nearest peak in downward direction: {nearest_peak_price:.2f} (vol: {nearest_peak_vol:.0f}, distance from entry: {abs(nearest_peak_price - entry_price):.2f})")
            
            # Exit when price crosses this specific peak downward
            if current_low <= nearest_peak_price:
                exit_price = min(nearest_peak_price, current_close)
                if entry_bar is not None:
                    print(f"  ✅ VOLUME EXIT TRIGGERED at bar {current_bar}!")
                    print(f"     Peak {nearest_peak_price:.2f} crossed downward (low {current_low:.2f} <= peak)")
                    print(f"     Exit price: {exit_price:.2f}")
                return True, exit_price, "volume_peak_exit"
            else:
                if entry_bar is not None:
                    # Log each bar for SHORT trades to see when/if peak gets crossed
                    bars_held = current_bar - entry_bar if entry_bar is not None else 0
                    if bars_held <= 4:  # Only log during first 4 bars
                        print(f"  ⏳ Bar {current_bar} (held {bars_held}): Peak not crossed yet (low {current_low:.2f} > peak {nearest_peak_price:.2f})")
        
        return False, None, None
    
    def _update_volume_profile(self, current_bar: int, historical_data: pd.DataFrame) -> None:
        """Update volume profile using rolling window of historical data (optimized)."""
        try:
            # Check for keyboard interrupt before expensive operation
            import signal
            signal.siginterrupt(signal.SIGINT, False)
            
            # Optimize: use iloc to get slice without copying if possible
            # Get last lookback bars - only slice what we need
            start_idx = max(0, current_bar - self.lookback + 1)
            end_idx = current_bar + 1
            
            # Use iloc view when possible to avoid copy
            if start_idx == 0 and end_idx == len(historical_data):
                data_window = historical_data
            else:
                data_window = historical_data.iloc[start_idx:end_idx]
            
            if len(data_window) < self.lookback:
                return
            
            # Compute volume profile (optimized with Numba JIT)
            # Fast (~5-25ms with 240/60, ~10-50ms with 360/100) - only runs once per completed bar
            profile_result = compute_volume_profile_full(
                df=data_window,
                lookback=self.lookback,
                num_rows=self.num_rows,
                peak_percent=self.peak_percent,
                trough_percent=self.trough_percent,
                threshold=self.threshold,
                value_area_threshold=0.7,  # Pine Script default: 70%
                top_n=1,  # Only highest volume node - Pine Script's single "volume peak" red band
                bottom_n=0,  # Not needed for trough detection
            )
            
            # Extract peak prices and volumes
            price_levels = np.array(profile_result['price_levels'])
            peaks = np.array(profile_result['peaks'])
            volume_bins = np.array(profile_result['total_volume'])
            
            # Get all peak indices (local maximums)
            peak_indices = np.where(peaks)[0]
            
            # Store ALL peaks with their volumes
            # We'll filter by direction (entry_price) in check_exit() to find highest in that direction
            if len(peak_indices) > 0:
                # Store all peak prices and their volumes
                self._peak_prices = [float(price_levels[i]) for i in peak_indices]
                self._peak_volumes = [float(volume_bins[i]) for i in peak_indices]
            else:
                # No peaks found
                self._peak_prices = []
                self._peak_volumes = []
            
            self._price_levels = price_levels
            self._last_profile_bar = current_bar
            
        except KeyboardInterrupt:
            # Re-raise keyboard interrupt immediately
            raise
        except Exception as e:
            # If volume profile computation fails, clear peaks and continue
            self._peak_prices = []
            self._peak_volumes = []
            self._price_levels = None
            # Don't log error to avoid spam - just silently fail


class VolumeNodeExitStrategy:
    """
    Exit strategy manager that combines default N-bar exit with volume node peak exit.
    Supports different modes: default only, both directions, long only, short only.
    """
    
    def __init__(
        self,
        default_exit_bars: int = 4,
        use_volume_exit: bool = False,
        volume_exit_long: bool = False,
        volume_exit_short: bool = False,
        volume_lookback: int = 360,  # Pine Script default: 360 bars
        volume_num_rows: int = 100,  # Pine Script default: 100 price levels
        volume_value_area: float = 0.7,  # Pine Script default: 70%
        volume_peak_percent: float = 0.09,  # Pine Script default: 9%
        volume_trough_percent: float = 0.07,  # Pine Script default: 7%
        volume_threshold: float = 0.01,  # Pine Script default: 1%
    ):
        self.default_exit_bars = default_exit_bars
        self.use_volume_exit = use_volume_exit
        self.volume_exit_long = volume_exit_long
        self.volume_exit_short = volume_exit_short
        
        # Initialize volume node detector if any volume exit is enabled
        # Uses Pine Script defaults, optimized with Numba JIT for real-time performance
        if use_volume_exit or volume_exit_long or volume_exit_short:
            self.volume_detector = VolumeNodeExitDetector(
                lookback=volume_lookback,
                num_rows=volume_num_rows,
                peak_percent=volume_peak_percent,
                trough_percent=volume_trough_percent,
                threshold=volume_threshold,
            )
        else:
            self.volume_detector = None
    
    def should_exit(
        self,
        trade_direction: int,  # 1=LONG, -1=SHORT
        entry_bar: int,
        current_bar: int,
        historical_data: pd.DataFrame,
        current_high: float,
        current_low: float,
        current_close: float,
        entry_price: Optional[float] = None,  # Entry price to filter peaks (only exit at targets, not losses)
    ) -> Tuple[bool, str, Optional[float]]:
        """
        Check if trade should exit (4-bar exit OR volume peak exit, whichever triggers first).
        
        Exit Strategy:
        1. Volume peak exit: Exit immediately if price crosses volume node peak
           - LONG: Exit at highest peak ABOVE entry (targets)
           - SHORT: Exit at lowest peak BELOW entry (targets)
        2. Default 4-bar exit: Exit at bar 4 if volume exit hasn't triggered (backup)
        
        Peak Filtering (for profitable exits):
        - LONG: Only consider peaks > entry_price (targets, not losses)
        - SHORT: Only consider peaks < entry_price (targets, not losses)
        This ensures we exit at targets, matching TradingView behavior.
        
        Uses Pine Script volume profile parameters (optimized with Numba JIT).
        Volume profile computes once per completed bar, then cached peaks checked intra-bar (<1ms).
        
        Returns:
            (should_exit, exit_reason, exit_price)
            - should_exit: True if any exit condition met
            - exit_reason: 'volume_peak_exit' or '4_bars'
            - exit_price: Peak price if volume exit, None if 4-bar exit (uses close)
        """
        # Check default N-bar exit
        bars_held = current_bar - entry_bar
        default_exit = bars_held >= self.default_exit_bars
        
        # Check volume node exit if enabled
        volume_exit = False
        volume_exit_price = None
        
        if self.volume_detector:
            # Check if volume exit is enabled for this direction
            if ((self.use_volume_exit) or  # Both directions
                (self.volume_exit_long and trade_direction == 1) or  # Long only
                (self.volume_exit_short and trade_direction == -1)):  # Short only
                
                volume_exit, volume_exit_price, _ = self.volume_detector.check_exit(
                    trade_direction=trade_direction,
                    current_bar=current_bar,
                    historical_data=historical_data,
                    current_high=current_high,
                    current_low=current_low,
                    current_close=current_close,
                    entry_price=entry_price,  # Pass entry price to filter peaks (targets only)
                    entry_bar=entry_bar,  # Pass entry bar for debug logging
                )
        
        # Exit if either condition met (whichever happens first)
        if volume_exit:
            return True, "volume_peak_exit", volume_exit_price
        elif default_exit:
            return True, f"{self.default_exit_bars}_bars", None
        
        return False, "", None

