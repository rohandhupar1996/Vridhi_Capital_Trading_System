"""
TradingView historical data ingestion utilities.

This module wraps the imperative script logic from
`scripts/fetch_historical_data.py` into reusable classes so other
components (tests, CLIs, services) can orchestrate data pulls without
duplicating code.
"""

from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
from dotenv import load_dotenv
from tvDatafeed import Interval, TvDatafeed

from ..config import DataStoreConfig


@dataclass(slots=True)
class TimeframeRequest:
    """Simple descriptor for a data pull request."""

    name: str
    interval: Interval
    bars: int = 10_000


class HistoricalDataCollector:
    """Orchestrates database setup and TradingView downloads."""

    def __init__(self, config: DataStoreConfig):
        self._config = config
        self._db_path = config.db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._tv: Optional[TvDatafeed] = None
        self._load_env_credentials()

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------
    def _load_env_credentials(self) -> None:
        """Attempt to populate username/password from .env files."""
        project_root = self._config.project_root or Path.cwd()
        env_loaded = False
        for env_path in self._config.env_paths:
            full_path = (project_root / env_path).resolve()
            if full_path.exists():
                load_dotenv(full_path, override=True)
                env_loaded = True

        if not self._config.tv_username:
            self._config.tv_username = os.getenv("TV_USERNAME")
        if not self._config.tv_password:
            self._config.tv_password = os.getenv("TV_PASSWORD")

    def setup_database(self) -> None:
        """Ensure tables and indices exist."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path)
        cursor = self._conn.cursor()

        cursor.execute(
            """
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
            """
        )

        # Separate table for Zerodha BankNifty futures data
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ohlcv_zerodha (
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
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at DATETIME
            )
            """
        )

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON ohlcv(timestamp)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_symbol_timeframe "
            "ON ohlcv(symbol, timeframe)"
        )
        
        # Indexes for Zerodha table
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp_zerodha ON ohlcv_zerodha(timestamp)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_symbol_timeframe_zerodha "
            "ON ohlcv_zerodha(symbol, timeframe)"
        )
        self._conn.commit()

    def connect_tradingview(self, username: Optional[str] = None, password: Optional[str] = None) -> bool:
        """
        Establish a tvDatafeed session.
        
        Args:
            username: Optional username override (if not provided, uses config)
            password: Optional password override (if not provided, uses config)
        
        Returns:
            True if successfully logged in, False if using no-login mode
        """
        # Use provided credentials or fall back to config
        username = username or self._config.tv_username
        password = password or self._config.tv_password
        
        if not username or not password:
            print("⚠️  No credentials provided, using no-login mode")
            try:
                self._tv = TvDatafeed()  # anonymous session fallback
                return False  # Return False to indicate no-login mode
            except Exception as e:
                print(f"❌ Failed to create anonymous session: {e}")
                return False
        
        try:
            print(f"🔐 Attempting login with username: {username}")
            # Pass credentials directly to TvDatafeed
            self._tv = TvDatafeed(username=username, password=password)
            
            # Verify actual login status by checking for token/session
            is_logged_in = self._verify_login_status()
            if is_logged_in:
                print("✅ Successfully logged in to TradingView (verified)")
            else:
                print("⚠️  Login failed - credentials rejected by TradingView")
                print("   Falling back to no-login mode. Data access may be limited.")
                print("   💡 Possible reasons:")
                print("      - Incorrect username/password")
                print("      - Account requires 2FA (tvDatafeed may not support 2FA)")
                print("      - Account locked/suspended")
                print("      - Try: python scripts/test_tradingview_login.py to test credentials")
            return is_logged_in
        except Exception as e:
            print(f"❌ Login error: {type(e).__name__}: {e}")
            print("⚠️  Falling back to no-login mode")
            try:
                self._tv = TvDatafeed()  # anonymous session fallback
                return False  # Return False to indicate no-login mode
            except Exception as fallback_error:
                print(f"❌ Failed to create anonymous session: {fallback_error}")
                return False

    def _verify_login_status(self) -> bool:
        """Verify if actually logged in by checking token/session."""
        if not self._tv:
            return False
        try:
            # Check if token exists (indicates logged-in session)
            token = getattr(self._tv, 'token', None)
            session = getattr(self._tv, 'session', None)
            
            # Check if token exists and is not the default unauthorized token
            if token is not None:
                token_str = str(token).strip()
                # "unauthorized_user_token" indicates failed login/no-login mode
                if token_str == 'unauthorized_user_token' or token_str == '':
                    return False
            
            # If we have a valid-looking token, we're logged in
            has_valid_token = token is not None and str(token).strip() != '' and str(token) != 'unauthorized_user_token'
            has_session = session is not None and session != ''
            
            return has_valid_token or has_session
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Data operations
    # ------------------------------------------------------------------
    def fetch_timeframes(
        self,
        symbol: str,
        exchange: str,
        requests: Iterable[TimeframeRequest],
        overwrite: bool = True,
        sleep_between: float = 5.0,
    ) -> list[tuple[str, bool]]:
        """Fetch all requested timeframes and store them in SQLite."""
        if not self._conn:
            raise RuntimeError("Database not initialised. Call setup_database() first.")
        if not self._tv:
            raise RuntimeError("TradingView client not connected.")

        request_list = list(requests)
        results: list[tuple[str, bool]] = []
        for idx, req in enumerate(request_list):
            success = self._fetch_single(symbol, exchange, req, overwrite=overwrite)
            results.append((req.name, success))
            if sleep_between and idx < len(request_list) - 1:
                time.sleep(sleep_between)
        return results

    def _fetch_single(
        self,
        symbol: str,
        exchange: str,
        request: TimeframeRequest,
        overwrite: bool = True,
    ) -> bool:
        """Fetch and persist one timeframe."""
        assert self._tv is not None
        assert self._conn is not None

        print(f"  📥 Fetching {request.name}: requesting {request.bars} bars...")
        df = self._tv.get_hist(
            symbol=symbol,
            exchange=exchange,
            interval=request.interval,
            n_bars=request.bars,
        )
        if df is None or df.empty:
            print(f"  ❌ No data returned for {request.name}")
            return False

        df = df.reset_index()
        df["symbol"] = symbol
        df["timeframe"] = request.name
        df.rename(columns={"datetime": "timestamp"}, inplace=True)
        
        # Convert timestamp to datetime if it's not already
        if isinstance(df["timestamp"].iloc[0], (int, float)):
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit='s')
        
        df = df[
            [
                "timestamp",
                "symbol",
                "timeframe",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]
        ]

        # Validate data completeness before saving
        received_bars = len(df)
        requested_bars = request.bars
        latest_date = df["timestamp"].max()
        earliest_date = df["timestamp"].min()
        
        # Check for data gaps
        df_sorted = df.sort_values("timestamp").reset_index(drop=True)
        gaps = self._detect_gaps(df_sorted, request.name)
        
        print(f"  ✅ Received {received_bars} bars (requested {requested_bars})")
        print(f"     Date range: {earliest_date.date()} to {latest_date.date()}")
        if gaps:
            print(f"     ⚠️  Warning: {len(gaps)} gap(s) detected in data")
        else:
            print(f"     ✓ No gaps detected")
        
        if received_bars < requested_bars * 0.9:  # Less than 90% of requested
            print(f"     ⚠️  Warning: Received less than 90% of requested bars!")

        cursor = self._conn.cursor()
        if overwrite:
            cursor.execute(
                "DELETE FROM ohlcv WHERE symbol = ? AND timeframe = ?",
                (symbol, request.name),
            )
        df.to_sql("ohlcv", self._conn, if_exists="append", index=False)
        self._conn.commit()

        cursor.execute(
            """
            INSERT OR REPLACE INTO metadata (key, value, updated_at)
            VALUES (?, ?, ?)
            """,
            (
                f"{symbol}_{request.name}_last_updated",
                df["timestamp"].max().isoformat(),
                datetime.now().isoformat(),
            ),
        )
        self._conn.commit()
        return True
    
    def _detect_gaps(self, df: pd.DataFrame, timeframe: str) -> list[tuple]:
        """Detect gaps in time series data."""
        if len(df) < 2:
            return []
        
        # Calculate expected interval in seconds based on timeframe
        interval_seconds = {
            "5min": 300,
            "15min": 900,
            "1hour": 3600,
            "1day": 86400,
        }.get(timeframe, 900)  # default to 15min
        
        gaps = []
        timestamps = df["timestamp"].values
        
        for i in range(1, len(timestamps)):
            time_diff = (pd.Timestamp(timestamps[i]) - pd.Timestamp(timestamps[i-1])).total_seconds()
            # Allow small tolerance (10% extra) for missing bars
            expected_interval = interval_seconds * 1.1
            if time_diff > expected_interval:
                gaps.append((timestamps[i-1], timestamps[i], time_diff))
        
        return gaps

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def statistics(self) -> pd.DataFrame:
        """Return a DataFrame describing stored data coverage."""
        if not self._conn:
            raise RuntimeError("Database not initialised. Call setup_database() first.")
        query = (
            "SELECT timeframe, COUNT(*) as bars, "
            "MIN(timestamp) as start_ts, MAX(timestamp) as end_ts "
            "FROM ohlcv GROUP BY timeframe ORDER BY timeframe"
        )
        return pd.read_sql_query(query, self._conn)
    
    def validate_data_completeness(
        self, symbol: str, timeframe: str, expected_bars: int
    ) -> dict:
        """Validate data completeness for a specific symbol/timeframe."""
        if not self._conn:
            raise RuntimeError("Database not initialised. Call setup_database() first.")
        
        query = """
            SELECT timestamp, open, high, low, close, volume
            FROM ohlcv 
            WHERE symbol = ? AND timeframe = ?
            ORDER BY timestamp
        """
        df = pd.read_sql_query(query, self._conn, params=(symbol, timeframe))
        
        if df.empty:
            return {
                "valid": False,
                "reason": "No data found",
                "received_bars": 0,
                "expected_bars": expected_bars,
            }
        
        # Convert timestamp - SQLite stores as INTEGER (Unix seconds) or TEXT (ISO format)
        # Check if it's numeric (int, float, numpy.int64, etc.)
        first_ts = df["timestamp"].iloc[0]
        if pd.api.types.is_numeric_dtype(df["timestamp"]):
            # It's a numeric type (stored as Unix timestamp in seconds)
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit='s')
        elif isinstance(first_ts, str):
            # It's a string (stored as ISO format)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        else:
            # Already datetime object
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        
        received_bars = len(df)
        latest_date = df["timestamp"].max()
        earliest_date = df["timestamp"].min()
        today = pd.Timestamp.now().normalize()
        
        # Check if latest date is today or yesterday (for intraday data)
        latest_date_normalized = latest_date.normalize()
        is_up_to_date = (today - latest_date_normalized).days <= 1
        
        # Detect gaps
        gaps = self._detect_gaps(df, timeframe)
        
        return {
            "valid": received_bars >= expected_bars * 0.9 and is_up_to_date and len(gaps) == 0,
            "received_bars": received_bars,
            "expected_bars": expected_bars,
            "completeness_percent": (received_bars / expected_bars * 100) if expected_bars > 0 else 0,
            "earliest_date": earliest_date,
            "latest_date": latest_date,
            "is_up_to_date": is_up_to_date,
            "gaps_count": len(gaps),
            "gaps": gaps[:10],  # Return first 10 gaps
        }

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


__all__ = ["HistoricalDataCollector", "TimeframeRequest"]

