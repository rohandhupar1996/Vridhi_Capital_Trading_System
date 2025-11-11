"""
Volume Profile with Node Detection
Optimized Python version of LuxAlgo script
Find nearest volume nodes for dynamic exits
"""

import numpy as np
from numba import jit
import pandas as pd


@jit(nopython=True, cache=True)
def calculate_volume_profile(high, low, volume, n_rows=100):
    """
    Calculate volume profile with Numba optimization
    
    Parameters:
    -----------
    high : ndarray
        High prices
    low : ndarray
        Low prices  
    volume : ndarray
        Volume data
    n_rows : int
        Number of price levels (rows) in profile
    
    Returns:
    --------
    volume_at_price : ndarray
        Volume at each price level
    price_levels : ndarray
        Price level for each row
    """
    n_bars = len(high)
    
    # Find price range
    highest_price = np.max(high)
    lowest_price = np.min(low)
    price_step = (highest_price - lowest_price) / n_rows
    
    # Initialize volume arrays
    volume_at_price = np.zeros(n_rows)
    price_levels = np.zeros(n_rows)
    
    # Calculate price levels
    for i in range(n_rows):
        price_levels[i] = lowest_price + (i + 0.5) * price_step
    
    # Distribute volume across price levels
    for bar_idx in range(n_bars):
        bar_high = high[bar_idx]
        bar_low = low[bar_idx]
        bar_volume = volume[bar_idx]
        
        # Find which price levels this bar touches
        start_idx = int((bar_low - lowest_price) / price_step)
        end_idx = int((bar_high - lowest_price) / price_step)
        
        # Clamp to valid range
        start_idx = max(0, min(start_idx, n_rows - 1))
        end_idx = max(0, min(end_idx, n_rows - 1))
        
        # Distribute volume proportionally
        for level_idx in range(start_idx, end_idx + 1):
            level_price = price_levels[level_idx]
            level_price_top = lowest_price + (level_idx + 1) * price_step
            level_price_bottom = lowest_price + level_idx * price_step
            
            # Calculate what proportion of this bar falls in this level
            if bar_low >= level_price_bottom and bar_high > level_price_top:
                # Bar starts in this level and extends above
                proportion = (level_price_top - bar_low) / (bar_high - bar_low)
            elif bar_high <= level_price_top and bar_low < level_price_bottom:
                # Bar ends in this level and extends below
                proportion = (bar_high - level_price_bottom) / (bar_high - bar_low)
            elif bar_low >= level_price_bottom and bar_high <= level_price_top:
                # Bar entirely within this level
                proportion = 1.0
            else:
                # Level entirely within bar
                proportion = price_step / (bar_high - bar_low)
            
            volume_at_price[level_idx] += bar_volume * proportion
    
    return volume_at_price, price_levels


@jit(nopython=True, cache=True)
def detect_volume_peaks(volume_profile, detection_percent=0.09):
    """
    Detect high-volume nodes (peaks)
    
    A peak is detected when surrounding N nodes have lower volume
    where N = len(profile) * detection_percent
    
    Parameters:
    -----------
    volume_profile : ndarray
        Volume at each price level
    detection_percent : float
        Percentage of profile length to check (0.09 = 9%)
    
    Returns:
    --------
    is_peak : ndarray (bool)
        True where peak detected
    """
    n = len(volume_profile)
    is_peak = np.zeros(n, dtype=np.bool_)
    
    window = int(n * detection_percent)
    if window < 1:
        window = 1
    
    for i in range(window, n - window):
        # Check if this point is higher than all points in window
        is_local_peak = True
        
        # Check window before
        for j in range(i - window, i):
            if volume_profile[i] <= volume_profile[j]:
                is_local_peak = False
                break
        
        if not is_local_peak:
            continue
        
        # Check window after
        for j in range(i + 1, i + window + 1):
            if volume_profile[i] <= volume_profile[j]:
                is_local_peak = False
                break
        
        is_peak[i] = is_local_peak
    
    return is_peak


@jit(nopython=True, cache=True)
def find_nearest_node_above(current_price, price_levels, volume_profile, is_peak):
    """
    Find nearest volume peak node ABOVE current price
    
    Returns:
    --------
    price : float
        Price of nearest node above (or np.inf if none)
    volume : float
        Volume at that node
    """
    n = len(price_levels)
    
    nearest_price = np.inf
    nearest_volume = 0.0
    
    for i in range(n):
        if is_peak[i] and price_levels[i] > current_price:
            if price_levels[i] < nearest_price:
                nearest_price = price_levels[i]
                nearest_volume = volume_profile[i]
    
    return nearest_price, nearest_volume


@jit(nopython=True, cache=True)
def find_nearest_node_below(current_price, price_levels, volume_profile, is_peak):
    """
    Find nearest volume peak node BELOW current price
    
    Returns:
    --------
    price : float
        Price of nearest node below (or -np.inf if none)
    volume : float
        Volume at that node
    """
    n = len(price_levels)
    
    nearest_price = -np.inf
    nearest_volume = 0.0
    
    for i in range(n):
        if is_peak[i] and price_levels[i] < current_price:
            if price_levels[i] > nearest_price:
                nearest_price = price_levels[i]
                nearest_volume = volume_profile[i]
    
    return nearest_price, nearest_volume


class VolumeNodeDetector:
    """
    Volume Profile calculator with peak/trough detection
    Optimized for real-time usage
    """
    
    def __init__(self, n_rows=100, detection_percent=0.09, lookback=360):
        """
        Initialize volume node detector
        
        Parameters:
        -----------
        n_rows : int
            Number of price levels in profile
        detection_percent : float
            Peak detection sensitivity (0.09 = 9%)
        lookback : int
            Number of bars to use for profile calculation
        """
        self.n_rows = n_rows
        self.detection_percent = detection_percent
        self.lookback = lookback
        
        # Cached results
        self.volume_profile = None
        self.price_levels = None
        self.is_peak = None
        self.poc_price = None  # Point of Control
    
    def calculate(self, df):
        """
        Calculate volume profile and detect nodes
        
        Parameters:
        -----------
        df : DataFrame
            Must have columns: high, low, volume
            Uses last 'lookback' rows
        
        Returns:
        --------
        dict with:
            - poc_price: Point of Control (highest volume)
            - nearest_resistance: Nearest node above current price
            - nearest_support: Nearest node below current price
        """
        # Get last N bars
        df_recent = df.iloc[-self.lookback:] if len(df) > self.lookback else df
        
        high = df_recent['high'].values
        low = df_recent['low'].values
        volume = df_recent['volume'].values
        current_price = df_recent['close'].iloc[-1]
        
        # Calculate volume profile
        self.volume_profile, self.price_levels = calculate_volume_profile(
            high, low, volume, self.n_rows
        )
        
        # Detect peaks
        self.is_peak = detect_volume_peaks(
            self.volume_profile,
            self.detection_percent
        )
        
        # Find POC (Point of Control = highest volume)
        poc_idx = np.argmax(self.volume_profile)
        self.poc_price = self.price_levels[poc_idx]
        
        # Find nearest nodes
        resistance_price, resistance_vol = find_nearest_node_above(
            current_price,
            self.price_levels,
            self.volume_profile,
            self.is_peak
        )
        
        support_price, support_vol = find_nearest_node_below(
            current_price,
            self.price_levels,
            self.volume_profile,
            self.is_peak
        )
        
        return {
            'poc_price': self.poc_price,
            'poc_volume': self.volume_profile[poc_idx],
            'nearest_resistance': resistance_price if resistance_price != np.inf else None,
            'nearest_support': support_price if support_price != -np.inf else None,
            'resistance_volume': resistance_vol if resistance_price != np.inf else 0,
            'support_volume': support_vol if support_price != -np.inf else 0,
            'current_price': current_price
        }
    
    def get_exit_target(self, direction, current_price):
        """
        Get exit target based on entry direction
        
        Parameters:
        -----------
        direction : int
            1 for long, -1 for short
        current_price : float
            Current market price
        
        Returns:
        --------
        float: Target exit price
        """
        if self.volume_profile is None:
            return None
        
        if direction == 1:  # Long position
            # Target = nearest resistance (node above)
            target, _ = find_nearest_node_above(
                current_price,
                self.price_levels,
                self.volume_profile,
                self.is_peak
            )
            return target if target != np.inf else None
            
        elif direction == -1:  # Short position
            # Target = nearest support (node below)
            target, _ = find_nearest_node_below(
                current_price,
                self.price_levels,
                self.volume_profile,
                self.is_peak
            )
            return target if target != -np.inf else None
        
        return None


# ==========================================
# TESTING
# ==========================================

def test_volume_nodes():
    """Test volume node detection"""
    print("="*80)
    print("🧪 TESTING VOLUME NODE DETECTION")
    print("="*80)
    
    # Load sample data
    import sqlite3
    
    db_path = "data/banknifty_data.db"
    conn = sqlite3.connect(db_path)
    
    query = """
        SELECT timestamp, open, high, low, close, volume
        FROM ohlcv
        WHERE timeframe = '15min'
        ORDER BY timestamp DESC
        LIMIT 500
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    print(f"\n📊 Loaded {len(df)} bars")
    print(f"   Price range: {df['low'].min():.2f} - {df['high'].max():.2f}")
    
    # Initialize detector
    detector = VolumeNodeDetector(n_rows=100, detection_percent=0.09, lookback=360)
    
    # Calculate
    result = detector.calculate(df)
    
    print(f"\n🎯 VOLUME PROFILE RESULTS:")
    print(f"   Current Price:      {result['current_price']:.2f}")
    print(f"   POC (Highest Vol):  {result['poc_price']:.2f} (volume: {result['poc_volume']:,.0f})")
    print(f"   Nearest Resistance: {result['nearest_resistance']:.2f if result['nearest_resistance'] else 'None'}")
    print(f"   Nearest Support:    {result['nearest_support']:.2f if result['nearest_support'] else 'None'}")
    
    # Test for Long trade
    print(f"\n📈 FOR LONG TRADE:")
    long_target = detector.get_exit_target(1, result['current_price'])
    if long_target:
        points_to_target = long_target - result['current_price']
        print(f"   Entry:  {result['current_price']:.2f}")
        print(f"   Target: {long_target:.2f} (+{points_to_target:.2f} points)")
    else:
        print(f"   ⚠️  No resistance node found above")
    
    # Test for Short trade
    print(f"\n📉 FOR SHORT TRADE:")
    short_target = detector.get_exit_target(-1, result['current_price'])
    if short_target:
        points_to_target = result['current_price'] - short_target
        print(f"   Entry:  {result['current_price']:.2f}")
        print(f"   Target: {short_target:.2f} (+{points_to_target:.2f} points)")
    else:
        print(f"   ⚠️  No support node found below")
    
    print("\n✅ Test complete!")


if __name__ == "__main__":
    test_volume_nodes()