"""
V-Shape Reversal Level Detection
Identifies institutional supply/demand zones from major reversals
"""

import numpy as np
import pandas as pd
from typing import List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class ReversalLevel:
    """Major reversal price level"""
    price: float
    timestamp: datetime
    direction: str  # 'resistance' or 'support'
    strength: float  # 0-1, based on volume/range
    bar_range: float
    volume: float


class VShapeDetector:
    """Detect V-shape reversal patterns for exit levels"""
    
    def __init__(self, lookback_days: int = 252, min_strength: float = 1.5):
        self.lookback_days = lookback_days
        self.min_strength = min_strength
        self.reversal_levels: List[ReversalLevel] = []
        self.atr_period = 14
    
    def calculate_atr(self, high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
        """Calculate ATR for strength normalization"""
        tr = np.maximum(
            high - low,
            np.maximum(
                np.abs(high - np.roll(close, 1)),
                np.abs(low - np.roll(close, 1))
            )
        )
        atr = pd.Series(tr).rolling(self.atr_period).mean().values
        return atr
    
    def detect_v_patterns(self, df: pd.DataFrame) -> List[ReversalLevel]:
        """
        Detect V-shape reversal patterns
        Criteria:
        - Large bar range (>2x ATR)
        - Strong reversal (close near opposite end from open)
        - Volume spike (>1.5x average)
        """
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        open_price = df['open'].values
        volume = df['volume'].values
        timestamps = df['timestamp'].values
        
        # Calculate ATR
        atr = self.calculate_atr(high, low, close)
        
        # Calculate volume MA
        vol_ma = pd.Series(volume).rolling(20).mean().values
        
        reversals = []
        
        for i in range(self.atr_period + 20, len(df)):
            bar_range = high[i] - low[i]
            
            # Skip if ATR not available
            if np.isnan(atr[i]) or atr[i] == 0:
                continue
            
            # Check large range
            if bar_range < 2.0 * atr[i]:
                continue
            
            # Check volume spike
            if volume[i] < 1.5 * vol_ma[i]:
                continue
            
            # Check reversal direction
            body = close[i] - open_price[i]
            body_position = (close[i] - low[i]) / bar_range if bar_range > 0 else 0.5
            
            # Bullish reversal (V-bottom) - close near high
            if body_position > 0.7:
                strength = (bar_range / atr[i]) * (volume[i] / vol_ma[i])
                reversals.append(ReversalLevel(
                    price=low[i],  # Support level
                    timestamp=timestamps[i],
                    direction='support',
                    strength=strength,
                    bar_range=bar_range,
                    volume=volume[i]
                ))
            
            # Bearish reversal (inverted V) - close near low
            elif body_position < 0.3:
                strength = (bar_range / atr[i]) * (volume[i] / vol_ma[i])
                reversals.append(ReversalLevel(
                    price=high[i],  # Resistance level
                    timestamp=timestamps[i],
                    direction='resistance',
                    strength=strength,
                    bar_range=bar_range,
                    volume=volume[i]
                ))
        
        # Filter by minimum strength
        reversals = [r for r in reversals if r.strength >= self.min_strength]
        
        # Sort by strength, keep top levels
        reversals.sort(key=lambda x: x.strength, reverse=True)
        
        return reversals[:50]  # Keep top 50 levels
    
    def update_levels(self, df: pd.DataFrame, current_time: datetime):
        """Update reversal levels, remove old ones"""
        # Detect new patterns
        new_levels = self.detect_v_patterns(df)
        
        # Remove levels older than lookback period
        cutoff_time = current_time - timedelta(days=self.lookback_days)
        
        self.reversal_levels = [
            level for level in new_levels
            if pd.Timestamp(level.timestamp) > pd.Timestamp(cutoff_time)
        ]
    
    def check_level_proximity(self, current_price: float, direction: int, tolerance: float = 0.005) -> Tuple[bool, Optional[float]]:
        """
        Check if price near reversal level
        direction: 1=LONG, -1=SHORT
        tolerance: 0.005 = 0.5%
        """
        if direction == 1:  # LONG - check resistance above
            resistances = [l for l in self.reversal_levels if l.direction == 'resistance' and l.price > current_price]
            if resistances:
                nearest = min(resistances, key=lambda x: abs(x.price - current_price))
                if abs(nearest.price - current_price) / current_price <= tolerance:
                    return True, nearest.price
        
        else:  # SHORT - check support below
            supports = [l for l in self.reversal_levels if l.direction == 'support' and l.price < current_price]
            if supports:
                nearest = min(supports, key=lambda x: abs(x.price - current_price))
                if abs(nearest.price - current_price) / current_price <= tolerance:
                    return True, nearest.price
        
        return False, None
    
    def get_all_levels(self) -> dict:
        """Get all current levels for visualization"""
        return {
            'supports': [l.price for l in self.reversal_levels if l.direction == 'support'],
            'resistances': [l.price for l in self.reversal_levels if l.direction == 'resistance']
        }


if __name__ == "__main__":
    # Test
    import sqlite3
    
    DB_PATH = "/Users/rohan/Downloads/Virdhi_Captial_trading_system/banknifty_trading_system/scripts/data/banknifty_data.db"
    
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT timestamp, open, high, low, close, volume
        FROM ohlcv WHERE timeframe = '15min'
        ORDER BY timestamp DESC LIMIT 5000
    """, conn)
    conn.close()
    
    df = df.iloc[::-1].reset_index(drop=True)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    
    print(f"\n{'='*60}")
    print("V-SHAPE REVERSAL DETECTION TEST")
    print(f"{'='*60}\n")
    print(f"Analyzing {len(df)} bars...")
    
    detector = VShapeDetector(lookback_days=180, min_strength=2.0)
    detector.update_levels(df, df['timestamp'].iloc[-1])
    
    levels = detector.get_all_levels()
    
    print(f"\n📊 DETECTED LEVELS:")
    print(f"   Supports:    {len(levels['supports'])}")
    print(f"   Resistances: {len(levels['resistances'])}")
    
    print(f"\n🔴 TOP 5 RESISTANCE LEVELS:")
    for price in sorted(levels['resistances'], reverse=True)[:5]:
        print(f"   {price:.2f}")
    
    print(f"\n🟢 TOP 5 SUPPORT LEVELS:")
    for price in sorted(levels['supports'], reverse=True)[:5]:
        print(f"   {price:.2f}")
    
    # Test proximity check
    current_price = df['close'].iloc[-1]
    print(f"\n💰 Current Price: {current_price:.2f}")
    
    near_res, res_price = detector.check_level_proximity(current_price, 1, tolerance=0.01)
    near_sup, sup_price = detector.check_level_proximity(current_price, -1, tolerance=0.01)
    
    if near_res:
        print(f"   ⚠️  Near resistance: {res_price:.2f}")
    if near_sup:
        print(f"   ⚠️  Near support: {sup_price:.2f}")
    
    print("\n✅ V-shape detection ready")