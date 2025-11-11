"""
Real Repainting Analysis - Run ML on Partial 15min Candles
Tests signal stability as candle forms minute-by-minute
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from .trading_system import LorentzianTradingSystem, TradingSettings


class RealRepaintingAnalyzer:
    """Test repainting by running ML on partial candles"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        
        # Initialize trading system
        self.settings = TradingSettings(
            neighbors_count=5,
            max_bars_back=2000,
            use_kernel_filter=True,
            use_volatility_filter=True,
            use_regime_filter=True,
            enable_reentry=True,
            reentry_window_start=3,
            reentry_window_end=50
        )
        self.system = LorentzianTradingSystem(self.settings)
    
    def load_data(self):
        """Load both 1min and 15min data"""
        # 1min data
        df_1min = pd.read_sql_query("""
            SELECT timestamp, open, high, low, close, volume
            FROM ohlcv WHERE timeframe = '1min'
            ORDER BY timestamp
        """, self.conn)
        df_1min['timestamp'] = pd.to_datetime(df_1min['timestamp'], unit='s').dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')
        
        # 15min data
        df_15min = pd.read_sql_query("""
            SELECT timestamp, open, high, low, close, volume
            FROM ohlcv WHERE timeframe = '15min'
            ORDER BY timestamp
        """, self.conn)
        df_15min['timestamp'] = pd.to_datetime(df_15min['timestamp'], unit='s').dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')
        
        # Filter to overlapping range
        min_1min_time = df_1min['timestamp'].min()
        max_1min_time = df_1min['timestamp'].max()
        
        df_15min = df_15min[
            (df_15min['timestamp'] >= min_1min_time) & 
            (df_15min['timestamp'] <= max_1min_time)
        ]
        
        print(f"   1-min coverage: {min_1min_time} to {max_1min_time}")
        print(f"   Overlapping 15-min bars: {len(df_15min)}")
        
        return df_1min, df_15min
    
    def build_partial_15min(self, df_1min, up_to_bar):
        """
        Build 15min candles using only first N minutes of each period
        up_to_bar: how many 1-min bars to use (1-15)
        """
        df_1min['period'] = df_1min['timestamp'].dt.floor('15min')
        
        result_bars = []
        for period, group in df_1min.groupby('period'):
            # Sort and take first N bars
            group_sorted = group.sort_values('timestamp')
            partial = group_sorted.head(up_to_bar)
            
            if len(partial) >= up_to_bar:  # Only include complete partials
                bar = {
                    'timestamp': period,
                    'open': partial['open'].iloc[0],
                    'high': partial['high'].max(),
                    'low': partial['low'].min(),
                    'close': partial['close'].iloc[-1],
                    'volume': partial['volume'].sum()
                }
                result_bars.append(bar)
        
        return pd.DataFrame(result_bars)
    
    def test_signal_at_minute(self, df_15min_partial):
        """Run ML classification on partial 15min data"""
        if len(df_15min_partial) < 200:
            return None
        
        # Generate signals
        results = self.system.generate_signals(
            df_15min_partial['high'].values,
            df_15min_partial['low'].values,
            df_15min_partial['close'].values,
            start_bar=100
        )
        
        # Extract last 100 bars signals
        signals = []
        for i in range(len(df_15min_partial) - 100, len(df_15min_partial)):
            if results['start_long'][i]:
                signals.append({
                    'timestamp': df_15min_partial.loc[i, 'timestamp'],
                    'type': 'LONG',
                    'price': df_15min_partial.loc[i, 'close']
                })
            elif results['start_short'][i]:
                signals.append({
                    'timestamp': df_15min_partial.loc[i, 'timestamp'],
                    'type': 'SHORT',
                    'price': df_15min_partial.loc[i, 'close']
                })
        
        return signals
    
    def analyze_repainting(self):
        """Compare signals at different minutes"""
        print(f"\n{'='*70}")
        print("REAL REPAINTING ANALYSIS - ML ON PARTIAL CANDLES")
        print(f"{'='*70}\n")
        
        df_1min, df_15min = self.load_data()
        
        print(f"Loaded {len(df_1min):,} 1-min bars")
        print(f"Loaded {len(df_15min):,} 15-min bars\n")
        
        # Test at minutes: 1, 5, 10, 15
        test_minutes = [1, 5, 10, 15]
        
        all_signals = {}
        
        for minute in test_minutes:
            print(f"🔄 Testing at minute {minute}...")
            
            # Build partial candles
            df_partial = self.build_partial_15min(df_1min, minute)
            
            print(f"   Built {len(df_partial)} partial candles")
            
            # Get signals
            signals = self.test_signal_at_minute(df_partial)
            
            if signals:
                all_signals[minute] = pd.DataFrame(signals)
                print(f"   Found {len(signals)} signals")
            else:
                all_signals[minute] = pd.DataFrame()
                print(f"   No signals (insufficient data)")
        
        # Compare signal consistency
        print(f"\n{'='*70}")
        print("SIGNAL STABILITY ANALYSIS")
        print(f"{'='*70}\n")
        
        # Confirmed signals (minute 15)
        confirmed = all_signals.get(15, pd.DataFrame())
        
        if confirmed.empty:
            print("❌ No confirmed signals to analyze")
            return
        
        print(f"Total confirmed signals: {len(confirmed)}\n")
        
        # Check how many appear at each earlier minute
        for minute in [1, 5, 10]:
            early = all_signals.get(minute, pd.DataFrame())
            
            if early.empty:
                print(f"Minute {minute:2d}: No signals")
                continue
            
            # Match by timestamp and type
            matched = pd.merge(
                confirmed,
                early,
                on=['timestamp', 'type'],
                how='inner',
                suffixes=('_conf', '_early')
            )
            
            match_rate = len(matched) / len(confirmed) * 100
            
            print(f"Minute {minute:2d}: {len(early)} signals total, {len(matched)} match confirmed ({match_rate:.1f}%)")
            
            # Price difference for matched signals
            if len(matched) > 0:
                matched['price_diff'] = abs(matched['price_conf'] - matched['price_early'])
                avg_diff = matched['price_diff'].mean()
                print(f"           Avg price diff: {avg_diff:.2f} points")
        
        # Repainting impact
        print(f"\n💡 REPAINTING INSIGHTS:")
        
        min_1 = all_signals.get(1, pd.DataFrame())
        min_15 = confirmed
        
        if not min_1.empty:
            # Signals only in minute 1 (will disappear)
            false_signals = len(min_1) - len(pd.merge(min_1, min_15, on=['timestamp', 'type']))
            print(f"  False signals at min 1: {false_signals} ({false_signals/len(min_1)*100:.1f}%)")
        
        # New signals appearing late
        min_10 = all_signals.get(10, pd.DataFrame())
        if not min_10.empty:
            new_late = len(min_15) - len(pd.merge(min_10, min_15, on=['timestamp', 'type']))
            print(f"  New signals after min 10: {new_late} ({new_late/len(min_15)*100:.1f}%)")
        
        return all_signals


def main():
    DB_PATH = "/Users/rohan/Downloads/Virdhi_Captial_trading_system/banknifty_trading_system/scripts/data/banknifty_data.db"
    
    analyzer = RealRepaintingAnalyzer(DB_PATH)
    
    # Check data exists
    cursor = analyzer.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM ohlcv WHERE timeframe = '1min'")
    count_1min = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM ohlcv WHERE timeframe = '15min'")
    count_15min = cursor.fetchone()[0]
    
    if count_1min == 0:
        print("❌ No 1-min data! Run data_collection_with_1min.py first")
        return
    
    if count_15min == 0:
        print("❌ No 15-min data!")
        return
    
    print(f"✅ Found {count_1min:,} 1-min bars, {count_15min:,} 15-min bars")
    
    # Run analysis
    signals = analyzer.analyze_repainting()
    
    analyzer.conn.close()


if __name__ == "__main__":
    main()