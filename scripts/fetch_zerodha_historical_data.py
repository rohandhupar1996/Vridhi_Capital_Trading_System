#!/usr/bin/env python3
"""
Fetch Zerodha Historical Data Script
Fetches historical BankNifty futures candle data from Zerodha API
and stores it in ohlcv_zerodha table.

This script:
1. Fetches current month BankNifty futures token from Zerodha
2. Uses Zerodha historical API to get 5min, 15min, 1hr candles
3. Uses continuous=1 to get data from previous contracts
4. Stores all data in ohlcv_zerodha table
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import pytz
from dotenv import load_dotenv
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.console import Console

# Ensure project root and src/ directory are on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_PATH):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from src.trading_system.config import AppConfig
from src.trading_system.logging import setup_logging, ComponentLogger
from src.trading_system.broker.zerodha_auth import ZerodhaAuthenticator, ZerodhaCredentials, ConnectionStatus
from src.trading_system.data.zerodha_futures_utils import get_current_month_futures_symbol_and_token

KOLKATA_TZ = pytz.timezone("Asia/Kolkata")
console = Console()


def fetch_historical_candles_chunk(
    kite,
    instrument_token: int,
    interval: str,
    from_date: datetime,
    to_date: datetime,
    continuous: bool = False,
    oi: bool = False
) -> pd.DataFrame:
    """
    Fetch a single chunk of historical candles from Zerodha API.
    
    Args:
        kite: Authenticated KiteConnect instance
        instrument_token: Instrument token for the contract
        interval: Candle interval ('minute', '5minute', '15minute', '60minute', 'day')
        from_date: Start date (datetime in IST)
        to_date: End date (datetime in IST)
        continuous: Use continuous data (only works with 'day' interval)
        oi: Include OI data
        
    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
    """
    try:
        # Map our interval names to Zerodha API format
        interval_map = {
            '5min': '5minute',
            '15min': '15minute',
            '1hour': '60minute',
            '1hr': '60minute',
            'hour': '60minute',
            'minute': 'minute',
            'day': 'day'
        }
        api_interval = interval_map.get(interval, interval)
        
        # Fetch historical data
        data = kite.historical_data(
            instrument_token=instrument_token,
            from_date=from_date,
            to_date=to_date,
            interval=api_interval,
            continuous=1 if continuous else 0,
            oi=1 if oi else 0
        )
        
        if not data or len(data) == 0:
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # Parse response: [timestamp, open, high, low, close, volume, ...]
        records = []
        for candle in data:
            # Handle different response formats
            if isinstance(candle, list):
                timestamp_str = candle[0]
                open_price = float(candle[1])
                high_price = float(candle[2])
                low_price = float(candle[3])
                close_price = float(candle[4])
                volume = int(candle[5]) if len(candle) > 5 else 0
            elif isinstance(candle, dict):
                timestamp_str = candle['date']
                open_price = float(candle['open'])
                high_price = float(candle['high'])
                low_price = float(candle['low'])
                close_price = float(candle['close'])
                volume = int(candle.get('volume', 0))
            else:
                continue
            
            # Parse timestamp (Zerodha returns in IST format: 2019-12-04T09:15:00+0530)
            try:
                # Use pandas to parse ISO format timestamp (handles timezones automatically)
                timestamp = pd.to_datetime(timestamp_str)
                
                # Ensure it's in IST timezone
                if timestamp.tzinfo is None:
                    timestamp = KOLKATA_TZ.localize(timestamp)
                else:
                    # Convert to IST if it has timezone info
                    timestamp = timestamp.astimezone(KOLKATA_TZ)
                
                records.append({
                    'timestamp': timestamp,
                    'open': open_price,
                    'high': high_price,
                    'low': low_price,
                    'close': close_price,
                    'volume': volume
                })
            except Exception as e:
                ComponentLogger.get_logger("zerodha_historical").warning(
                    f"Skipping invalid candle: {candle}, error: {e}"
                )
                continue
        
        df = pd.DataFrame(records)
        if df.empty:
            return df
        
        # Sort by timestamp (oldest first)
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        return df
        
    except Exception as e:
        ComponentLogger.get_logger("zerodha_historical").error(
            f"Error fetching historical data chunk: {e}", exc_info=True
        )
        return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])


def fetch_historical_candles(
    kite,
    instrument_token: int,
    interval: str,
    from_date: datetime,
    to_date: datetime,
    continuous: bool = True,
    oi: bool = False,
    progress_callback=None
) -> pd.DataFrame:
    """
    Fetch historical candles from Zerodha API in chunks (handles API limits).
    
    API Limits:
    - 5minute: 100 days max
    - 15minute: 200 days max
    - 60minute: 200 days max (doesn't support continuous)
    - continuous=1 only works with 'day' interval
    
    Args:
        kite: Authenticated KiteConnect instance
        instrument_token: Instrument token for the contract
        interval: Candle interval ('5minute', '15minute', '60minute', 'day')
        from_date: Start date (datetime in IST)
        to_date: End date (datetime in IST)
        continuous: Use continuous data (only for 'day' interval)
        oi: Include OI data
        progress_callback: Optional callback function(progress_task, description, advance)
        
    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
    """
    # Determine API limits based on interval
    interval_map = {
        '5min': ('5minute', 100),  # 100 days max
        '15min': ('15minute', 200),  # 200 days max
        '1hour': ('60minute', 200),  # 200 days max, no continuous
        '1hr': ('60minute', 200),
        'hour': ('60minute', 200),
        '60minute': ('60minute', 200),
        'day': ('day', 365),  # Can use continuous for full year
    }
    
    api_interval, max_days = interval_map.get(interval, (interval, 200))
    
    # For intraday intervals (not 'day'), continuous doesn't work
    use_continuous = continuous and (api_interval == 'day')
    
    # Calculate total days
    total_days = (to_date - from_date).days
    
    # If within limit, fetch in one go
    if total_days <= max_days:
        if progress_callback:
            progress_callback("Fetching data...", 50)
        
        df = fetch_historical_candles_chunk(
            kite=kite,
            instrument_token=instrument_token,
            interval=api_interval,
            from_date=from_date,
            to_date=to_date,
            continuous=use_continuous,
            oi=oi
        )
        
        if progress_callback:
            progress_callback("Data received", 50)
        
        return df
    
    # Fetch in chunks
    all_data = []
    current_date = from_date
    chunk_number = 0
    total_chunks = (total_days + max_days - 1) // max_days  # Ceiling division
    
    while current_date < to_date:
        chunk_number += 1
        chunk_end = min(current_date + timedelta(days=max_days), to_date)
        
        if progress_callback:
            progress_callback(
                f"Fetching chunk {chunk_number}/{total_chunks} ({current_date.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')})...",
                int((chunk_number - 1) * 100 / total_chunks)
            )
        
        # Fetch chunk
        chunk_df = fetch_historical_candles_chunk(
            kite=kite,
            instrument_token=instrument_token,
            interval=api_interval,
            from_date=current_date,
            to_date=chunk_end,
            continuous=use_continuous,  # Only works for 'day'
            oi=oi
        )
        
        if not chunk_df.empty:
            all_data.append(chunk_df)
        
        # Move to next chunk
        current_date = chunk_end
        
        # Small delay to avoid rate limits
        import time
        time.sleep(0.1)
    
    if progress_callback:
        progress_callback("Combining chunks...", 90)
    
    # Combine all chunks
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        # Remove duplicates (in case of overlap)
        combined_df = combined_df.drop_duplicates(subset=['timestamp'], keep='first')
        # Sort by timestamp
        combined_df = combined_df.sort_values('timestamp').reset_index(drop=True)
        
        if progress_callback:
            progress_callback("Data combined", 100)
        
        return combined_df
    else:
        return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])


def store_candles_to_db(
    db_path: Path,
    symbol: str,
    timeframe: str,
    df: pd.DataFrame,
    table_name: str = "zerodha_candles"
) -> bool:
    """
    Store candles to specified table.
    
    Args:
        db_path: Path to SQLite database
        symbol: Trading symbol (e.g., "BANKNIFTY25NOVFUT")
        timeframe: Timeframe ('5min', '15min', '1hour')
        df: DataFrame with candles
        table_name: Table name to store data (default: ohlcv_zerodha)
        
    Returns:
        True if successful, False otherwise
    """
    import sqlite3
    
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Ensure table exists
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                timestamp INTEGER,
                symbol TEXT,
                timeframe TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                PRIMARY KEY (timestamp, symbol, timeframe)
            )
            """
        )
        
        # Create indexes
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS idx_timestamp_{table_name} ON {table_name}(timestamp)"
        )
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS idx_symbol_timeframe_{table_name} ON {table_name}(symbol, timeframe)"
        )
        
        # Insert or replace candles
        rows_inserted = 0
        for _, row in df.iterrows():
            timestamp_int = int(row['timestamp'].timestamp())
            cursor.execute(
                f"""
                INSERT OR REPLACE INTO {table_name} 
                (timestamp, symbol, timeframe, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp_int,
                    symbol,
                    timeframe,
                    row['open'],
                    row['high'],
                    row['low'],
                    row['close'],
                    row['volume']
                )
            )
            rows_inserted += 1
        
        conn.commit()
        conn.close()
        
        ComponentLogger.get_logger("zerodha_historical").info(
            f"Stored {rows_inserted} candles to DB",
            symbol=symbol,
            timeframe=timeframe,
            table=table_name
        )
        
        return True
        
    except Exception as e:
        ComponentLogger.get_logger("zerodha_historical").error(
            f"Error storing candles to DB: {e}", exc_info=True
        )
        return False


def main():
    """Main entry point"""
    print("=" * 70)
    print("🚀 ZERODHA HISTORICAL DATA FETCHER")
    print("=" * 70)
    print()
    
    # Setup logging
    setup_logging(log_dir=PROJECT_ROOT / "logs")
    logger = ComponentLogger.get_logger("zerodha_historical")
    
    # Load configuration
    app_config = AppConfig()
    data_config = app_config.data
    
    print(f"📁 Database: {app_config.resolve_path(data_config.db_path)}")
    print()
    
    # Load Zerodha credentials from .env
    env_path = PROJECT_ROOT / "configs" / ".env"
    if not env_path.exists():
        print(f"❌ Config file not found: {env_path}")
        return 1
    
    load_dotenv(env_path)
    logger.info(f"Loaded credentials from {env_path}")
    
    api_key = os.getenv("ZERODHA_API_KEY")
    api_secret = os.getenv("ZERODHA_API_SECRET")
    
    if not api_key or not api_secret:
        print("❌ ZERODHA_API_KEY or ZERODHA_API_SECRET not found in configs/.env")
        return 1
    
    # Authenticate with Zerodha
    print("🔐 Authenticating with Zerodha...")
    credentials = ZerodhaCredentials(api_key=api_key, api_secret=api_secret)
    token_file_path = PROJECT_ROOT / "configs" / "zerodha_tokens.json"
    zerodha_auth = ZerodhaAuthenticator(
        credentials=credentials,
        token_file=str(token_file_path),
        logger=logger
    )
    
    if not zerodha_auth.login(auto_open_browser=False):
        print("❌ Authentication failed. Please authenticate first.")
        print("   Run: python scripts/zerodha_login.py")
        return 1
    
    if zerodha_auth.connection_status != ConnectionStatus.CONNECTED:
        print("❌ Not authenticated. Please authenticate first.")
        print("   Run: python scripts/zerodha_login.py")
        return 1
    
    kite = zerodha_auth.get_kite_instance()
    if not kite:
        print("❌ Failed to get KiteConnect instance")
        return 1
    
    profile = kite.profile()
    print(f"✅ Authenticated as: {profile.get('user_name', 'N/A')} ({profile.get('user_id', 'N/A')})")
    print()
    
    # Fetch current month futures symbol and token
    print("📊 Fetching current month BankNifty futures contract...")
    try:
        futures_symbol, futures_token = get_current_month_futures_symbol_and_token(kite)
        
        if not futures_symbol or not futures_token:
            print("❌ Failed to fetch current month futures contract from Zerodha")
            logger.error("No futures contract found")
            return 1
        
        print(f"✅ Found: {futures_symbol} (Token: {futures_token})")
        print()
        
    except Exception as e:
        print(f"❌ Error fetching futures contract: {e}")
        logger.error(f"Error fetching futures contract: {e}", exc_info=True)
        return 1
    
    # Calculate date range (1st of current month to today, including today)
    now = datetime.now(KOLKATA_TZ)
    from_date = datetime(now.year, now.month, 1, 9, 15, 0, tzinfo=KOLKATA_TZ)  # 1st of current month at market open
    to_date = now  # Include all data up to current moment (includes today)
    
    month_name = from_date.strftime('%B %Y')
    today_date = now.strftime('%Y-%m-%d')
    
    print(f"📅 Date range: {from_date.strftime('%Y-%m-%d %H:%M:%S %Z')} to {to_date.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"   Fetching {month_name} data (including today: {today_date})")
    print(f"   Contract: Current month's expiry ({futures_symbol})")
    print()
    
    # Only fetch 15min data (system requirement)
    timeframes = [
        ('15min', '15minute'),
    ]
    
    db_path = Path(data_config.db_path)
    table_name = "ohlcv_zerodha"  # Store in ohlcv_zerodha table (same as LiveDataManager uses)
    
    print(f"📈 Fetching historical data...")
    print(f"   Contract: {futures_symbol}")
    print(f"   Table: {table_name}")
    print(f"   Month: {month_name}")
    print("    This may take a few minutes...")
    print()
    
    results = []
    
    # Use Rich progress bar for overall progress
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False
    ) as progress:
        
        # Create overall task
        overall_task = progress.add_task(
            "[cyan]Fetching all timeframes...",
            total=len(timeframes)
        )
        
        for idx, (tf_display, tf_api) in enumerate(timeframes, 1):
            # Create task for current timeframe
            tf_task = progress.add_task(
                f"[yellow]Fetching {tf_display} candles...",
                total=100
            )
            
            try:
                # Update progress - starting fetch
                progress.update(tf_task, advance=5, description=f"[yellow]Starting fetch for {tf_display}...")
                
                # Create progress callback for chunked fetching
                # The callback is called with (description, advance_percentage)
                last_progress = 5  # Track last progress value
                
                def update_progress(desc, advance_val):
                    nonlocal last_progress
                    # advance_val is 0-100, scale to 5-90% range for fetching
                    if advance_val == 0:
                        # Just update description
                        progress.update(tf_task, description=f"[yellow]{desc}")
                    else:
                        # Calculate target progress (5% to 90%)
                        target_progress = 5 + int((advance_val / 100) * 85)  # 5 to 90 range
                        # Calculate incremental advance
                        increment = target_progress - last_progress
                        if increment > 0:
                            progress.update(tf_task, advance=increment, description=f"[yellow]{desc}")
                            last_progress = target_progress
                        else:
                            # Just update description if no progress change
                            progress.update(tf_task, description=f"[yellow]{desc}")
                
                # Fetch historical data (will automatically chunk based on API limits)
                # Note: continuous only works for 'day' interval, so it's disabled for intraday
                df = fetch_historical_candles(
                    kite=kite,
                    instrument_token=futures_token,
                    interval=tf_display,  # Use display name, function will map to API format
                    from_date=from_date,
                    to_date=to_date,
                    continuous=False,  # Only works for 'day' interval, disabled for intraday
                    oi=False,
                    progress_callback=update_progress
                )
                
                if df.empty:
                    progress.update(tf_task, completed=100, description=f"[red]⚠️  No data received for {tf_display}")
                    console.print(f"      ⚠️  No data received for {tf_display}")
                    results.append((tf_display, False, 0))
                    progress.remove_task(tf_task)
                    progress.update(overall_task, advance=1)
                    continue
                
                # Update progress to 90% after fetching
                progress.update(tf_task, advance=10, description=f"[green]✅ Received {len(df)} {tf_display} candles")
                console.print(f"      ✅ Received {len(df)} {tf_display} candles")
                
                # Store to database
                progress.update(tf_task, advance=5, description=f"[yellow]Storing {tf_display} candles to database...")
                
                if store_candles_to_db(db_path, futures_symbol, tf_display, df, table_name=table_name):
                    progress.update(tf_task, completed=100, description=f"[green]✅ Completed {tf_display}")
                    console.print(f"      ✅ Stored {len(df)} candles to {table_name} table")
                    results.append((tf_display, True, len(df)))
                else:
                    progress.update(tf_task, completed=100, description=f"[red]❌ Failed to store {tf_display}")
                    console.print(f"      ❌ Failed to store {tf_display} candles")
                    results.append((tf_display, False, len(df)))
                
                progress.remove_task(tf_task)
                progress.update(overall_task, advance=1)
                
            except Exception as e:
                progress.update(tf_task, completed=100, description=f"[red]❌ Error fetching {tf_display}")
                console.print(f"      ❌ Error fetching {tf_display}: {e}")
                logger.error(f"Error fetching {tf_display}: {e}", exc_info=True)
                results.append((tf_display, False, 0))
                progress.remove_task(tf_task)
                progress.update(overall_task, advance=1)
            
            print()
    
    # Summary
    print("=" * 70)
    print("📊 FETCH SUMMARY")
    print("=" * 70)
    
    for tf, success, count in results:
        status = "✅" if success else "❌"
        print(f"{status} {tf.upper():10} | {'Success' if success else 'Failed':10} | {count:6} candles")
    
    total_candles = sum(count for _, _, count in results)
    successful = sum(1 for _, success, _ in results if success)
    
    print()
    print(f"Total candles fetched: {total_candles}")
    print(f"Successful timeframes: {successful}/{len(timeframes)}")
    
    if successful == len(timeframes):
        print()
        print("=" * 70)
        print("✨ ALL DATA FETCHED SUCCESSFULLY!")
        print("=" * 70)
    else:
        print()
        print("=" * 70)
        print("⚠️  SOME FETCHES FAILED")
        print("=" * 70)
    
    return 0 if successful == len(timeframes) else 1


if __name__ == "__main__":
    sys.exit(main())

