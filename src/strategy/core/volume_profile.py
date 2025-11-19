"""
Volume Profile with Node Detection - Optimized with Numba JIT
Implements LuxAlgo volume profile algorithm for dynamic exit strategies

Based on: LuxAlgo Volume Profile with Node Detection [LuxAlgo]
License: Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)
"""

from __future__ import annotations

import numpy as np
from numba import jit
from typing import Dict, List, Tuple
import pandas as pd


@jit(nopython=True, cache=True, fastmath=True, parallel=False)
def _compute_volume_profile_numba(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    open: np.ndarray,
    volume: np.ndarray,
    lookback: int,
    num_rows: int,
    value_area_threshold: float,
    peak_percent: float,
    trough_percent: float,
    threshold: float,
    top_n: int,
    bottom_n: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, 
           float, float, float, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Numba-optimized volume profile computation.
    
    Returns:
        (total_volume, bullish_volume, bearish_volume, peaks, troughs,
         high_volume_nodes, low_volume_nodes, poc_price, vah_price, val_price,
         price_levels, peak_indices, trough_indices)
    """
    # Use last lookback bars
    n_bars = len(high)
    start_idx = max(0, n_bars - lookback)
    
    # Find price range
    price_high = np.max(high[start_idx:])
    price_low = np.min(low[start_idx:])
    
    if price_high <= price_low:
        # Edge case: all prices same
        price_high = price_low + 1.0
    
    price_step = (price_high - price_low) / num_rows
    
    # Initialize volume bins
    volume_bins = np.zeros(num_rows)
    bullish_bins = np.zeros(num_rows)
    
    # Distribute volume across price levels
    for bar_idx in range(start_idx, n_bars):
        bar_high = high[bar_idx]
        bar_low = low[bar_idx]
        bar_volume = volume[bar_idx]
        is_bullish = close[bar_idx] > open[bar_idx]
        
        # Calculate which price levels this bar touches
        start_level = int(max((bar_low - price_low) / price_step, 0))
        end_level = int(min((bar_high - price_low) / price_step, num_rows - 1))
        
        # Distribute volume proportionally
        for level_idx in range(start_level, end_level + 1):
            price_level_low = price_low + level_idx * price_step
            price_level_high = price_level_low + price_step
            
            # Calculate volume proportion for this level
            if bar_high != bar_low:
                if bar_low >= price_level_low and bar_high > price_level_high:
                    vol_ratio = (price_level_high - bar_low) / (bar_high - bar_low)
                elif bar_high <= price_level_high and bar_low < price_level_low:
                    vol_ratio = (bar_high - price_level_low) / (bar_high - bar_low)
                elif bar_low >= price_level_low and bar_high <= price_level_high:
                    vol_ratio = 1.0
                else:
                    vol_ratio = price_step / (bar_high - bar_low)
            else:
                vol_ratio = 1.0
            
            volume_bins[level_idx] += bar_volume * vol_ratio
            if is_bullish:
                bullish_bins[level_idx] += bar_volume * vol_ratio
    
    # Calculate bearish volume
    bearish_bins = volume_bins - bullish_bins
    
    # Point of Control (POC)
    poc_index = np.argmax(volume_bins)
    poc_price = price_low + (poc_index + 0.5) * price_step
    
    # Value Area calculation
    total_volume = np.sum(volume_bins)
    target_volume = total_volume * value_area_threshold
    current_volume = volume_bins[poc_index]
    vah_index = poc_index
    val_index = poc_index
    
    while current_volume < target_volume:
        above = volume_bins[vah_index + 1] if vah_index + 1 < num_rows else 0.0
        below = volume_bins[val_index - 1] if val_index - 1 >= 0 else 0.0
        
        if above >= below:
            vah_index += 1
            current_volume += above
        else:
            val_index -= 1
            current_volume += below
        
        if vah_index == num_rows - 1 and val_index == 0:
            break
    
    vah_price = price_low + (vah_index + 1) * price_step
    val_price = price_low + val_index * price_step
    
    # Peak detection
    peaks = np.zeros(num_rows, dtype=np.bool_)
    peak_n = max(1, int(num_rows * peak_percent))
    volume_threshold = np.max(volume_bins) * threshold
    
    for i in range(peak_n, num_rows - peak_n):
        center = volume_bins[i]
        if center < volume_threshold:
            continue
        
        # Check if center is higher than all left nodes
        is_peak = True
        for j in range(i - peak_n, i):
            if volume_bins[j] >= center:
                is_peak = False
                break
        
        if not is_peak:
            continue
        
        # Check if center is higher than all right nodes
        for j in range(i + 1, i + 1 + peak_n):
            if volume_bins[j] >= center:
                is_peak = False
                break
        
        if is_peak:
            peaks[i] = True
    
    # Trough detection
    troughs = np.zeros(num_rows, dtype=np.bool_)
    trough_n = max(1, int(num_rows * trough_percent))
    
    for i in range(trough_n, num_rows - trough_n):
        center = volume_bins[i]
        if center < volume_threshold:
            continue
        
        # Check if center is lower than all left nodes
        is_trough = True
        for j in range(i - trough_n, i):
            if volume_bins[j] <= center:
                is_trough = False
                break
        
        if not is_trough:
            continue
        
        # Check if center is lower than all right nodes
        for j in range(i + 1, i + 1 + trough_n):
            if volume_bins[j] <= center:
                is_trough = False
                break
        
        if is_trough:
            troughs[i] = True
    
    # High/Low volume nodes
    sorted_indices = np.argsort(volume_bins)[::-1]  # Descending
    high_volume_nodes = sorted_indices[:top_n]
    low_volume_nodes = sorted_indices[::-1][:bottom_n]
    
    # Price levels
    price_levels = np.array([price_low + (i + 0.5) * price_step for i in range(num_rows)])
    
    # Convert peaks/troughs to indices
    peak_indices = np.where(peaks)[0]
    trough_indices = np.where(troughs)[0]
    
    return (volume_bins, bullish_bins, bearish_bins, peaks, troughs,
            high_volume_nodes, low_volume_nodes, poc_price, vah_price, val_price,
            price_levels, peak_indices, trough_indices)


def compute_volume_profile_full(
    df: pd.DataFrame,
    lookback: int = 360,
    num_rows: int = 100,
    value_area_threshold: float = 0.7,
    peak_percent: float = 0.09,   # 9% -> node size for peaks
    trough_percent: float = 0.07, # 7% -> node size for troughs
    threshold: float = 0.01,      # Ignore volume nodes < 1% of max
    top_n: int = 3,
    bottom_n: int = 3,
) -> Dict:
    """
    Compute volume profile with node detection (optimized with Numba JIT).
    
    Args:
        df: DataFrame with columns ['high', 'low', 'close', 'open', 'volume']
        lookback: Number of bars to look back (default: 360)
        num_rows: Number of price levels in profile (default: 100)
        value_area_threshold: Percentage of volume in value area (default: 0.7 = 70%)
        peak_percent: Node size for peak detection as % of total rows (default: 0.09 = 9%)
        trough_percent: Node size for trough detection as % of total rows (default: 0.07 = 7%)
        threshold: Ignore nodes below this % of max volume (default: 0.01 = 1%)
        top_n: Number of highest volume nodes to return (default: 3)
        bottom_n: Number of lowest volume nodes to return (default: 3)
    
    Returns:
        Dictionary with:
        - 'price_levels': List of price levels
        - 'total_volume': List of total volume per price level
        - 'bullish_volume': List of bullish volume per price level
        - 'bearish_volume': List of bearish volume per price level
        - 'poc_price': Point of Control price
        - 'vah_price': Value Area High price
        - 'val_price': Value Area Low price
        - 'peaks': Boolean list indicating peak nodes
        - 'troughs': Boolean list indicating trough nodes
        - 'high_volume_nodes': List of indices for top N highest volume nodes
        - 'low_volume_nodes': List of indices for top N lowest volume nodes
    """
    # Extract numpy arrays from DataFrame (last lookback bars)
    # Optimize: if DataFrame is already sliced to lookback size, use directly
    if len(df) <= lookback:
        df_subset = df
    else:
        df_subset = df.iloc[-lookback:]
    
    high_arr = df_subset['high'].values.astype(np.float64)
    low_arr = df_subset['low'].values.astype(np.float64)
    close_arr = df_subset['close'].values.astype(np.float64)
    open_arr = df_subset['open'].values.astype(np.float64)
    volume_arr = df_subset['volume'].values.astype(np.float64)
    
    # Call numba-optimized function
    (volume_bins, bullish_bins, bearish_bins, peaks, troughs,
     high_volume_nodes, low_volume_nodes, poc_price, vah_price, val_price,
     price_levels, peak_indices, trough_indices) = _compute_volume_profile_numba(
        high_arr, low_arr, close_arr, open_arr, volume_arr,
        lookback, num_rows, value_area_threshold,
        peak_percent, trough_percent, threshold, top_n, bottom_n
    )
    
    # Build result dictionary (can't do dict operations in numba nopython mode)
    return {
        'price_levels': price_levels.tolist(),
        'total_volume': volume_bins.tolist(),
        'bullish_volume': bullish_bins.tolist(),
        'bearish_volume': bearish_bins.tolist(),
        'poc_price': float(poc_price),
        'vah_price': float(vah_price),
        'val_price': float(val_price),
        'peaks': peaks.tolist(),
        'troughs': troughs.tolist(),
        'high_volume_nodes': high_volume_nodes.tolist(),
        'low_volume_nodes': low_volume_nodes.tolist(),
        'peak_indices': peak_indices.tolist(),
        'trough_indices': trough_indices.tolist(),
    }


# ==================== TESTING ====================

if __name__ == "__main__":
    import time
    
    # Create sample data
    np.random.seed(42)
    n_bars = 6000
    
    df = pd.DataFrame({
        'high': 59000 + np.random.randn(n_bars) * 200 + np.cumsum(np.random.randn(n_bars) * 10),
        'low': 59000 + np.random.randn(n_bars) * 200 + np.cumsum(np.random.randn(n_bars) * 10) - 50,
        'close': 59000 + np.random.randn(n_bars) * 200 + np.cumsum(np.random.randn(n_bars) * 10),
        'open': 59000 + np.random.randn(n_bars) * 200 + np.cumsum(np.random.randn(n_bars) * 10) - 10,
        'volume': np.abs(np.random.randn(n_bars) * 1000000) + 500000,
    })
    
    # Ensure high >= low, close/open within range
    df['high'] = np.maximum(df['high'], df[['open', 'close']].max(axis=1))
    df['low'] = np.minimum(df['low'], df[['open', 'close']].min(axis=1))
    
    print("="*70)
    print("VOLUME PROFILE - NUMBA OPTIMIZED")
    print("="*70)
    
    # Warmup run (compile numba)
    print("\n⏳ Compiling Numba JIT (first run)...")
    _ = compute_volume_profile_full(df.iloc[:100], lookback=100)
    
    # Benchmark
    print("\n⏱️  Benchmarking with 6000 bars, 360 lookback...")
    start = time.perf_counter()
    result = compute_volume_profile_full(df, lookback=360)
    elapsed = (time.perf_counter() - start) * 1000
    
    print(f"\n✅ Volume profile computed in {elapsed:.2f}ms")
    print(f"\n📊 Results:")
    print(f"  POC Price:      {result['poc_price']:.2f}")
    print(f"  VAH Price:      {result['vah_price']:.2f}")
    print(f"  VAL Price:      {result['val_price']:.2f}")
    print(f"  Peaks found:    {sum(result['peaks'])}")
    print(f"  Troughs found:  {sum(result['troughs'])}")
    print(f"  High vol nodes: {len(result['high_volume_nodes'])}")
    print(f"  Low vol nodes:  {len(result['low_volume_nodes'])}")
    
    # Compare with non-numba version (if needed for validation)
    print("\n✅ Numba optimization active - all computation in compiled code")

