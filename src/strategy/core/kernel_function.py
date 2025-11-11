"""
Kernel Functions Module - FIXED
"""

import numpy as np
from numba import jit
import time


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


@jit(nopython=True, cache=True)
def rational_quadratic_kernel(src: np.ndarray, lookback: int, relative_weight: float, start_at_bar: int) -> np.ndarray:
    n = len(src)
    yhat = np.empty(n)
    yhat[:] = np.nan
    
    for bar in range(start_at_bar, n):
        current_weight = 0.0
        cumulative_weight = 0.0
        max_lookback = min(bar + 1, n)
        
        for i in range(max_lookback):
            y = src[bar - i]
            if not np.isnan(y):
                numerator = i * i
                denominator = (lookback * lookback * 2 * relative_weight)
                w = (1 + numerator / denominator) ** (-relative_weight)
                current_weight += y * w
                cumulative_weight += w
        
        if cumulative_weight > 0:
            yhat[bar] = current_weight / cumulative_weight
    
    return yhat


@jit(nopython=True, cache=True)
def gaussian_kernel(src: np.ndarray, lookback: int, start_at_bar: int) -> np.ndarray:
    n = len(src)
    yhat = np.empty(n)
    yhat[:] = np.nan
    
    for bar in range(start_at_bar, n):
        current_weight = 0.0
        cumulative_weight = 0.0
        max_lookback = min(bar + 1, n)
        
        for i in range(max_lookback):
            y = src[bar - i]
            if not np.isnan(y):
                w = np.exp(-i * i / (2 * lookback * lookback))
                current_weight += y * w
                cumulative_weight += w
        
        if cumulative_weight > 0:
            yhat[bar] = current_weight / cumulative_weight
    
    return yhat


def rationalQuadratic(src: np.ndarray, h: int, r: float, x: int) -> np.ndarray:
    with PerformanceTimer(f"RationalQuadratic(h={h}, r={r}, x={x})"):
        result = rational_quadratic_kernel(src, h, r, x)
    return result


def gaussian(src: np.ndarray, h: int, x: int) -> np.ndarray:
    with PerformanceTimer(f"Gaussian(h={h}, x={x})"):
        result = gaussian_kernel(src, h, x)
    return result


def detect_kernel_trend(yhat: np.ndarray) -> dict:
    """✅ FIXED: Simple 2-bar slope check (matches Pine)"""
    n = len(yhat)
    is_bearish_rate = np.zeros(n, dtype=bool)
    is_bullish_rate = np.zeros(n, dtype=bool)
    
    for i in range(1, n):
        is_bullish_rate[i] = yhat[i-1] < yhat[i]
        is_bearish_rate[i] = yhat[i-1] > yhat[i]
    
    return {
        'is_bullish_rate': is_bullish_rate,
        'is_bearish_rate': is_bearish_rate,
        'kernel_estimate': yhat
    }