#!/usr/bin/env python3
"""
Data Completeness Checker
Checks if 15min data is complete for all market working days (excluding weekends and holidays).
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import pytz
import sqlite3

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

KOLKATA_TZ = pytz.timezone("Asia/Kolkata")

# Market holidays for 2024-2025 (add more as needed)
MARKET_HOLIDAYS = {
    # 2024
    datetime(2024, 1, 26).date(),  # Republic Day
    datetime(2024, 3, 8).date(),   # Holi
    datetime(2024, 3, 29).date(),  # Good Friday
    datetime(2024, 4, 11).date(),  # Id-Ul-Fitr
    datetime(2024, 4, 17).date(),  # Ram Navami
    datetime(2024, 5, 1).date(),   # Labour Day
    datetime(2024, 6, 17).date(),  # Id-Ul-Adha
    datetime(2024, 8, 15).date(),   # Independence Day
    datetime(2024, 8, 26).date(),  # Janmashtami
    datetime(2024, 10, 2).date(),  # Gandhi Jayanti
    datetime(2024, 10, 31).date(), # Diwali-Balipratipada
    datetime(2024, 11, 1).date(),  # Diwali
    datetime(2024, 11, 15).date(), # Guru Nanak Jayanti
    # 2025
    datetime(2025, 1, 15).date(),   # Makar Sankranti
    datetime(2025, 1, 26).date(),  # Republic Day
    datetime(2025, 2, 14).date(),  # Vasant Panchami
    datetime(2025, 3, 29).date(),  # Holi
    datetime(2025, 4, 18).date(),  # Good Friday
    datetime(2025, 4, 21).date(),  # Ram Navami
    datetime(2025, 5, 1).date(),   # Labour Day
    datetime(2025, 6, 6).date(),   # Id-Ul-Fitr
    datetime(2025, 6, 17).date(),  # Id-Ul-Adha
    datetime(2025, 8, 15).date(),  # Independence Day
    datetime(2025, 8, 15).date(),  # Janmashtami
    datetime(2025, 10, 2).date(),  # Gandhi Jayanti
    datetime(2025, 10, 20).date(), # Dussehra
    datetime(2025, 10, 23).date(), # Diwali-Balipratipada
    datetime(2025, 10, 24).date(), # Diwali
    datetime(2025, 11, 5).date(),  # Bhai Dooj
    datetime(2025, 11, 14).date(), # Guru Nanak Jayanti
}


def is_market_holiday(date: datetime.date) -> bool:
    """Check if a date is a market holiday."""
    return date in MARKET_HOLIDAYS


def is_weekend(date: datetime.date) -> bool:
    """Check if a date is a weekend (Saturday or Sunday)."""
    return date.weekday() >= 5


def is_trading_day(date: datetime.date) -> bool:
    """Check if a date is a trading day (not weekend, not holiday)."""
    return not is_weekend(date) and not is_market_holiday(date)


def get_expected_timestamps(start_date: datetime.date, end_date: datetime.date) -> list[datetime]:
    """Get expected 15min candle timestamps for all trading days."""
    expected = []
    current_date = start_date
    
    while current_date <= end_date:
        if is_trading_day(current_date):
            # Market hours: 9:15 AM to 3:30 PM IST
            # 15min candles: 9:15, 9:30, 9:45, 10:00, ..., 3:15
            # Last candle at 3:15 PM covers period 3:15-3:30 PM
            # Total: 25 candles per day (9:15 to 3:15 inclusive)
            market_open = datetime.combine(current_date, datetime.min.time().replace(hour=9, minute=15))
            last_candle = datetime.combine(current_date, datetime.min.time().replace(hour=15, minute=15))
            
            # Generate 15min intervals from 9:15 to 3:15 (inclusive)
            current_time = market_open
            while current_time <= last_candle:
                expected.append(KOLKATA_TZ.localize(current_time))
                current_time += timedelta(minutes=15)
        
        current_date += timedelta(days=1)
    
    return expected


def check_data_completeness(db_path: Path, table_name: str, symbol: str = "BANKNIFTY1!") -> dict:
    """Check data completeness for a table."""
    try:
        conn = sqlite3.connect(db_path)
        
        # Get all timestamps from database
        query = f"""
            SELECT DISTINCT timestamp
            FROM {table_name}
            WHERE symbol = ? AND timeframe = '15min'
            ORDER BY timestamp
        """
        
        df = pd.read_sql_query(query, conn, params=(symbol,))
        conn.close()
        
        if df.empty:
            return {
                'table': table_name,
                'symbol': symbol,
                'total_candles': 0,
                'missing_candles': 0,
                'completeness_percent': 0.0,
                'date_range': None,
                'missing_dates': [],
                'status': '❌ NO DATA'
            }
        
        # Convert timestamps
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
        df['timestamp'] = df['timestamp'].dt.tz_convert('Asia/Kolkata')
        
        # Get date range
        start_date = df['timestamp'].min().date()
        end_date = df['timestamp'].max().date()
        
        # Get expected timestamps
        expected_timestamps = get_expected_timestamps(start_date, end_date)
        expected_set = set(expected_timestamps)
        
        # Get actual timestamps
        actual_timestamps = set(df['timestamp'].tolist())
        
        # Find missing timestamps
        missing_timestamps = expected_set - actual_timestamps
        
        # Group missing by date
        missing_dates = {}
        for ts in missing_timestamps:
            date_key = ts.date()
            if date_key not in missing_dates:
                missing_dates[date_key] = []
            missing_dates[date_key].append(ts.strftime('%H:%M'))
        
        # Calculate completeness
        total_expected = len(expected_timestamps)
        total_actual = len(actual_timestamps)
        missing_count = len(missing_timestamps)
        completeness = (total_actual / total_expected * 100) if total_expected > 0 else 0.0
        
        status = '✅ COMPLETE' if missing_count == 0 else '⚠️  INCOMPLETE'
        
        return {
            'table': table_name,
            'symbol': symbol,
            'total_candles': total_actual,
            'expected_candles': total_expected,
            'missing_candles': missing_count,
            'completeness_percent': completeness,
            'date_range': (start_date, end_date),
            'missing_dates': missing_dates,
            'status': status
        }
        
    except Exception as e:
        return {
            'table': table_name,
            'symbol': symbol,
            'error': str(e),
            'status': '❌ ERROR'
        }


def main():
    """Main entry point"""
    print("=" * 70)
    print("🔍 DATA COMPLETENESS CHECKER")
    print("=" * 70)
    print()
    
    db_path = PROJECT_ROOT / "data" / "banknifty_data.db"
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return 1
    
    print(f"📁 Database: {db_path}")
    print()
    
    # Check both tables
    # For Zerodha, we need to check all symbols in the table
    tables_to_check = [
        ('ohlcv', 'BANKNIFTY1!'),
    ]
    
    # For ohlcv_zerodha, check all symbols dynamically
    try:
        conn = sqlite3.connect(db_path)
        zerodha_symbols = pd.read_sql_query(
            "SELECT DISTINCT symbol FROM ohlcv_zerodha WHERE timeframe = '15min'",
            conn
        )['symbol'].tolist()
        conn.close()
        
        for symbol in zerodha_symbols:
            tables_to_check.append(('ohlcv_zerodha', symbol))
    except:
        # Table might not exist yet
        pass
    
    results = []
    for table_name, symbol in tables_to_check:
        print(f"Checking {table_name} table (symbol: {symbol})...")
        result = check_data_completeness(db_path, table_name, symbol)
        results.append(result)
        print()
    
    # Print summary
    print("=" * 70)
    print("📊 COMPLETENESS SUMMARY")
    print("=" * 70)
    print()
    
    for result in results:
        if 'error' in result:
            print(f"{result['status']} {result['table']}: {result['error']}")
            continue
        
        print(f"{result['status']} {result['table'].upper()}")
        print(f"   Symbol: {result['symbol']}")
        print(f"   Date Range: {result['date_range'][0]} to {result['date_range'][1]}")
        print(f"   Expected Candles: {result['expected_candles']:,}")
        print(f"   Actual Candles: {result['total_candles']:,}")
        print(f"   Missing Candles: {result['missing_candles']:,}")
        print(f"   Completeness: {result['completeness_percent']:.2f}%")
        
        if result['missing_dates']:
            print(f"   Missing Dates: {len(result['missing_dates'])} day(s) with missing candles")
            # Show first 5 missing dates
            for date, times in list(result['missing_dates'].items())[:5]:
                print(f"      - {date}: {len(times)} missing candles ({', '.join(times[:5])}{'...' if len(times) > 5 else ''})")
            if len(result['missing_dates']) > 5:
                print(f"      ... and {len(result['missing_dates']) - 5} more day(s)")
        
        print()
    
    # Overall status
    all_complete = all(r.get('missing_candles', 0) == 0 for r in results if 'error' not in r)
    
    if all_complete:
        print("=" * 70)
        print("✅ ALL DATA IS COMPLETE!")
        print("=" * 70)
        return 0
    else:
        print("=" * 70)
        print("⚠️  SOME DATA IS INCOMPLETE")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())

