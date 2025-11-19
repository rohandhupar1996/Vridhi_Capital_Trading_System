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
        """Load initial data from DB into memory buffer (symbol-specific)"""
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
            
            # Load last max_bars_back bars from DB (symbol-specific)
            if self.symbol:
                query = f"""
                    SELECT timestamp, open, high, low, close, volume
                    FROM {self.table_name}
                    WHERE symbol = ? AND timeframe = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """
                params = (self.symbol, self.timeframe, self.max_bars_back)
            else:
                # Empty symbol means contract-agnostic loading
                query = f"""
                    SELECT timestamp, open, high, low, close, volume
                    FROM {self.table_name}
                    WHERE timeframe = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """
                params = (self.timeframe, self.max_bars_back)
            
            df = pd.read_sql_query(query, self._conn, params=params)
            
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
                symbol=self.symbol or "ANY",
                start=self._buffer[0].timestamp.isoformat() if self._buffer else None,
                end=self._buffer[-1].timestamp.isoformat() if self._buffer else None
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize: {e}", exc_info=True)
            return False
    
    def initialize_contract_agnostic(self) -> bool:
        """
        Load historical data by timeframe only (ignores symbol for continuity across contract rollovers)
        
        This allows seamless continuation when contracts rollover (e.g., NOV → DEC).
        Data from any symbol with the same timeframe is loaded.
        """
        # Temporarily clear symbol for contract-agnostic loading
        original_symbol = self.symbol
        self.symbol = ""  # Empty symbol triggers contract-agnostic query
        
        try:
            success = self.initialize()
            return success
        finally:
            # Restore original symbol (will be updated later with update_symbol())
            self.symbol = original_symbol
    
    def update_symbol(self, new_symbol: str) -> None:
        """
        Update symbol after contract rollover
        
        Args:
            new_symbol: New futures symbol (e.g., "BANKNIFTY25DECFUT")
        """
        old_symbol = self.symbol
        self.symbol = new_symbol
        
        self.logger.info(
            f"Symbol updated",
            old_symbol=old_symbol or "NONE",
            new_symbol=new_symbol
        )
    
    def check_and_update_contract_rollover(self, kite) -> bool:
        """
        Check contract expiry from option chain and update symbol if rollover needed.
        
        Rollover Logic:
        - Gets expiry date from option chain (BANKNIFTY CE/PE options) - source of truth
        - If today is AFTER expiry date, switch to next contract
        - Example: Nov expiry on Nov 25 (from option chain), on Nov 26 switch to DEC
        - NO hardcoded day of week - uses actual expiry date from option chain
        
        Args:
            kite: Authenticated KiteConnect instance
            
        Returns:
            True if rollover happened, False otherwise
        """
        try:
            from .zerodha_futures_utils import get_futures_symbol_with_rollover
            
            # Get symbol with rollover logic (uses option chain expiry)
            new_symbol, new_token, expiry_date = get_futures_symbol_with_rollover(kite)
            
            if not new_symbol:
                self.logger.warning("Could not get futures symbol with rollover")
                return False
            
            # Check if symbol needs to be updated
            if new_symbol != self.symbol:
                old_symbol = self.symbol
                self.update_symbol(new_symbol)
                
                self.logger.info(
                    f"Contract rollover executed",
                    old_symbol=old_symbol or "NONE",
                    new_symbol=new_symbol,
                    expiry_date=expiry_date.isoformat() if expiry_date else "UNKNOWN",
                    reason="Expiry passed, switched to next contract"
                )
                return True
            else:
                # Same symbol, no rollover needed
                self.logger.debug(
                    f"No rollover needed",
                    current_symbol=self.symbol,
                    expiry_date=expiry_date.isoformat() if expiry_date else "UNKNOWN"
                )
                return False
                
        except Exception as e:
            self.logger.error(f"Error checking contract rollover: {e}", exc_info=True)
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

