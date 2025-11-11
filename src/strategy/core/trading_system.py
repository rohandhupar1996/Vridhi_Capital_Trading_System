"""
Complete Lorentzian Trading System - FIXED RE-ENTRY LOGIC
The bug was: only entered on signal CHANGES (1→0→1), not continuous signals
Now: enters on ANY valid signal when not in position
"""

import numpy as np
from numba import jit
import time
from typing import Tuple, Dict, Optional
from dataclasses import dataclass

# Import our modules
from .ml_extension import (n_rsi, n_wt, n_cci, n_adx, 
                           filter_volatility, regime_filter, filter_adx,
                           calculate_ema)
from .kernel_function import rationalQuadratic, gaussian, detect_kernel_trend
from .lorentzian_classifier import LorentzianClassifier


class PerformanceTimer:
    def __init__(self, name: str):
        self.name = name
        
    def __enter__(self):
        self.start = time.perf_counter()
        return self
        
    def __exit__(self, *args):
        self.end = time.perf_counter()
        self.elapsed = (self.end - self.start) * 1000
        print(f"⏱️  {self.name}: {self.elapsed:.3f}ms")


@dataclass
class TradingSettings:
    """Configuration for trading system"""
    # ML settings
    neighbors_count: int = 5
    max_bars_back: int = 5000
    feature_count: int = 5
    
    # Kernel settings
    use_kernel_filter: bool = True
    kernel_lookback: int = 8
    kernel_relative_weight: float = 8.0
    kernel_regression_level: int = 25
    kernel_lag: int = 2
    
    # Filter settings
    use_volatility_filter: bool = True
    use_regime_filter: bool = True
    regime_threshold: float = -0.1
    use_adx_filter: bool = False
    adx_threshold: int = 20
    
    # Re-entry settings
    enable_reentry: bool = True
    reentry_window_start: int = 3
    reentry_window_end: int = 50
    
    # Exit settings
    use_dynamic_exits: bool = False
    show_exits: bool = True
    bars_held_for_exit: int = 4


@jit(nopython=True, cache=True)
def detect_signal_changes(signals: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Detect new buy/sell signals
    Returns: (is_new_buy, is_new_sell)
    """
    n = len(signals)
    is_new_buy = np.zeros(n, dtype=np.bool_)
    is_new_sell = np.zeros(n, dtype=np.bool_)
    
    for i in range(1, n):
        if signals[i] == 1 and signals[i-1] != 1:
            is_new_buy[i] = True
        elif signals[i] == -1 and signals[i-1] != -1:
            is_new_sell[i] = True
    
    return is_new_buy, is_new_sell


@jit(nopython=True, cache=True)
def apply_reentry_logic(signals: np.ndarray, predictions: np.ndarray,
                       kernel_bullish: np.ndarray, kernel_bearish: np.ndarray,
                       filter_all: np.ndarray, reentry_start: int, 
                       reentry_end: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Apply re-entry logic to generate entry/exit signals
    ✅ FIXED: Now enters on ANY valid signal, not just signal changes
    
    Returns: (start_long, start_short, end_long, end_short)
    """
    n = len(signals)
    
    # Track positions
    in_long = False
    in_short = False
    bars_in_long = 0
    bars_in_short = 0
    
    # Entry/exit signals
    start_long = np.zeros(n, dtype=np.bool_)
    start_short = np.zeros(n, dtype=np.bool_)
    end_long = np.zeros(n, dtype=np.bool_)
    end_short = np.zeros(n, dtype=np.bool_)
    
    # Track last exit bar for re-entry window
    last_long_exit = -9999
    last_short_exit = -9999
    
    for i in range(1, n):
        # Check for exits FIRST
        if in_long:
            # Exit after 4 bars OR on opposing signal
            if bars_in_long >= 4:
                end_long[i] = True
                in_long = False
                bars_in_long = 0
                last_long_exit = i
            elif signals[i] == -1 and kernel_bearish[i] and filter_all[i]:
                end_long[i] = True  # Early flip exit
                in_long = False
                bars_in_long = 0
                last_long_exit = i
        
        if in_short:
            if bars_in_short >= 4:
                end_short[i] = True
                in_short = False
                bars_in_short = 0
                last_short_exit = i
            elif signals[i] == 1 and kernel_bullish[i] and filter_all[i]:
                end_short[i] = True
                in_short = False
                bars_in_short = 0
                last_short_exit = i
        
        # Check for new entries AFTER exits
        if not in_long and not in_short:
            # ✅ FIX: Check if signal exists AND passes all filters
            has_long_signal = signals[i] == 1 and kernel_bullish[i] and filter_all[i]
            has_short_signal = signals[i] == -1 and kernel_bearish[i] and filter_all[i]
            
            # Check re-entry window conditions
            bars_since_long_exit = i - last_long_exit
            bars_since_short_exit = i - last_short_exit
            
            # Allow entry if:
            # 1. Never traded before (bars_since_exit < 0)
            # 2. Outside re-entry window (bars_since_exit > reentry_end)
            # 3. Within re-entry window AND prediction confirms
            can_enter_long = (bars_since_long_exit < 0 or 
                             bars_since_long_exit > reentry_end or
                             (bars_since_long_exit >= reentry_start and 
                              bars_since_long_exit <= reentry_end and predictions[i] > 0))
            
            can_enter_short = (bars_since_short_exit < 0 or 
                              bars_since_short_exit > reentry_end or
                              (bars_since_short_exit >= reentry_start and 
                               bars_since_short_exit <= reentry_end and predictions[i] < 0))
            
            # Process entries
            if has_long_signal and can_enter_long:
                start_long[i] = True
                in_long = True
                bars_in_long = 0
            elif has_short_signal and can_enter_short:
                start_short[i] = True
                in_short = True
                bars_in_short = 0
        
        # Update bar counters
        if in_long:
            bars_in_long += 1
        if in_short:
            bars_in_short += 1
    
    return start_long, start_short, end_long, end_short


class LorentzianTradingSystem:
    """Complete trading system with all components"""
    
    def __init__(self, settings: TradingSettings):
        self.settings = settings
        self.classifier = LorentzianClassifier(
            neighbors_count=settings.neighbors_count,
            max_bars_back=settings.max_bars_back,
            feature_count=settings.feature_count
        )
        
        # Performance tracking
        self.timing = {}
    
    def generate_features(self, high: np.ndarray, low: np.ndarray, 
                         close: np.ndarray) -> Dict[str, np.ndarray]:
        """Generate all 5 features from OHLC data"""
        
        hlc3 = (high + low + close) / 3
        
        with PerformanceTimer("Feature Generation"):
            # Feature 1: RSI(14, 1)
            f1 = n_rsi(close, 14, 1)
            
            # Feature 2: WT(10, 11)
            f2 = n_wt(hlc3, 10, 11)
            
            # Feature 3: CCI(20, 1)
            f3 = n_cci(close, high, low, 20, 1)
            
            # Feature 4: ADX(20)
            f4 = n_adx(high, low, close, 20)
            
            # Feature 5: RSI(9, 1)
            f5 = n_rsi(close, 9, 1)
            
            # Forward-fill NaN values with 0.5 (neutral for normalized features)
            f1 = self._forward_fill(f1, fill_value=0.5)
            f2 = self._forward_fill(f2, fill_value=0.5)
            f3 = self._forward_fill(f3, fill_value=0.5)
            f4 = self._forward_fill(f4, fill_value=0.5)
            f5 = self._forward_fill(f5, fill_value=0.5)
        
        return {
            'f1': f1, 'f2': f2, 'f3': f3, 'f4': f4, 'f5': f5
        }
    
    def _forward_fill(self, arr: np.ndarray, fill_value: float = 0.5) -> np.ndarray:
        """Forward fill NaN values, use fill_value for leading NaNs"""
        result = arr.copy()
        mask = np.isnan(result)
        
        # Fill leading NaNs with neutral value
        first_valid = np.where(~mask)[0]
        if len(first_valid) > 0:
            result[:first_valid[0]] = fill_value
            
            # Forward fill remaining NaNs
            idx = np.where(~mask, np.arange(len(mask)), 0)
            np.maximum.accumulate(idx, out=idx)
            result[mask] = result[idx[mask]]
        else:
            # All NaN - fill with neutral
            result[:] = fill_value
        
        return result
    
    def apply_filters(self, high: np.ndarray, low: np.ndarray, 
                     close: np.ndarray) -> np.ndarray:
        """Apply all filters and return combined filter array"""
        
        with PerformanceTimer("Filter Application"):
            vol_filter = (filter_volatility(high, low, close, 1, 10) 
                         if self.settings.use_volatility_filter 
                         else np.ones(len(close), dtype=bool))
            
            # ✅ FIXED: Pass high, low, close to regime_filter
            reg_filter = (regime_filter(high, low, close, self.settings.regime_threshold)
                         if self.settings.use_regime_filter
                         else np.ones(len(close), dtype=bool))
            
            adx_filt = (filter_adx(high, low, close, 14, self.settings.adx_threshold)
                       if self.settings.use_adx_filter
                       else np.ones(len(close), dtype=bool))
            
            # Combined filter
            filter_all = vol_filter & reg_filter & adx_filt
        
        return filter_all
    
    def apply_kernel_filter(self, close: np.ndarray) -> Dict[str, np.ndarray]:
        """Apply kernel regression for trend detection"""
        
        if not self.settings.use_kernel_filter:
            n = len(close)
            return {
                'kernel_estimate': close,
                'is_bullish': np.ones(n, dtype=bool),
                'is_bearish': np.ones(n, dtype=bool)
            }
        
        with PerformanceTimer("Kernel Calculation"):
            # Primary kernel
            yhat1 = rationalQuadratic(
                close, 
                self.settings.kernel_lookback,
                self.settings.kernel_relative_weight,
                self.settings.kernel_regression_level
            )
            
            # Smoothing kernel with lag
            yhat2 = gaussian(
                close,
                self.settings.kernel_lookback - self.settings.kernel_lag,
                self.settings.kernel_regression_level
            )
            
            # Detect trends
            trend = detect_kernel_trend(yhat1)
        
        return {
            'kernel_estimate': yhat1,
            'is_bullish': trend['is_bullish_rate'],
            'is_bearish': trend['is_bearish_rate']
        }
    
    def generate_signals(self, high: np.ndarray, low: np.ndarray,
                        close: np.ndarray, start_bar: int = 100) -> Dict:
        """
        Complete signal generation pipeline
        
        Returns dictionary with all signals and intermediate values
        """
        n = len(close)
        
        print(f"\n{'='*60}")
        print(f"PROCESSING {n} BARS...")
        print(f"{'='*60}\n")
        
        # Step 1: Generate features
        features = self.generate_features(high, low, close)
        
        # Step 2: Apply filters
        filter_all = self.apply_filters(high, low, close)
        
        # Step 3: Apply kernel filter
        kernel_data = self.apply_kernel_filter(close)
        
        # Step 4: ML Classification
        with PerformanceTimer("ML Classification"):
            predictions, signals = self.classifier.classify_all(
                features['f1'], features['f2'], features['f3'],
                features['f4'], features['f5'], close, start_bar
            )
        
        # Step 5: Apply re-entry logic
        with PerformanceTimer("Re-entry Logic"):
            start_long, start_short, end_long, end_short = apply_reentry_logic(
                signals, predictions,
                kernel_data['is_bullish'], kernel_data['is_bearish'],
                filter_all,
                self.settings.reentry_window_start,
                self.settings.reentry_window_end
            )
        
        return {
            'predictions': predictions,
            'signals': signals,
            'start_long': start_long,
            'start_short': start_short,
            'end_long': end_long,
            'end_short': end_short,
            'filter_all': filter_all,
            'kernel_estimate': kernel_data['kernel_estimate'],
            'features': features
        }


# ==================== TESTING ====================

if __name__ == "__main__":
    print("=" * 60)
    print("COMPLETE LORENTZIAN TRADING SYSTEM TEST")
    print("=" * 60)
    
    # Generate realistic test data
    np.random.seed(42)
    n_bars = 3000
    
    # Simulate price with trend and noise
    trend = np.linspace(100, 130, n_bars)
    noise = np.cumsum(np.random.randn(n_bars) * 0.5)
    close = trend + noise
    high = close + np.random.rand(n_bars) * 2
    low = close - np.random.rand(n_bars) * 2
    
    # Create system with your settings
    settings = TradingSettings(
        neighbors_count=5,
        max_bars_back=2000,
        feature_count=5,
        use_kernel_filter=True,
        kernel_lookback=8,
        kernel_relative_weight=8.0,
        use_volatility_filter=True,
        use_regime_filter=True,
        regime_threshold=-0.1,
        enable_reentry=True,
        reentry_window_start=3,
        reentry_window_end=50
    )
    
    system = LorentzianTradingSystem(settings)
    
    # Generate signals
    results = system.generate_signals(high, low, close, start_bar=100)
    
    # Calculate statistics
    long_entries = np.sum(results['start_long'])
    short_entries = np.sum(results['start_short'])
    long_exits = np.sum(results['end_long'])
    short_exits = np.sum(results['end_short'])
    
    print(f"\n{'='*60}")
    print(f"TRADING STATISTICS")
    print(f"{'='*60}")
    print(f"\n📊 ENTRY/EXIT COUNTS:")
    print(f"  Long entries:  {long_entries}")
    print(f"  Short entries: {short_entries}")
    print(f"  Long exits:    {long_exits}")
    print(f"  Short exits:   {short_exits}")
    print(f"  Total trades:  {long_entries + short_entries}")
    
    # Show last 20 signals
    print(f"\n📈 LAST 20 SIGNALS:")
    for i in range(-20, 0):
        if results['start_long'][i]:
            print(f"  Bar {i}: 🟢 LONG ENTRY (pred={results['predictions'][i]:+.1f})")
        elif results['start_short'][i]:
            print(f"  Bar {i}: 🔴 SHORT ENTRY (pred={results['predictions'][i]:+.1f})")
        elif results['end_long'][i]:
            print(f"  Bar {i}: ✅ LONG EXIT")
        elif results['end_short'][i]:
            print(f"  Bar {i}: ✅ SHORT EXIT")
    
    print(f"\n{'='*60}")
    print("✅ SYSTEM READY FOR BACKTESTING!")
    print(f"{'='*60}\n")