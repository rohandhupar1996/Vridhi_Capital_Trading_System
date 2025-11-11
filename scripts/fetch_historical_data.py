"""
BankNifty Historical Data Fetcher
Fetches OHLCV data from TradingView and stores in SQLite database
"""

import sqlite3
import pandas as pd
from tvDatafeed import TvDatafeed, Interval
from datetime import datetime
import time
import os
from pathlib import Path
from dotenv import load_dotenv

class BankNiftyDataCollector:
    def __init__(self, db_path="data/banknifty_data.db"):
        """Initialize data collector with database path"""
        self.db_path = db_path
        self.conn = None
        self.tv = None
        
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Load environment variables from config/.env
        env_path = os.path.join('/Users/rohan/Downloads/Virdhi_Captial_trading_system/banknifty_trading_system/config', '.env')
        if os.path.exists(env_path):
            load_dotenv(env_path)
            print(f"✅ Loaded configuration from {env_path}")
        
    def setup_database(self):
        """Create database and tables if they don't exist"""
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()
        
        # Create main OHLCV table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv (
                timestamp DATETIME,
                symbol TEXT,
                timeframe TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                PRIMARY KEY (timestamp, symbol, timeframe)
            )
        """)
        
        # Create metadata table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at DATETIME
            )
        """)
        
        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON ohlcv(timestamp)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_symbol_timeframe 
            ON ohlcv(symbol, timeframe)
        """)
        
        self.conn.commit()
        print("✅ Database setup complete")
        print(f"📁 Database location: {os.path.abspath(self.db_path)}")
        
    def connect_tradingview(self, username=None, password=None):
        """Connect to TradingView with credentials"""
        # Get credentials from parameters, environment, or user input
        tv_user = username or os.getenv('TV_USERNAME')
        tv_pass = password or os.getenv('TV_PASSWORD')
        
        if not tv_user or not tv_pass:
            print("⚠️  Credentials not found in config/.env")
            print("    Please enter your TradingView credentials:")
            tv_user = input("    Username: ")
            tv_pass = input("    Password: ")
        else:
            print(f"✅ Using credentials for: {tv_user}")
        
        try:
            print("🔐 Connecting to TradingView...")
            self.tv = TvDatafeed(tv_user, tv_pass)
            print("✅ Connected to TradingView successfully!")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to TradingView: {e}")
            print("\nPossible issues:")
            print("  - Incorrect username/password")
            print("  - Google authentication still enabled (must use email/password)")
            print("  - TradingView rate limiting")
            return False
    
    def check_existing_data(self, symbol, timeframe):
        """Check if data already exists for symbol and timeframe"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*), MIN(timestamp), MAX(timestamp)
            FROM ohlcv
            WHERE symbol = ? AND timeframe = ?
        """, (symbol, timeframe))
        
        result = cursor.fetchone()
        count = result[0]
        
        if count > 0:
            return {
                'exists': True,
                'count': count,
                'min_date': result[1],
                'max_date': result[2]
            }
        return {'exists': False}
    
    def fetch_and_store(self, symbol, exchange, timeframe_name, interval, n_bars=5000):
        """Fetch data from TradingView and store in database"""
        print(f"\n{'='*60}")
        print(f"📊 Fetching {timeframe_name} data for {symbol}")
        print(f"{'='*60}")
        
        # Check existing data
        existing = self.check_existing_data(symbol, timeframe_name)
        if existing['exists']:
            print(f"ℹ️  Found {existing['count']} existing bars")
            print(f"   Date range: {existing['min_date']} to {existing['max_date']}")
            
            response = input("   Overwrite existing data? (y/n): ").lower()
            if response != 'y':
                print("⏭️  Skipping...")
                return False
        
        try:
            # Fetch data from TradingView
            print(f"🔄 Fetching {n_bars} bars from TradingView...")
            data = self.tv.get_hist(
                symbol=symbol,
                exchange=exchange,
                interval=interval,
                n_bars=n_bars
            )
            
            if data is None or data.empty:
                print(f"❌ No data returned for {timeframe_name}")
                print(f"   Symbol: {symbol}, Exchange: {exchange}")
                return False
            
            # Prepare data for storage
            data = data.reset_index()
            data['symbol'] = symbol
            data['timeframe'] = timeframe_name
            data.rename(columns={'datetime': 'timestamp'}, inplace=True)
            
            # Select only needed columns
            data = data[['timestamp', 'symbol', 'timeframe', 'open', 'high', 'low', 'close', 'volume']]
            
            # Delete existing data for this symbol/timeframe if overwriting
            if existing['exists']:
                cursor = self.conn.cursor()
                cursor.execute("""
                    DELETE FROM ohlcv 
                    WHERE symbol = ? AND timeframe = ?
                """, (symbol, timeframe_name))
                self.conn.commit()
            
            # Store in database
            data.to_sql('ohlcv', self.conn, if_exists='append', index=False)
            self.conn.commit()
            
            # Update metadata
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO metadata (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (f"{symbol}_{timeframe_name}_last_updated", 
                  data['timestamp'].max().isoformat(),
                  datetime.now().isoformat()))
            self.conn.commit()
            
            print(f"✅ Saved {len(data)} bars")
            print(f"   Date range: {data['timestamp'].min()} to {data['timestamp'].max()}")
            print(f"   Latest close: {data['close'].iloc[-1]:.2f}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error fetching {timeframe_name} data: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def collect_all_data(self):
        """Fetch all timeframes for BankNifty"""
        symbol = "BANKNIFTY1!"
        exchange = "NSE"
        
        timeframes = [
            ("5min", Interval.in_5_minute, 5000),
            ("15min", Interval.in_15_minute, 5000),
            ("1hour", Interval.in_1_hour, 5000),
        ]
        
        results = []
        
        for tf_name, tf_interval, bars in timeframes:
            success = self.fetch_and_store(
                symbol=symbol,
                exchange=exchange,
                timeframe_name=tf_name,
                interval=tf_interval,
                n_bars=bars
            )
            results.append((tf_name, success))
            
            # Rate limiting - be nice to TradingView servers
            if tf_name != timeframes[-1][0]:  # Don't wait after last one
                print("⏳ Waiting 5 seconds before next request...")
                time.sleep(5)
        
        return results
    
    def get_statistics(self):
        """Get summary statistics of stored data"""
        cursor = self.conn.cursor()
        
        print(f"\n{'='*60}")
        print("📊 DATABASE STATISTICS")
        print(f"{'='*60}")
        
        # Total bars
        cursor.execute("SELECT COUNT(*) FROM ohlcv")
        total_bars = cursor.fetchone()[0]
        print(f"Total bars stored: {total_bars:,}")
        
        # By timeframe
        cursor.execute("""
            SELECT timeframe, COUNT(*), MIN(timestamp), MAX(timestamp)
            FROM ohlcv
            GROUP BY timeframe
            ORDER BY timeframe
        """)
        
        print(f"\n{'Timeframe':<10} {'Bars':<10} {'From':<20} {'To':<20}")
        print("-" * 60)
        
        for row in cursor.fetchall():
            tf, count, min_date, max_date = row
            print(f"{tf:<10} {count:<10,} {min_date:<20} {max_date:<20}")
        
        # Database file size
        if os.path.exists(self.db_path):
            db_size = os.path.getsize(self.db_path) / (1024 * 1024)  # MB
            print(f"\nDatabase size: {db_size:.2f} MB")
            print(f"Database location: {os.path.abspath(self.db_path)}")
        
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            print("\n✅ Database connection closed")


def main():
    """Main execution function"""
    print("="*60)
    print("🚀 BANKNIFTY HISTORICAL DATA COLLECTOR")
    print("="*60)
    print()
    
    # Initialize collector with correct path
    collector = BankNiftyDataCollector(db_path="data/banknifty_data.db")
    
    # Setup database
    collector.setup_database()
    print()
    
    # Connect to TradingView
    if not collector.connect_tradingview():
        print("\n❌ Failed to connect. Exiting...")
        collector.close()
        return
    
    # Collect all data
    print("\n🔄 Starting data collection...")
    print("    This will take approximately 30-60 seconds...")
    results = collector.collect_all_data()
    
    # Show results summary
    print(f"\n{'='*60}")
    print("📋 COLLECTION SUMMARY")
    print(f"{'='*60}")
    
    success_count = sum(1 for _, success in results if success)
    total_count = len(results)
    
    for tf_name, success in results:
        status = "✅ Success" if success else "❌ Failed"
        print(f"{tf_name:<10} {status}")
    
    print(f"\nCompleted: {success_count}/{total_count}")
    
    # Show statistics
    if success_count > 0:
        collector.get_statistics()
    else:
        print("\n⚠️  No data collected. Please check errors above.")
    
    # Close connection
    collector.close()
    
    if success_count > 0:
        print("\n" + "="*60)
        print("✨ DATA COLLECTION COMPLETE!")
        print("="*60)
        print("\n📌 Next steps:")
        print("   1. Open DBeaver")
        print("   2. Connect to SQLite database")
        print(f"   3. Browse to: {os.path.abspath('data/banknifty_data.db')}")
        print("   4. View the 'ohlcv' table")
    else:
        print("\n" + "="*60)
        print("❌ DATA COLLECTION FAILED")
        print("="*60)
        print("\nPlease check the errors above and try again.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Exiting...")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()