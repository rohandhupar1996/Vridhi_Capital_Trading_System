"""
Historical Data Loader
Loads historical OHLCV data from SQLite DB into RAM for ML model processing
"""

from typing import Optional
import sqlite3
import pandas as pd
from pathlib import Path

from ..logging import ComponentLogger


class HistoricalDataLoader:
    """
    Loads historical data from SQLite database into RAM
    Pre-processes and caches for fast ML model access
    """
    
    def __init__(
        self,
        db_path: Path | str,
        symbol: str = "BANKNIFTY1!",
        timeframe: str = "15min",
        lookback_bars: int = 2000,
        logger: Optional[ComponentLogger] = None
    ):
        self.db_path = Path(db_path)
        self.symbol = symbol
        self.timeframe = timeframe
        self.lookback_bars = lookback_bars
        self.logger = logger or ComponentLogger.get_logger("data_loader")
        
        self.data: Optional[pd.DataFrame] = None
    
    def load(self) -> bool:
        """
        Load historical data from database into RAM
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.db_path.exists():
                self.logger.error(f"Database not found: {self.db_path}")
                return False
            
            self.logger.info(
                f"Loading historical data",
                db=str(self.db_path),
                symbol=self.symbol,
                timeframe=self.timeframe,
                lookback=self.lookback_bars
            )
            
            conn = sqlite3.connect(self.db_path)
            
            # Load data (most recent first, then reverse)
            query = """
                SELECT timestamp, open, high, low, close, volume
                FROM ohlcv
                WHERE symbol = ? AND timeframe = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """
            
            df = pd.read_sql_query(query, conn, params=(self.symbol, self.timeframe, self.lookback_bars))
            conn.close()
            
            if df.empty:
                self.logger.error("No data found in database")
                return False
            
            # Reverse to chronological order (oldest first)
            df = df.iloc[::-1].reset_index(drop=True)
            
            # Convert timestamp
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
            df['timestamp'] = df['timestamp'].dt.tz_convert('Asia/Kolkata')
            
            # Ensure numeric types
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Remove any NaN rows
            df = df.dropna()
            
            self.data = df
            
            self.logger.info(
                f"Historical data loaded",
                bars=len(df),
                start=df['timestamp'].min().isoformat() if not df.empty else None,
                end=df['timestamp'].max().isoformat() if not df.empty else None
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load historical data: {e}", exc_info=True)
            return False
    
    def get_data(self) -> Optional[pd.DataFrame]:
        """
        Get loaded historical data
        
        Returns:
            DataFrame with historical OHLCV data, or None if not loaded
        """
        return self.data
    
    def append_current_price(self, current_price: float, current_time: Optional[pd.Timestamp] = None) -> pd.DataFrame:
        """
        Append current price to historical data for ML processing
        
        Args:
            current_price: Current futures price
            current_time: Current timestamp (defaults to now)
            
        Returns:
            Combined DataFrame with current price appended
        """
        if self.data is None or self.data.empty:
            return pd.DataFrame()
        
        if current_time is None:
            from datetime import datetime
            import pytz
            current_time = pd.Timestamp(datetime.now(pytz.timezone('Asia/Kolkata')))
        
        # Create new row with current price
        new_row = pd.DataFrame({
            'timestamp': [current_time],
            'open': [current_price],
            'high': [current_price],
            'low': [current_price],
            'close': [current_price],
            'volume': [0]  # Volume not available for real-time
        })
        
        # Append to historical data
        combined = pd.concat([self.data, new_row], ignore_index=True)
        
        return combined
    
    def is_loaded(self) -> bool:
        """Check if data is loaded"""
        return self.data is not None and not self.data.empty




