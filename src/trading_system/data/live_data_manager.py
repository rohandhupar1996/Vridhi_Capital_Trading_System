"""
Live Data Manager for Real-Time Trading
Efficient rolling buffer system for incremental bar updates

Key features:
- Keeps max_bars_back bars in memory (rolling window)
- Incremental updates: add new bar, drop oldest if exceeds limit
- Fast: No DB query per bar, only on startup/gaps
- Multi-timeframe support (5min, 15min, 1hr)
- Automatic DB persistence
"""

from __future__ import annotations

import sqlite3
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import pytz

from ..config import DataStoreConfig
from ..logging import ComponentLogger

KOLKATA_TZ = pytz.timezone("Asia/Kolkata")


@dataclass
class OHLCVBar:
    """Single OHLCV candle bar"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

    def to_dict(self) -> dict:
        return {
            'timestamp': int(self.timestamp.timestamp()),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume
        }


class LiveDataManager:
    """
    Efficient rolling buffer for live trading data.
    Keeps max_bars_back bars in memory for fast ML calculations.
    Stores to zerodha table in database.
    """
    
    def __init__(
        self,
        config: DataStoreConfig,
        symbol: str = "BANKNIFTY1!",
        timeframe: str = "15min",
        max_bars_back: int = 3000,
        use_zerodha_table: bool = True,
        logger: Optional[ComponentLogger] = None
    ):
        self.config = config
        self.symbol = symbol
        self.timeframe = timeframe
        self.max_bars_back = max_bars_back
        self.use_zerodha_table = use_zerodha_table
        self.logger = logger or ComponentLogger.get_logger("live_data_manager")
        
        # Rolling buffer: keep last max_bars_back bars in memory
        self._buffer: deque[OHLCVBar] = deque(maxlen=max_bars_back)
        
        # Database path
        self.db_path = Path(config.db_path)
        self._conn: Optional[sqlite3.Connection] = None
        
        # Table name based on source
        self.table_name = "ohlcv_zerodha" if use_zerodha_table else "ohlcv"
        
    def initialize(self) -> bool:
        """Load initial data from DB into memory buffer"""
        try:
            # Ensure database directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            self._conn = sqlite3.connect(self.db_path)
            cursor = self._conn.cursor()
            
            # Ensure table exists (create if not exists)
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
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
            
            # Create index if not exists
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS idx_timestamp_{self.table_name} "
                f"ON {self.table_name}(timestamp)"
            )
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS idx_symbol_timeframe_{self.table_name} "
                f"ON {self.table_name}(symbol, timeframe)"
            )
            self._conn.commit()
            
            # Load last max_bars_back bars from DB
            query = f"""
                SELECT timestamp, open, high, low, close, volume
                FROM {self.table_name}
                WHERE symbol = ? AND timeframe = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """
            
            df = pd.read_sql_query(
                query, 
                self._conn, 
                params=(self.symbol, self.timeframe, self.max_bars_back)
            )
            
            if df.empty:
                self.logger.warning("No historical data found, starting with empty buffer")
                return True
            
            # Convert to OHLCVBar objects (oldest first)
            df = df.iloc[::-1].reset_index(drop=True)
            for _, row in df.iterrows():
                ts = pd.to_datetime(row['timestamp'], unit='s', utc=True)
                ts = ts.tz_convert(KOLKATA_TZ)
                bar = OHLCVBar(
                    timestamp=ts.to_pydatetime(),
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=int(row['volume'])
                )
                self._buffer.append(bar)
            
            self.logger.info(
                f"Initialized buffer",
                bars=len(self._buffer),
                start=self._buffer[0].timestamp.isoformat() if self._buffer else None,
                end=self._buffer[-1].timestamp.isoformat() if self._buffer else None
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize: {e}", exc_info=True)
            return False
    
    def add_new_bar(
        self, 
        timestamp: datetime,
        open: float,
        high: float,
        low: float,
        close: float,
        volume: int = 0
    ) -> bool:
        """
        Add new bar to buffer (incremental update).
        
        - Automatically drops oldest if buffer exceeds max_bars_back
        - Stores to DB immediately
        - Fast: O(1) append operation
        """
        try:
            bar = OHLCVBar(
                timestamp=timestamp,
                open=open,
                high=high,
                low=low,
                close=close,
                volume=volume
            )
            
            # Add to rolling buffer (deque automatically manages size)
            self._buffer.append(bar)
            
            # Store to DB
            self._store_bar_to_db(bar)
            
            self.logger.debug(
                f"Added new bar",
                timestamp=timestamp.isoformat(),
                close=close,
                buffer_size=len(self._buffer)
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add bar: {e}", exc_info=True)
            return False
    
    def _store_bar_to_db(self, bar: OHLCVBar) -> None:
        """Store single bar to database (async-friendly)"""
        if not self._conn:
            return
        
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                f"""
                INSERT OR REPLACE INTO {self.table_name} 
                (timestamp, symbol, timeframe, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(bar.timestamp.timestamp()),
                    self.symbol,
                    self.timeframe,
                    bar.open,
                    bar.high,
                    bar.low,
                    bar.close,
                    bar.volume
                )
            )
            self._conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to store bar to DB: {e}")
    
    def get_dataframe(self) -> pd.DataFrame:
        """
        Get current buffer as DataFrame for ML calculations.
        
        Fast: Just converts in-memory buffer to DataFrame (no DB query)
        """
        if not self._buffer:
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        data = [bar.to_dict() for bar in self._buffer]
        df = pd.DataFrame(data)
        
        # Convert timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
        df['timestamp'] = df['timestamp'].dt.tz_convert(KOLKATA_TZ)
        
        return df
    
    def get_numpy_arrays(self) -> dict[str, np.ndarray]:
        """
        Get data as numpy arrays for fast ML calculations.
        
        Returns:
            Dict with 'high', 'low', 'close' as numpy arrays
        """
        if not self._buffer:
            n = 0
            return {
                'high': np.array([]),
                'low': np.array([]),
                'close': np.array([]),
                'timestamp': np.array([])
            }
        
        n = len(self._buffer)
        high = np.zeros(n)
        low = np.zeros(n)
        close = np.zeros(n)
        timestamps = []
        
        for i, bar in enumerate(self._buffer):
            high[i] = bar.high
            low[i] = bar.low
            close[i] = bar.close
            timestamps.append(bar.timestamp)
        
        return {
            'high': high,
            'low': low,
            'close': close,
            'timestamp': np.array(timestamps)
        }
    
    def get_buffer_size(self) -> int:
        """Get current buffer size"""
        return len(self._buffer)
    
    def get_latest_bar(self) -> Optional[OHLCVBar]:
        """Get the most recent bar from buffer"""
        if not self._buffer:
            return None
        return self._buffer[-1]
    
    def close(self) -> None:
        """Close database connection"""
        if self._conn:
            self._conn.close()
            self._conn = None

