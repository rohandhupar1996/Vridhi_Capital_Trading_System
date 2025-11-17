"""
Zerodha Tick to Candle Aggregator
Converts tick data from Zerodha WebSocket into OHLCV candles
Stores candles in database for 5min, 15min, 1hr timeframes
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional

import pandas as pd
import pytz

from ..config import DataStoreConfig
from ..logging import ComponentLogger
from .live_data_manager import LiveDataManager, OHLCVBar

KOLKATA_TZ = pytz.timezone("Asia/Kolkata")


@dataclass
class RunningCandle:
    """Tracks a candle that's currently forming"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    tick_count: int


class ZerodhaCandleAggregator:
    """
    Aggregates Zerodha tick data into candles for multiple timeframes.
    Manages candles in memory and stores to DB when candle closes.
    
    Automatically fetches current month BankNifty futures symbol from Zerodha.
    Stores all contracts in the same ohlcv_zerodha table for continuous data stream.
    """
    
    def __init__(
        self,
        config: DataStoreConfig,
        kite=None,  # Optional KiteConnect instance to fetch futures symbol dynamically
        symbol: Optional[str] = None,  # Optional: if provided, uses this instead of fetching
        logger: Optional[ComponentLogger] = None
    ):
        self.config = config
        self.kite = kite
        self.logger = logger or ComponentLogger.get_logger("zerodha_candle_aggregator")
        
        # Fetch current month futures symbol from Zerodha if kite provided
        if symbol:
            self.symbol = symbol
            self.logger.info(f"Using provided symbol: {symbol}")
        elif kite:
            from .zerodha_futures_utils import get_current_month_futures_symbol
            self.symbol = get_current_month_futures_symbol(kite)
            if not self.symbol:
                self.logger.error("Failed to fetch current month futures symbol from Zerodha")
                raise ValueError("Could not determine current month futures symbol")
            self.logger.info(f"Fetched current month futures symbol from Zerodha: {self.symbol}")
        else:
            # Fallback to default (for testing)
            self.symbol = "BANKNIFTY1!"
            self.logger.warning(f"No kite instance provided, using default symbol: {self.symbol}")
        
        # Live data managers for each timeframe (rolling buffers)
        # use_zerodha_table=True to store in ohlcv_zerodha table
        # All contracts stored in same table for continuous data stream
        self.managers: Dict[str, LiveDataManager] = {
            '5min': LiveDataManager(config, self.symbol, '5min', max_bars_back=3000, use_zerodha_table=True, logger=logger),
            '15min': LiveDataManager(config, self.symbol, '15min', max_bars_back=3000, use_zerodha_table=True, logger=logger),
            '1hour': LiveDataManager(config, self.symbol, '1hour', max_bars_back=3000, use_zerodha_table=True, logger=logger),
        }
        
        # Running candles for each timeframe (current candle being formed)
        self.running_candles: Dict[str, Optional[RunningCandle]] = {
            '5min': None,
            '15min': None,
            '1hour': None,
        }
        
        # Timeframe intervals in minutes
        self.intervals = {
            '5min': 5,
            '15min': 15,
            '1hour': 60,
        }
    
    def initialize(self) -> bool:
        """Initialize all data managers"""
        success = True
        for tf, manager in self.managers.items():
            if not manager.initialize():
                self.logger.error(f"Failed to initialize {tf} manager")
                success = False
        return success
    
    def on_tick(
        self,
        price: float,
        volume: int,
        timestamp: Optional[datetime] = None
    ) -> Dict[str, Optional[OHLCVBar]]:
        """
        Process new tick data and update all timeframes.
        
        Returns:
            Dict of completed candles: {'5min': OHLCVBar or None, '15min': ..., '1hour': ...}
            None means candle is still running (not closed yet)
        """
        if timestamp is None:
            timestamp = datetime.now(KOLKATA_TZ)
        else:
            if timestamp.tzinfo is None:
                timestamp = KOLKATA_TZ.localize(timestamp)
        
        completed_candles = {}
        
        for timeframe, interval_min in self.intervals.items():
            candle_start = self._get_candle_start(timestamp, interval_min)
            
            # Get or create running candle
            running = self.running_candles[timeframe]
            
            if running is None or running.timestamp != candle_start:
                # Candle closed - save previous if exists
                if running is not None:
                    completed_bar = OHLCVBar(
                        timestamp=running.timestamp,
                        open=running.open,
                        high=running.high,
                        low=running.low,
                        close=running.close,
                        volume=running.volume
                    )
                    self.managers[timeframe].add_new_bar(
                        timestamp=running.timestamp,
                        open=running.open,
                        high=running.high,
                        low=running.low,
                        close=running.close,
                        volume=running.volume
                    )
                    completed_candles[timeframe] = completed_bar
                
                # Start new candle
                self.running_candles[timeframe] = RunningCandle(
                    timestamp=candle_start,
                    open=price,
                    high=price,
                    low=price,
                    close=price,
                    volume=volume,
                    tick_count=1
                )
            else:
                # Update existing running candle
                running.high = max(running.high, price)
                running.low = min(running.low, price)
                running.close = price
                running.volume += volume
                running.tick_count += 1
                completed_candles[timeframe] = None  # Still running
        
        return completed_candles
    
    def _get_candle_start(self, timestamp: datetime, interval_min: int) -> datetime:
        """
        Calculate candle start time for given timestamp and interval.
        Handles market opening at 9:15 AM IST.
        """
        # Market opens at 9:15 AM IST
        market_open_hour = 9
        market_open_minute = 15
        
        # If before 9:15, use 9:15 as candle start
        if timestamp.hour < market_open_hour or (timestamp.hour == market_open_hour and timestamp.minute < market_open_minute):
            return timestamp.replace(hour=market_open_hour, minute=market_open_minute, second=0, microsecond=0)
        
        # Calculate total minutes since 9:15
        total_minutes_since_open = (timestamp.hour - market_open_hour) * 60 + (timestamp.minute - market_open_minute)
        
        # Round down to nearest interval
        intervals_since_open = total_minutes_since_open // interval_min
        minutes_from_open = intervals_since_open * interval_min
        
        # Calculate candle start time
        candle_start_minutes = market_open_minute + minutes_from_open
        candle_start_hour = market_open_hour + (candle_start_minutes // 60)
        candle_start_minute = candle_start_minutes % 60
        
        candle_start = timestamp.replace(hour=candle_start_hour, minute=candle_start_minute, second=0, microsecond=0)
        return candle_start
    
    def get_dataframe(self, timeframe: str) -> pd.DataFrame:
        """Get DataFrame for specific timeframe"""
        if timeframe not in self.managers:
            raise ValueError(f"Unknown timeframe: {timeframe}")
        return self.managers[timeframe].get_dataframe()
    
    def get_numpy_arrays(self, timeframe: str) -> dict:
        """Get numpy arrays for specific timeframe"""
        if timeframe not in self.managers:
            raise ValueError(f"Unknown timeframe: {timeframe}")
        return self.managers[timeframe].get_numpy_arrays()
    
    def close(self) -> None:
        """Close all managers"""
        for manager in self.managers.values():
            manager.close()

