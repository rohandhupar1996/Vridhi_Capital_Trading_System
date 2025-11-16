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
        for env_path in self._config.env_paths:
            full_path = (project_root / env_path).resolve()
            if full_path.exists():
                load_dotenv(full_path)

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
        self._conn.commit()

    def connect_tradingview(self) -> bool:
        """Establish a tvDatafeed session."""
        username = self._config.tv_username
        password = self._config.tv_password
        try:
            self._tv = TvDatafeed(username, password)
            return True
        except Exception:
            self._tv = TvDatafeed()  # anonymous session fallback
            return self._tv is not None

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

        df = self._tv.get_hist(
            symbol=symbol,
            exchange=exchange,
            interval=request.interval,
            n_bars=request.bars,
        )
        if df is None or df.empty:
            return False

        df = df.reset_index()
        df["symbol"] = symbol
        df["timeframe"] = request.name
        df.rename(columns={"datetime": "timestamp"}, inplace=True)
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

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


__all__ = ["HistoricalDataCollector", "TimeframeRequest"]

