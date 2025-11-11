"""
Volume Node Detection - Based on LuxAlgo Volume Profile
Detects peak volume nodes for exit signals
"""

import numpy as np
from numba import jit
from typing import Tuple, List


@jit(nopython=True, cache=True)
def calculate_volume_profile(high: np.ndarray, low: np.ndarray, 
                             volume: np.ndarray, close: np.ndarray,
                             lookback: int, num_rows: int) -> Tuple[np.ndarray, float, float]:
    """
    Calculate volume profile for last N bars - optimized
    
    Returns: (volume_per_level, lowest_price, price_step)
    """
    n = len(close)
    start_idx = max(0, n - lookback)
    
    # Find price range
    lowest = np.min(low[start_idx:])
    highest = np.max(high[start_idx:])
    price_step = (highest - lowest) / num_rows
    
    if price_step == 0:
        return np.zeros(num_rows), lowest, 0.001
    
    # Volume distribution - optimized
    volume_profile = np.zeros(num_rows)
    
    for i in range(start_idx, n):
        bar_high = high[i]
        bar_low = low[i]
        bar_vol = volume[i]
        bar_range = bar_high - bar_low
        
        if bar_range == 0:
            level = int((bar_low - lowest) / price_step)
            level = max(0, min(level, num_rows - 1))
            volume_profile[level] += bar_vol
            continue
        
        # Calculate level range
        start_level = max(0, int((bar_low - lowest) / price_step))
        end_level = min(num_rows - 1, int((bar_high - lowest) / price_step))
        
        # Distribute volume proportionally
        for level in range(start_level, end_level + 1):
            level_low = lowest + level * price_step
            level_high = level_low + price_step
            
            overlap_low = max(bar_low, level_low)
            overlap_high = min(bar_high, level_high)
            overlap = max(0, overlap_high - overlap_low)
            
            proportion = overlap / bar_range
            volume_profile[level] += bar_vol * proportion
    
    return volume_profile, lowest, price_step


@jit(nopython=True, cache=True)
def detect_peak_nodes(volume_profile: np.ndarray, detection_percent: float,
                     threshold_percent: float) -> np.ndarray:
    """
    Detect peak volume nodes
    Peak = volume higher than N surrounding nodes
    """
    num_rows = len(volume_profile)
    peaks = np.zeros(num_rows, dtype=np.bool_)
    
    detection_window = int(num_rows * detection_percent)
    if detection_window == 0:
        return peaks
    
    max_volume = np.max(volume_profile)
    threshold = max_volume * threshold_percent
    
    for i in range(detection_window, num_rows - detection_window):
        if volume_profile[i] < threshold:
            continue
        
        # Check if peak (higher than surrounding nodes)
        is_peak = True
        for j in range(i - detection_window, i):
            if volume_profile[i] <= volume_profile[j]:
                is_peak = False
                break
        
        if is_peak:
            for j in range(i + 1, i + detection_window + 1):
                if volume_profile[i] <= volume_profile[j]:
                    is_peak = False
                    break
        
        peaks[i] = is_peak
    
    return peaks


class VolumeNodeDetector:
    """Real-time volume node detection"""
    
    def __init__(self, lookback: int = 360, num_rows: int = 100,
                 detection_percent: float = 0.09, threshold_percent: float = 0.01):
        self.lookback = lookback
        self.num_rows = num_rows
        self.detection_percent = detection_percent
        self.threshold_percent = threshold_percent
        
        self.peak_prices = []
        self.lowest_price = 0
        self.price_step = 0
    
    def update(self, high: np.ndarray, low: np.ndarray, 
               volume: np.ndarray, close: np.ndarray) -> List[float]:
        """
        Update volume profile and return peak node prices
        """
        # Calculate volume profile
        volume_profile, lowest, step = calculate_volume_profile(
            high, low, volume, close, self.lookback, self.num_rows
        )
        
        self.lowest_price = lowest
        self.price_step = step
        
        # Detect peaks
        peaks = detect_peak_nodes(
            volume_profile, self.detection_percent, self.threshold_percent
        )
        
        # Convert peak levels to prices
        peak_prices = []
        for level in range(len(peaks)):
            if peaks[level]:
                price = lowest + (level + 0.5) * step
                peak_prices.append(price)
        
        self.peak_prices = peak_prices
        return peak_prices
    
    def check_price_cross(self, current_price: float, tolerance: float = 0.5) -> bool:
        """
        Check if current price touches any peak node
        tolerance: price_step multiplier
        """
        threshold = self.price_step * tolerance
        
        for peak in self.peak_prices:
            if abs(current_price - peak) <= threshold:
                return True
        return False


# ==================== TESTING ====================

if __name__ == "__main__":
    print("Volume Node Detection Test\n" + "="*50)
    
    # Generate test data
    np.random.seed(42)
    n = 1000
    
    close = np.cumsum(np.random.randn(n) * 10) + 45000
    high = close + np.random.rand(n) * 50
    low = close - np.random.rand(n) * 50
    volume = np.random.randint(1000, 10000, n)
    
    # Detect nodes
    detector = VolumeNodeDetector(lookback=360, num_rows=100)
    peaks = detector.update(high, low, volume, close)
    
    print(f"Detected {len(peaks)} peak volume nodes:")
    for i, price in enumerate(peaks[:10]):
        print(f"  Node {i+1}: {price:.2f}")
    
    # Test price cross
    test_price = peaks[0] if len(peaks) > 0 else close[-1]
    crossed = detector.check_price_cross(test_price)
    print(f"\nPrice {test_price:.2f} crosses node: {crossed}")
    
    print("\n✅ Volume node detection ready")