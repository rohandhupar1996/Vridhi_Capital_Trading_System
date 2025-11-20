"""
System Recovery Module
Handles system crashes, position mismatches, data gaps, and recovery scenarios.

Recovery Flow:
1. Load last saved state
2. Check actual broker position
3. Reconcile position state
4. Detect data gaps
5. Fill data gaps (using fetch_zerodha_historical_data.py)
6. Rebuild ML state (if gaps filled)
7. Update re-entry state
"""

from __future__ import annotations

from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3

import pandas as pd
import pytz

from ..oms.order_manager import OrderManager, PositionType
from ..data.trading_state_manager import TradingStateManager
from ..logging import ComponentLogger

KOLKATA_TZ = pytz.timezone('Asia/Kolkata')


def generate_expected_timestamps(from_time: datetime, to_time: datetime, interval_min: int = 15) -> List[datetime]:
    """
    Generate expected 15min candle timestamps between from_time and to_time.
    Only during market hours: 9:15 AM to 3:30 PM IST.
    
    Args:
        from_time: Start time (datetime in IST)
        to_time: End time (datetime in IST)
        interval_min: Candle interval in minutes (default: 15)
        
    Returns:
        List of expected candle timestamps
    """
    expected = []
    current = from_time.replace(second=0, microsecond=0)
    
    # Market hours: 9:15 AM to 3:30 PM
    market_open_hour = 9
    market_open_minute = 15
    market_close_hour = 15
    market_close_minute = 30
    
    # Align to 15min boundaries (9:15, 9:30, 9:45, ...)
    if current.minute % interval_min != 15:
        # Round down to nearest 15min boundary + 15min offset
        minutes_to_subtract = (current.minute % interval_min) - 15
        if minutes_to_subtract < 0:
            minutes_to_subtract += interval_min
        current = current - timedelta(minutes=minutes_to_subtract)
    
    while current <= to_time:
        # Only include during market hours
        if (current.hour == market_open_hour and current.minute >= market_open_minute) or \
           (market_open_hour < current.hour < market_close_hour) or \
           (current.hour == market_close_hour and current.minute <= market_close_minute):
            expected.append(current)
        
        current += timedelta(minutes=interval_min)
        
        # Skip to next day if past market close
        if current.hour > market_close_hour or \
           (current.hour == market_close_hour and current.minute > market_close_minute):
            # Move to next day 9:15 AM
            current = current.replace(hour=market_open_hour, minute=market_open_minute)
            current += timedelta(days=1)
    
    return expected


def detect_data_gaps(
    saved_timestamp: Optional[str],
    current_time: datetime,
    db_path: Path,
    logger: Optional[ComponentLogger] = None
) -> List[datetime]:
    """
    Detect missing candle bars while system was down.
    
    We save every candle to database when it closes, so gaps = missing timestamps in DB.
    
    Args:
        saved_timestamp: Last processed timestamp from saved state (ISO format string)
        current_time: Current time (datetime in IST)
        db_path: Path to SQLite database
        logger: Optional logger instance
        
    Returns:
        List of missing candle timestamps (datetime objects)
    """
    if logger is None:
        logger = ComponentLogger.get_logger("system_recovery")
    
    saved_ts = datetime.fromisoformat(saved_timestamp) if saved_timestamp else None
    
    if not saved_ts:
        logger.warning("No saved timestamp - cannot detect gaps")
        return []
    
    # Calculate expected candle bars between saved_timestamp and current_time
    # 15min candles: one every 15 minutes (market hours: 9:15 AM to 3:30 PM)
    # Only check during market hours
    expected_timestamps = generate_expected_timestamps(saved_ts, current_time, interval_min=15)
    
    if not expected_timestamps:
        logger.info("No expected candles in the time range")
        return []
    
    logger.info(f"System was down - checking {len(expected_timestamps)} expected candles")
    
    # Query database for candles between saved_timestamp and current_time
    try:
        conn = sqlite3.connect(db_path)
        
        # Convert timestamps to unix timestamps for query
        from_ts_int = int(saved_ts.timestamp())
        to_ts_int = int(current_time.timestamp())
        
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT timestamp
            FROM ohlcv_zerodha
            WHERE timeframe = '15min'
            AND timestamp >= ?
            AND timestamp <= ?
            ORDER BY timestamp
            """,
            (from_ts_int, to_ts_int)
        )
        
        db_timestamps = set([row[0] for row in cursor.fetchall()])
        conn.close()
        
        # Find missing timestamps (convert expected to unix timestamps)
        missing_bars = []
        for expected_ts in expected_timestamps:
            expected_ts_int = int(expected_ts.timestamp())
            if expected_ts_int not in db_timestamps:
                missing_bars.append(expected_ts)  # Keep as datetime for fetching
        
        logger.info(f"Found {len(missing_bars)} missing candles in database")
        
        return missing_bars
        
    except Exception as e:
        logger.error(f"Error detecting data gaps: {e}", exc_info=True)
        return []


def reconcile_position(
    saved_position: Optional[Dict[str, Any]],
    broker_positions: List[Dict[str, Any]],
    oms: OrderManager,
    logger: Optional[ComponentLogger] = None
) -> Dict[str, Any]:
    """
    Reconcile position state after crash/recovery.
    
    Args:
        saved_position: Position from saved state (dict or None)
        broker_positions: Actual positions from broker (list of dicts)
        oms: OrderManager instance
        logger: Optional logger instance
        
    Returns:
        Reconciliation result dict with status and details
    """
    if logger is None:
        logger = ComponentLogger.get_logger("system_recovery")
    
    # Determine actual position from broker
    actual_position = None
    for pos in broker_positions:
        if pos.get('quantity', 0) != 0:
            # Position exists in market
            actual_position = {
                'direction': 'LONG' if pos['quantity'] > 0 else 'SHORT',
                'entry_price': pos.get('average_price', 0.0),
                'quantity': abs(pos['quantity']),
                'product': pos.get('product'),
                'instrument_token': pos.get('instrument_token')
            }
            break
    
    result = {
        'status': 'clean',
        'action': None,
        'position_restored': False,
        'details': {}
    }
    
    if actual_position and not saved_position:
        # Position exists in market but not in saved state
        # System crashed after entering position but before saving state
        logger.warning("⚠️ Position mismatch: Position exists in market but not in saved state")
        
        # Update OMS position from broker
        oms.position.position_type = PositionType.LONG if actual_position['direction'] == 'LONG' else PositionType.SHORT
        oms.position.entry_price = actual_position['entry_price']
        oms.position.lot_size = actual_position['quantity'] // 35  # BankNifty lot size = 35 (approximate)
        oms.position.entry_time = datetime.now(KOLKATA_TZ)  # We don't know exact entry time, use current
        
        # We don't know entry_bar_index - need to estimate or use current
        # Option: Use current bar index (conservative approach)
        oms.position.entry_bar_index = -1  # Will be set when data is loaded
        
        logger.info(f"✅ Recovered position from broker: {oms.position.position_type.value}")
        
        result['status'] = 'recovered_from_broker'
        result['action'] = 'restore_from_broker'
        result['position_restored'] = True
        result['details'] = {
            'direction': actual_position['direction'],
            'entry_price': actual_position['entry_price']
        }
        
    elif saved_position and not actual_position:
        # Position exists in saved state but not in market
        # Position was exited while system was down
        logger.warning("⚠️ Position mismatch: Position in saved state but not in market (exited during downtime)")
        
        # Update re-entry state from saved position's entry_bar_index
        # Exit happened while system was down - mark that bar as exit
        last_long_exit_bar = -1
        last_short_exit_bar = -1
        
        if saved_position['direction'] == 'LONG':
            last_long_exit_bar = saved_position.get('entry_bar_index', -1)  # Approximate, we don't know exact exit bar
        else:
            last_short_exit_bar = saved_position.get('entry_bar_index', -1)
        
        # Reset position
        oms.position.position_type = PositionType.NONE
        oms.position.entry_price = 0.0
        oms.position.entry_bar_index = -1
        oms.position.entry_time = None
        
        logger.info("✅ Cleared position (exited during downtime)")
        
        result['status'] = 'cleared_exited_during_downtime'
        result['action'] = 'clear_position'
        result['details'] = {
            'last_long_exit_bar': last_long_exit_bar,
            'last_short_exit_bar': last_short_exit_bar
        }
        
    elif saved_position and actual_position:
        # Both exist - check if they match
        if (saved_position['direction'] == actual_position['direction'] and
            abs(saved_position['entry_price'] - actual_position['entry_price']) < 10):  # Allow small difference
            # Positions match - use saved state (has entry_bar_index)
            logger.info("✅ Position state matches broker position")
            
            # Restore position from saved state (has more info like entry_bar_index)
            oms.position.position_type = PositionType.LONG if saved_position['direction'] == 'LONG' else PositionType.SHORT
            oms.position.entry_price = saved_position['entry_price']
            oms.position.entry_bar_index = saved_position.get('entry_bar_index', -1)
            oms.position.entry_time = datetime.fromisoformat(saved_position['entry_timestamp']) if 'entry_timestamp' in saved_position else None
            oms.position.atm_strike = saved_position.get('atm_strike')
            oms.position.hedge_strike = saved_position.get('hedge_strike')
            
            result['status'] = 'matches'
            result['action'] = 'restore_from_saved_state'
            result['position_restored'] = True
            
        else:
            # Positions don't match - use broker as source of truth
            logger.warning("⚠️ Position mismatch: Saved and broker positions differ, using broker")
            oms.position.position_type = PositionType.LONG if actual_position['direction'] == 'LONG' else PositionType.SHORT
            oms.position.entry_price = actual_position['entry_price']
            oms.position.lot_size = actual_position['quantity'] // 35
            oms.position.entry_bar_index = -1  # Unknown
            
            result['status'] = 'mismatch_using_broker'
            result['action'] = 'restore_from_broker'
            result['position_restored'] = True
            result['details'] = {
                'saved_direction': saved_position['direction'],
                'broker_direction': actual_position['direction']
            }
            
    else:
        # No position in either - system state is clean
        logger.info("✅ No position state mismatch - system clean")
        result['status'] = 'clean'
        result['action'] = None
    
    return result


def recover_system(
    state_manager: TradingStateManager,
    oms: OrderManager,
    db_path: Path,
    logger: Optional[ComponentLogger] = None
) -> Dict[str, Any]:
    """
    Complete system recovery after crash/downtime.
    
    Recovery flow:
    1. Load last saved state
    2. Check actual broker position
    3. Reconcile position state
    4. Detect data gaps
    5. Return recovery result
    
    Args:
        state_manager: TradingStateManager instance
        oms: OrderManager instance
        db_path: Path to SQLite database
        logger: Optional logger instance
        
    Returns:
        Recovery result dict with status, position reconciliation, and data gaps
    """
    if logger is None:
        logger = ComponentLogger.get_logger("system_recovery")
    
    recovery_result = {
        'state_loaded': False,
        'saved_state': None,
        'position_reconciliation': None,
        'data_gaps': [],
        'data_gaps_count': 0
    }
    
    # Step 1: Load last saved state
    saved_state = state_manager.load_saved_state()
    
    if saved_state is None:
        logger.warning("No saved state found - starting fresh")
        recovery_result['saved_state'] = None
        return recovery_result
    
    recovery_result['state_loaded'] = True
    recovery_result['saved_state'] = saved_state
    
    logger.info("✅ Saved state loaded successfully")
    
    # Step 2: Check actual broker position
    broker_positions = []
    try:
        if not oms.dry_run:
            broker_positions = oms.kite.positions()['net']
        else:
            # Dry-run mode: No broker positions
            broker_positions = []
    except Exception as e:
        logger.error(f"Failed to get broker positions: {e}", exc_info=True)
        broker_positions = []
    
    # Step 3: Reconcile position state
    saved_position = saved_state.get('position')
    position_reconciliation = reconcile_position(
        saved_position=saved_position,
        broker_positions=broker_positions,
        oms=oms,
        logger=logger
    )
    
    recovery_result['position_reconciliation'] = position_reconciliation
    
    # Step 4: Detect data gaps
    saved_timestamp = saved_state.get('last_processed_timestamp')
    current_time = datetime.now(KOLKATA_TZ)
    
    data_gaps = detect_data_gaps(
        saved_timestamp=saved_timestamp,
        current_time=current_time,
        db_path=db_path,
        logger=logger
    )
    
    recovery_result['data_gaps'] = data_gaps
    recovery_result['data_gaps_count'] = len(data_gaps)
    
    if len(data_gaps) > 0:
        logger.warning(f"⚠️ Found {len(data_gaps)} missing candles - data gaps detected")
    else:
        logger.info("✅ No data gaps detected - data is continuous")
    
    return recovery_result

