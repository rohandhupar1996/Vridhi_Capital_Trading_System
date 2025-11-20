"""
Trading State Manager
Saves and loads complete system state for Pine Script-style continuity

Saves at 3:30 PM daily:
- Re-entry state (last_long_exit_bar, last_short_exit_bar)
- Position state (direction, entry_price, entry_bar_index, atm_strike, hedge_strike)
- ML system state (features, indicators, predictions, signals)
- Historical OHLCV data (last 2000 bars)
- Futures previous close (for gap calculation)

Loads at 9:15 AM daily:
- All saved state restored seamlessly (no recalculation needed)
"""

from __future__ import annotations

from typing import Optional, Dict, Any
import sqlite3
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytz

from ..logging import ComponentLogger

KOLKATA_TZ = pytz.timezone('Asia/Kolkata')


class TradingStateManager:
    """
    Manages saving and loading complete system state
    
    Like Pine Script: Saves everything (features, indicators, state) so system
    can continue seamlessly without recalculation.
    """
    
    def __init__(
        self,
        db_path: Path | str,
        logger: Optional[ComponentLogger] = None
    ):
        """
        Initialize state manager
        
        Args:
            db_path: Path to SQLite database
            logger: Optional logger instance
        """
        self.db_path = Path(db_path)
        self.logger = logger or ComponentLogger.get_logger("state_manager")
        
        # Table name for state storage
        self.table_name = "trading_state"
        
        # Initialize database table if needed
        self._initialize_table()
    
    def _initialize_table(self) -> None:
        """Create state table if it doesn't exist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create state table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    save_time TEXT NOT NULL,
                    state_data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            
            conn.commit()
            conn.close()
            
            self.logger.debug(f"State table '{self.table_name}' initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize state table: {e}", exc_info=True)
    
    def save_daily_state(self, state: Dict[str, Any]) -> bool:
        """
        Save complete system state to database
        
        State should contain:
        - last_long_exit_bar: int
        - last_short_exit_bar: int
        - position: dict or None (direction, entry_price, entry_bar_index, atm_strike, hedge_strike)
        - ml_features: dict (f1, f2, f3, f4, f5)
        - ml_indicators: dict (filter_all, kernel_estimate, is_bullish, is_bearish)
        - ml_predictions: list
        - ml_signals: list
        - historical_data: list of dicts (OHLCV records)
        - futures_previous_close: float
        - last_processed_timestamp: str
        - save_time: str
        - data_source: str
        
        Args:
            state: Complete system state dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Add save timestamp if not present
            if 'save_time' not in state:
                state['save_time'] = datetime.now(KOLKATA_TZ).isoformat()
            
            # Serialize state to JSON
            state_json = json.dumps(state, default=str)
            
            # Save to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Delete previous state (keep only latest)
            cursor.execute(f"DELETE FROM {self.table_name}")
            
            # Insert new state
            cursor.execute(f"""
                INSERT INTO {self.table_name} (save_time, state_data, created_at)
                VALUES (?, ?, ?)
            """, (
                state['save_time'],
                state_json,
                datetime.now(KOLKATA_TZ).isoformat()
            ))
            
            conn.commit()
            conn.close()
            
            self.logger.info(
                f"✅ Daily state saved successfully",
                save_time=state['save_time'],
                has_position=state.get('position') is not None,
                historical_bars=len(state.get('historical_data', [])),
                ml_features_count=len(state.get('ml_features', {}))
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save daily state: {e}", exc_info=True)
            return False
    
    def load_saved_state(self) -> Optional[Dict[str, Any]]:
        """
        Load saved state from database
        
        Returns:
            State dictionary if found, None otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get latest state
            cursor.execute(f"""
                SELECT state_data, save_time, created_at
                FROM {self.table_name}
                ORDER BY id DESC
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            conn.close()
            
            if row is None:
                self.logger.info("No saved state found (first run or no state saved yet)")
                return None
            
            state_json, save_time, created_at = row
            
            # Deserialize JSON
            state = json.loads(state_json)
            
            self.logger.info(
                f"✅ Saved state loaded successfully",
                save_time=save_time,
                created_at=created_at,
                has_position=state.get('position') is not None,
                historical_bars=len(state.get('historical_data', [])),
                ml_features_count=len(state.get('ml_features', {}))
            )
            
            return state
            
        except Exception as e:
            self.logger.error(f"Failed to load saved state: {e}", exc_info=True)
            return None
    
    def clear_state(self) -> bool:
        """
        Clear all saved state (for testing or fresh start)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(f"DELETE FROM {self.table_name}")
            
            conn.commit()
            conn.close()
            
            self.logger.info("✅ All saved state cleared")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to clear state: {e}", exc_info=True)
            return False
    
    def has_saved_state(self) -> bool:
        """
        Check if saved state exists in database
        
        Returns:
            True if state exists, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
            count = cursor.fetchone()[0]
            
            conn.close()
            
            return count > 0
            
        except Exception as e:
            self.logger.error(f"Failed to check saved state: {e}", exc_info=True)
            return False

