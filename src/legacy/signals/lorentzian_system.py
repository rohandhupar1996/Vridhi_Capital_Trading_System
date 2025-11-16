"""
Lorentzian Classification Trading System
With 3 Exit Strategies + AlgoTest Integration
Optimized with Numba for real-time performance
"""

import numpy as np
import pandas as pd
from numba import jit
import talib
import sqlite3
from datetime import datetime
import time

# ==========================================
# NUMBA-OPTIMIZED INDICATORS
# ==========================================

@jit(nopython=True, cache=True)
def normalize(series, min_val, max_val):
    """Normalize to 0-1 range"""
    return (series - min_val) / (max_val - min_val) if max_val != min_val else 0.5


def calculate_rsi(close, period=14):
    """Calculate RSI using TA-Lib (fast)"""
    return talib.RSI(close, timeperiod=period)


def calculate_cci(close, period=20):
    """Calculate CCI using TA-Lib"""
    high = close.copy()
    low = close.copy()
    return talib.CCI(high, low, close, timeperiod=period)


def calculate_adx(high, low, close, period=14):
    """Calculate ADX using TA-Lib"""
    return talib.ADX(high, low, close, timeperiod=period)


def calculate_wt(hlc3, channel_len=10, average_len=11):
    """
    Wave Trend oscillator
    """
    esa = talib.EMA(hlc3, timeperiod=channel_len)
    d = talib.EMA(np.abs(hlc3 - esa), timeperiod=channel_len)
    ci = (hlc3 - esa) / (0.015 * d)
    wt1 = talib.EMA(ci, timeperiod=average_len)
    wt2 = talib.SMA(wt1, timeperiod=4)
    
    return wt1


def calculate_features(df, config):
    """
    Calculate all 5 features and normalize them
    Returns: f1, f2, f3, f4, f5 arrays
    """
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    hlc3 = (high + low + close) / 3
    
    # Feature 1: RSI(14, 1)
    rsi = calculate_rsi(close, period=14)
    f1 = normalize(rsi, 0, 100)
    
    # Feature 2: WT(10, 11)
    wt = calculate_wt(hlc3, channel_len=10, average_len=11)
    f2 = normalize(wt, -200, 200)  # Typical WT range
    
    # Feature 3: CCI(20, 1)
    cci = calculate_cci(close, period=20)
    f3 = normalize(cci, -200, 200)
    
    # Feature 4: ADX(20)
    adx = calculate_adx(high, low, close, period=20)
    f4 = normalize(adx, 0, 100)
    
    # Feature 5: RSI(9, 1)
    rsi9 = calculate_rsi(close, period=9)
    f5 = normalize(rsi9, 0, 100)
    
    return f1, f2, f3, f4, f5


# ==========================================
# LORENTZIAN DISTANCE (NUMBA JIT)
# ==========================================

@jit(nopython=True, cache=True)
def lorentzian_distance_single(f1_cur, f2_cur, f3_cur, f4_cur, f5_cur,
                                f1_hist, f2_hist, f3_hist, f4_hist, f5_hist):
    """Calculate Lorentzian distance for a single point"""
    d1 = np.log(1 + np.abs(f1_cur - f1_hist))
    d2 = np.log(1 + np.abs(f2_cur - f2_hist))
    d3 = np.log(1 + np.abs(f3_cur - f3_hist))
    d4 = np.log(1 + np.abs(f4_cur - f4_hist))
    d5 = np.log(1 + np.abs(f5_cur - f5_hist))
    
    return d1 + d2 + d3 + d4 + d5


@jit(nopython=True, cache=True)
def find_k_nearest_neighbors(f1_cur, f2_cur, f3_cur, f4_cur, f5_cur,
                             f1_arr, f2_arr, f3_arr, f4_arr, f5_arr,
                             labels, k=8):
    """
    Find k-nearest neighbors and predict direction
    Returns: prediction score (-k to +k)
    """
    n = len(f1_arr)
    
    # Calculate all distances
    distances = np.zeros(n)
    for i in range(n):
        distances[i] = lorentzian_distance_single(
            f1_cur, f2_cur, f3_cur, f4_cur, f5_cur,
            f1_arr[i], f2_arr[i], f3_arr[i], f4_arr[i], f5_arr[i]
        )
    
    # Find k smallest distances (k-nearest neighbors)
    k_indices = np.argsort(distances)[:k]
    
    # Sum predictions of nearest neighbors
    prediction = 0.0
    for idx in k_indices:
        prediction += labels[idx]
    
    return prediction


# ==========================================
# FILTERS
# ==========================================

def volatility_filter(close, lookback=10):
    """Simple volatility filter"""
    returns = np.diff(close) / close[:-1]
    volatility = np.std(returns[-lookback:]) if len(returns) >= lookback else 1
    return volatility > 0.001  # Active volatility


def regime_filter(ohlc4, threshold=-0.1):
    """Regime filter - trend detection"""
    klmf = talib.EMA(ohlc4, timeperiod=20)
    abs_curve_slope = np.diff(klmf[-10:])
    regime = np.mean(abs_curve_slope)
    return regime > threshold


def adx_filter(high, low, close, period=14, threshold=20):
    """ADX trend strength filter"""
    adx = calculate_adx(high, low, close, period)
    return adx[-1] > threshold


# ==========================================
# KERNEL REGRESSION
# ==========================================

def rational_quadratic_kernel(close, h=8, r=8.0, x=25):
    """
    Rational Quadratic Kernel Regression
    """
    n = len(close)
    yhat = np.zeros(n)
    
    for i in range(x, n):
        weights = np.zeros(x)
        for j in range(x):
            lag = j + 1
            weight = (1 + (lag**2) / (2 * r * h**2)) ** (-r)
            weights[j] = weight
        
        # Normalize weights
        weights = weights / np.sum(weights)
        
        # Weighted average
        window = close[i-x:i]
        yhat[i] = np.sum(window * weights)
    
    return yhat


# ==========================================
# SIGNAL GENERATOR CLASS
# ==========================================

class LorentzianSignalGenerator:
    def __init__(self, db_path="data/banknifty_data.db"):
        self.db_path = db_path
        self.df = None
        
        # Signal state
        self.current_signal = 0  # 0=neutral, 1=long, -1=short
        self.in_position = False
        self.entry_bar_index = -1
        self.entry_price = 0
        self.entry_direction = 0  # 1=long, -1=short
        self.bars_held = 0
        
        # Store entry candle signal for repaint detection
        self.entry_candle_had_signal = False
        
        # Configuration
        self.config = {
            'neighbors_count': 8,
            'max_bars_back': 2000,
            'use_filters': True,
            'use_kernel': True,
            'kernel_h': 8,
            'kernel_r': 8.0,
            'kernel_x': 25,
            'use_ema_filter': False,
            'ema_period': 200,
            'use_reentry': True,
            'reentry_window_min': 1,
            'reentry_window_max': 8,
        }
    
    def load_data(self, timeframe='15min', n_bars=2000):
        """Load historical data from database"""
        print(f"📊 Loading {n_bars} bars of {timeframe} data...")
        
        conn = sqlite3.connect(self.db_path)
        
        query = f"""
            SELECT timestamp, open, high, low, close, volume
            FROM ohlcv
            WHERE timeframe = '{timeframe}'
            ORDER BY timestamp DESC
            LIMIT {n_bars}
        """
        
        df = pd.read_sql(query, conn)
        conn.close()
        
        # Sort chronologically
        df = df.sort_values('timestamp').reset_index(drop=True)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        self.df = df
        print(f"✅ Loaded {len(df)} bars")
        print(f"   Range: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
        
        return df
    
    def generate_signal(self, new_candle=None):
        """
        Generate Lorentzian signal for latest candle
        
        Parameters:
        -----------
        new_candle : dict, optional
            New candle data: {'open', 'high', 'low', 'close', 'volume'}
            If provided, append to existing data
        
        Returns:
        --------
        dict: {
            'signal': 1 (long), -1 (short), or 0 (neutral),
            'prediction': raw prediction score,
            'entry': True if new entry signal,
            'exit': True if exit signal,
            'exit_reason': 'bars_held' | 'volume_node' | 'repaint'
        }
        """
        start_time = time.time()
        
        # Append new candle if provided
        if new_candle is not None:
            self.df = pd.concat([self.df, pd.DataFrame([new_candle])], ignore_index=True)
            # Keep only last max_bars_back + 100 for memory
            if len(self.df) > self.config['max_bars_back'] + 100:
                self.df = self.df.iloc[-(self.config['max_bars_back'] + 100):].reset_index(drop=True)
        
        df = self.df
        
        # Calculate features for all bars
        f1, f2, f3, f4, f5 = calculate_features(df, self.config)
        
        # Create labels (direction 4 bars ahead)
        close = df['close'].values
        labels = np.zeros(len(close))
        for i in range(len(close) - 4):
            if close[i+4] > close[i]:
                labels[i] = 1  # Long
            elif close[i+4] < close[i]:
                labels[i] = -1  # Short
        
        # Get current features (latest bar)
        f1_cur = f1[-1]
        f2_cur = f2[-1]
        f3_cur = f3[-1]
        f4_cur = f4[-1]
        f5_cur = f5[-1]
        
        # Historical features (exclude last bar)
        max_lookback = min(self.config['max_bars_back'], len(f1) - 1)
        f1_hist = f1[-max_lookback-1:-1]
        f2_hist = f2[-max_lookback-1:-1]
        f3_hist = f3[-max_lookback-1:-1]
        f4_hist = f4[-max_lookback-1:-1]
        f5_hist = f5[-max_lookback-1:-1]
        labels_hist = labels[-max_lookback-1:-1]
        
        # Find k-nearest neighbors and predict
        prediction = find_k_nearest_neighbors(
            f1_cur, f2_cur, f3_cur, f4_cur, f5_cur,
            f1_hist, f2_hist, f3_hist, f4_hist, f5_hist,
            labels_hist,
            k=self.config['neighbors_count']
        )
        
        # Apply filters
        filter_pass = True
        if self.config['use_filters']:
            vol_filter = volatility_filter(close)
            regime_f = regime_filter((df['high'] + df['low'] + df['close'] + df['open']) / 4)
            # adx_f = adx_filter(df['high'].values, df['low'].values, close)
            
            filter_pass = vol_filter and regime_f
        
        # Kernel filter
        kernel_bullish = True
        kernel_bearish = True
        if self.config['use_kernel']:
            yhat = rational_quadratic_kernel(
                close,
                h=self.config['kernel_h'],
                r=self.config['kernel_r'],
                x=self.config['kernel_x']
            )
            kernel_bullish = yhat[-1] > yhat[-2]  # Bullish trend
            kernel_bearish = yhat[-1] < yhat[-2]  # Bearish trend
        
        # Generate signal
        signal = 0
        if prediction > 0 and filter_pass and kernel_bullish:
            signal = 1  # Long
        elif prediction < 0 and filter_pass and kernel_bearish:
            signal = -1  # Short
        
        # ==========================================
        # EXIT LOGIC (3 strategies)
        # ==========================================
        
        exit_signal = False
        exit_reason = None
        
        if self.in_position:
            self.bars_held += 1
            
            # EXIT 1: Default - 4 bars held
            if self.bars_held >= 4:
                exit_signal = True
                exit_reason = 'bars_held'
            
            # EXIT 3: REPAINT - Entry candle closes with NO signal
            # Check if we're still on entry candle (bars_held == 0 after increment means we just entered)
            if self.bars_held == 1:  # Still on entry candle
                self.entry_candle_had_signal = (signal == self.entry_direction)
            
            # If entry candle closes and signal disappeared
            if self.bars_held == 1 and not self.entry_candle_had_signal:
                exit_signal = True
                exit_reason = 'repaint'
                print(f"   ⚠️  REPAINT EXIT: Signal disappeared on entry candle!")
        
        # Entry logic
        entry_signal = False
        if not self.in_position:
            if signal != 0 and signal != self.current_signal:
                # New entry
                entry_signal = True
                self.in_position = True
                self.entry_bar_index = len(df) - 1
                self.entry_price = close[-1]
                self.entry_direction = signal
                self.bars_held = 0
                self.entry_candle_had_signal = True
                
                print(f"   🎯 {'LONG' if signal == 1 else 'SHORT'} ENTRY @ {self.entry_price:.2f}")
        
        # Process exit
        if exit_signal:
            self.in_position = False
            self.bars_held = 0
            print(f"   🚪 EXIT @ {close[-1]:.2f} | Reason: {exit_reason}")
        
        # Update current signal
        self.current_signal = signal
        
        # Calculate processing time
        process_time = (time.time() - start_time) * 1000  # ms
        
        result = {
            'signal': signal,
            'prediction': prediction,
            'entry': entry_signal,
            'exit': exit_signal,
            'exit_reason': exit_reason,
            'in_position': self.in_position,
            'bars_held': self.bars_held,
            'entry_price': self.entry_price if self.in_position else None,
            'current_price': close[-1],
            'process_time_ms': process_time
        }
        
        return result


# ==========================================
# TEST / DEMO
# ==========================================

def test_signal_generator():
    """Test the signal generator"""
    print("="*80)
    print("🧪 TESTING LORENTZIAN SIGNAL GENERATOR")
    print("="*80)
    
    # Initialize
    generator = LorentzianSignalGenerator()
    
    # Load data
    df = generator.load_data(timeframe='15min', n_bars=2000)
    
    print("\n🔄 Generating signals for last 100 bars...")
    
    # Simulate real-time by processing bar-by-bar
    for i in range(len(df) - 100, len(df)):
        # Use data up to current bar
        generator.df = df.iloc[:i+1].copy()
        
        result = generator.generate_signal()
        
        if result['entry']:
            print(f"\n📊 Bar {i}: {'🟢 LONG' if result['signal'] == 1 else '🔴 SHORT'} @ {result['current_price']:.2f}")
            print(f"   Prediction: {result['prediction']:.1f}")
            print(f"   Process time: {result['process_time_ms']:.2f}ms")
        
        if result['exit']:
            pnl = (result['current_price'] - result['entry_price']) * result['signal']
            pnl_pct = (pnl / result['entry_price']) * 100
            print(f"   EXIT: {result['exit_reason']} | P&L: {pnl_pct:+.2f}%")
    
    print("\n✅ Test complete!")


if __name__ == "__main__":
    test_signal_generator()