"""
Dual Timeframe System - 15min + 1hr
Takes all 15m signals, tags when 1h confirms
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

from .trading_system import LorentzianTradingSystem, TradingSettings


@dataclass
class Signal:
    """Trading signal with timestamp"""
    direction: int  # 1=long, -1=short
    timestamp: datetime
    bar_index: int
    price: float
    prediction: float


@dataclass
class TimeframeData:
    """OHLCV data for a timeframe"""
    timestamp: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    bar_index: np.ndarray


class DualTimeframeSystem:
    """Manages 15min and 1hr signals"""
    
    def __init__(self, settings: TradingSettings):
        self.system_15m = LorentzianTradingSystem(settings)
        self.system_1h = LorentzianTradingSystem(settings)
        
        self.results_15m = None
        self.results_1h = None
        
        self.data_15m = None
        self.data_1h = None
    
    def load_data(self, df_15m: pd.DataFrame, df_1h: pd.DataFrame):
        """Load and pre-calculate all signals once"""
        print("Loading data...")
        
        self.data_15m = TimeframeData(
            timestamp=df_15m['timestamp'].values,
            high=df_15m['high'].values,
            low=df_15m['low'].values,
            close=df_15m['close'].values,
            volume=df_15m['volume'].values,
            bar_index=np.arange(len(df_15m))
        )
        
        self.data_1h = TimeframeData(
            timestamp=df_1h['timestamp'].values,
            high=df_1h['high'].values,
            low=df_1h['low'].values,
            close=df_1h['close'].values,
            volume=df_1h['volume'].values,
            bar_index=np.arange(len(df_1h))
        )
        
        print("Calculating 15min signals...")
        self.results_15m = self.system_15m.generate_signals(
            self.data_15m.high, self.data_15m.low, self.data_15m.close, start_bar=100
        )
        
        print("Calculating 1hr signals...")
        self.results_1h = self.system_1h.generate_signals(
            self.data_1h.high, self.data_1h.low, self.data_1h.close, start_bar=100
        )
        
        print("✅ All signals pre-calculated\n")
    
    def get_signal_at_bar(self, bar_idx: int, timeframe: str = '15m') -> Optional[Signal]:
        """Get signal at bar"""
        results = self.results_15m if timeframe == '15m' else self.results_1h
        data = self.data_15m if timeframe == '15m' else self.data_1h
        
        if results['start_long'][bar_idx]:
            return Signal(1, data.timestamp[bar_idx], bar_idx, 
                         data.close[bar_idx], results['predictions'][bar_idx])
        elif results['start_short'][bar_idx]:
            return Signal(-1, data.timestamp[bar_idx], bar_idx,
                         data.close[bar_idx], results['predictions'][bar_idx])
        return None
    
    def find_1h_bar_for_time(self, timestamp) -> int:
        """Find 1hr bar index containing timestamp"""
        target_ts = pd.Timestamp(timestamp)
        
        for i in range(len(self.data_1h.timestamp)):
            bar_ts = pd.Timestamp(self.data_1h.timestamp[i])
            if bar_ts >= target_ts:
                return i
        
        return len(self.data_1h.timestamp) - 1
    
    def check_confluence_window(self, bar_15m: int) -> Tuple[bool, Optional[Signal], str]:
        """
        PRIMARY: 15m signals (always trade these)
        SECONDARY: 1h confirmation (quality enhancement)
        Returns: (has_signal, signal_15m, '15m' or '1h')
        """
        # Get 15m signal (primary)
        signal_15m = self.get_signal_at_bar(bar_15m, '15m')
        if not signal_15m:
            return False, None, 'none'
        
        # Check for 1h confluence
        has_1h_confirm = False
        
        if bar_15m < len(self.data_15m.timestamp) - 1:
            time_15m_ts = pd.Timestamp(self.data_15m.timestamp[bar_15m])
            next_15m_ts = pd.Timestamp(self.data_15m.timestamp[bar_15m + 1])
            
            bar_1h = self.find_1h_bar_for_time(time_15m_ts)
            
            # Check current and next 1h bar
            for check_bar in [bar_1h, bar_1h + 1]:
                if check_bar >= len(self.data_1h.timestamp):
                    break
                
                signal_1h = self.get_signal_at_bar(check_bar, '1h')
                if signal_1h:
                    signal_ts = pd.Timestamp(signal_1h.timestamp)
                    
                    # 1h signal within window and same direction
                    if signal_ts <= next_15m_ts and signal_1h.direction == signal_15m.direction:
                        has_1h_confirm = True
                        break
        
        # Return 15m signal, tag as '1h' if confirmed
        return True, signal_15m, '1h' if has_1h_confirm else '15m'


if __name__ == "__main__":
    import sqlite3
    import time
    
    DB_PATH = "/Users/rohan/Downloads/Virdhi_Captial_trading_system/banknifty_trading_system/scripts/data/banknifty_data.db"
    
    print("Dual Timeframe Test\n" + "="*60)
    
    conn = sqlite3.connect(DB_PATH)
    
    df_15m = pd.read_sql_query("""
        SELECT timestamp, open, high, low, close, volume
        FROM ohlcv WHERE timeframe = '15min'
        ORDER BY timestamp DESC LIMIT 2000
    """, conn)
    
    df_1h = pd.read_sql_query("""
        SELECT timestamp, open, high, low, close, volume
        FROM ohlcv WHERE timeframe = '1hour'
        ORDER BY timestamp DESC LIMIT 500
    """, conn)
    
    conn.close()
    
    df_15m = df_15m.iloc[::-1].reset_index(drop=True)
    df_1h = df_1h.iloc[::-1].reset_index(drop=True)
    
    df_15m['timestamp'] = pd.to_datetime(df_15m['timestamp'], unit='s').dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')
    df_1h['timestamp'] = pd.to_datetime(df_1h['timestamp'], unit='s').dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')
    
    print(f"15min: {len(df_15m)} bars")
    print(f"1hr:   {len(df_1h)} bars\n")
    
    settings = TradingSettings(neighbors_count=5, max_bars_back=1000)
    dual_system = DualTimeframeSystem(settings)
    
    start = time.perf_counter()
    dual_system.load_data(df_15m, df_1h)
    load_time = time.perf_counter() - start
    print(f"⚡ Pre-calculation took {load_time:.2f}s\n")
    
    print("Testing confluence detection...\n")
    signals_15m = 0
    signals_1h = 0
    
    start = time.perf_counter()
    for bar in range(200, len(df_15m)):
        has_signal, signal, tf = dual_system.check_confluence_window(bar)
        
        if has_signal:
            if tf == '1h':
                signals_1h += 1
            else:
                signals_15m += 1
    
    check_time = (time.perf_counter() - start) * 1000
    
    print(f"⚡ Checked {len(df_15m) - 200} bars in {check_time:.2f}ms")
    print(f"   15m only signals: {signals_15m}")
    print(f"   1h confirmed:     {signals_1h}")
    print(f"   Total signals:    {signals_15m + signals_1h}")
    print("\n✅ Dual timeframe system ready")