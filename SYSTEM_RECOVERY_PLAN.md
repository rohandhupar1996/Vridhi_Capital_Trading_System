# System Recovery & Glitch Handling Plan

## 🎯 **Goal**
Handle system failures, crashes, WiFi disconnections, and API issues to ensure continuous trading operation with proper recovery.

---

## 🔴 **Failure Scenarios**

### **1. Zerodha API Issues**
- **Scenario A**: API down temporarily
  - **Detection**: WebSocket disconnects, API calls fail
  - **Action**: Retry with same request token (valid till 6 AM next morning)
  - **Recovery**: Auto-reconnect, continue processing

- **Scenario B**: Request token expired (after 6 AM)
  - **Detection**: API returns authentication error
  - **Action**: Generate new request token (re-login)
  - **Recovery**: Authenticate, reconnect, continue

### **2. System Crashes / WiFi Down**
- **Scenario**: System crashes or network disconnects
  - **Detection**: System restarts, gaps in candle data
  - **Impact**: 
    - Candle bars progressed while system was off
    - Position might exist in market but not in our state
    - ML state might be out of sync
  - **Recovery**: Full state reconciliation

### **3. Position Mismatch**
- **Scenario**: Position exists in market but not in our saved state (or vice versa)
  - **Detection**: Compare saved position vs broker positions
  - **Recovery**: Reconcile position state with actual market position

---

## 🛠️ **Recovery Strategy**

### **Step 1: Load Last Saved State**
```python
# On system restart:
state_manager = TradingStateManager(db_path)
saved_state = state_manager.load_saved_state()  # Last saved state (could be hours old)

# Extract saved state:
last_long_exit_bar = saved_state.get('last_long_exit_bar', -1)
last_short_exit_bar = saved_state.get('last_short_exit_bar', -1)
saved_position = saved_state.get('position')
saved_timestamp = saved_state.get('last_processed_timestamp')  # When state was saved
```

### **Step 2: Check Actual Broker Position**
```python
# Get actual positions from Zerodha broker
try:
    broker_positions = oms.kite.positions()['net']
    
    # Determine actual position from broker
    actual_position = None
    for pos in broker_positions:
        if pos['quantity'] != 0:
            # Position exists in market
            actual_position = {
                'direction': 'LONG' if pos['quantity'] > 0 else 'SHORT',
                'entry_price': pos['average_price'],
                'quantity': abs(pos['quantity']),
                'product': pos['product'],
                'instrument_token': pos['instrument_token']
            }
            break
except Exception as e:
    logger.error(f"Failed to get broker positions: {e}")
    actual_position = None
```

### **Step 3: Reconcile Position State**
```python
# Compare saved position vs actual broker position
def reconcile_position(saved_position, actual_position, oms):
    """
    Reconcile position state after crash/recovery
    """
    if actual_position and not saved_position:
        # Position exists in market but not in saved state
        # System crashed after entering position but before saving state
        logger.warning("⚠️ Position mismatch: Position exists in market but not in saved state")
        
        # Update OMS position from broker
        oms.position.position_type = PositionType.LONG if actual_position['direction'] == 'LONG' else PositionType.SHORT
        oms.position.entry_price = actual_position['entry_price']
        oms.position.lot_size = calculate_lot_size(actual_position['quantity'])
        oms.position.entry_time = datetime.now()  # We don't know exact entry time, use current
        
        # We don't know entry_bar_index - need to estimate or use current
        # Option: Use current bar index (conservative approach)
        # Or: Query order history to find exact entry time/bar
        
        logger.info(f"✅ Recovered position from broker: {oms.position.position_type.value}")
        
    elif saved_position and not actual_position:
        # Position exists in saved state but not in market
        # Position was exited while system was down
        logger.warning("⚠️ Position mismatch: Position in saved state but not in market (exited during downtime)")
        
        # Update re-entry state from saved position's entry_bar_index
        # Exit happened while system was down - mark that bar as exit
        if saved_position['direction'] == 'LONG':
            last_long_exit_bar = saved_position['entry_bar_index']  # Approximate, we don't know exact exit bar
        else:
            last_short_exit_bar = saved_position['entry_bar_index']
        
        # Reset position
        oms.position = Position()
        logger.info("✅ Cleared position (exited during downtime)")
        
    elif saved_position and actual_position:
        # Both exist - check if they match
        if (saved_position['direction'] == actual_position['direction'] and
            abs(saved_position['entry_price'] - actual_position['entry_price']) < 10):  # Allow small difference
            # Positions match - use saved state (has entry_bar_index)
            logger.info("✅ Position state matches broker position")
        else:
            # Positions don't match - use broker as source of truth
            logger.warning("⚠️ Position mismatch: Saved and broker positions differ, using broker")
            oms.position.position_type = PositionType.LONG if actual_position['direction'] == 'LONG' else PositionType.SHORT
            oms.position.entry_price = actual_position['entry_price']
            oms.position.lot_size = calculate_lot_size(actual_position['quantity'])
            
    else:
        # No position in either - system state is clean
        logger.info("✅ No position state mismatch - system clean")
```

### **Step 4: Detect Data Gaps**
```python
def detect_data_gaps(saved_timestamp, current_time, db_path):
    """
    Detect missing candle bars while system was down.
    
    We save every candle to database when it closes, so gaps = missing timestamps in DB.
    """
    import sqlite3
    from datetime import timedelta
    
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


def generate_expected_timestamps(from_time, to_time, interval_min=15):
    """
    Generate expected 15min candle timestamps between from_time and to_time.
    Only during market hours: 9:15 AM to 3:30 PM IST.
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
```

### **Step 5: Fill Data Gaps (Using Existing Zerodha Fetch Script)**
```python
def fill_data_gaps(missing_bars, oms, db_path, symbol):
    """
    Fill missing candle bars from Zerodha historical data.
    Uses existing functions from scripts/fetch_zerodha_historical_data.py
    """
    if not missing_bars:
        logger.info("No data gaps to fill")
        return 0
    
    logger.info(f"Filling {len(missing_bars)} missing candle bars from Zerodha...")
    
    # Import functions from existing script
    from scripts.fetch_zerodha_historical_data import (
        fetch_historical_candles,
        store_candles_to_db
    )
    
    # Get futures token
    futures_token = oms._get_futures_token()
    if not futures_token:
        logger.error("Cannot fill gaps: Failed to get futures token")
        return 0
    
    # Calculate date range for missing bars
    from_date = min(missing_bars)  # Earliest missing timestamp
    to_date = max(missing_bars) + timedelta(minutes=15)  # Latest missing timestamp + buffer
    
    try:
        # Fetch historical data for the gap period using existing function
        # This function handles API limits and chunking automatically
        df = fetch_historical_candles(
            kite=oms.kite,
            instrument_token=futures_token,
            interval='15min',  # 15min candles
            from_date=from_date,
            to_date=to_date,
            continuous=False,  # Not using continuous for intraday
            oi=False,  # Don't need OI data
            progress_callback=None  # Can add progress callback if needed
        )
        
        if df.empty:
            logger.warning(f"⚠️ No data received from Zerodha for gap period")
            return 0
        
        # Filter to only missing timestamps
        missing_timestamps = set(missing_bars)
        df_filtered = df[df['timestamp'].isin(missing_timestamps)]
        
        if df_filtered.empty:
            logger.warning(f"⚠️ Fetched data but none matched missing timestamps")
            return 0
        
        # Store to database using existing function
        # Store to ohlcv_zerodha table (same table used by live system)
        success = store_candles_to_db(
            db_path=db_path,
            symbol=symbol,
            timeframe='15min',
            df=df_filtered,
            table_name='ohlcv_zerodha'  # Same table as live system
        )
        
        if success:
            logger.info(f"✅ Filled {len(df_filtered)} missing candles from Zerodha")
            return len(df_filtered)
        else:
            logger.error(f"❌ Failed to store {len(df_filtered)} candles to database")
            return 0
            
    except Exception as e:
        logger.error(f"Error filling data gaps: {e}", exc_info=True)
        return 0
```

### **Step 6: Rebuild ML State**
```python
def rebuild_ml_state(missing_bars_count, saved_state, db_path, ml_system):
    """
    Rebuild ML system state after gap filling.
    
    If gaps exist and were filled, we need to recalculate ML state from
    complete historical data (since gaps mean we missed candles).
    """
    if missing_bars_count == 0:
        # No gaps - can restore from saved state (fast, no recalculation)
        logger.info("No gaps - restoring ML state from saved state")
        ml_system.restore_state(
            features=saved_state['ml_features'],
            indicators=saved_state['ml_indicators'],
            predictions=saved_state.get('ml_predictions', []),
            signals=saved_state.get('ml_signals', [])
        )
        logger.info("✅ ML state restored from saved state (no recalculation needed)")
    else:
        # Gaps exist - need to recalculate from complete historical data
        # Because gaps mean we missed candles, ML features/indicators need recalculation
        logger.info(f"Gaps detected ({missing_bars_count} bars) - recalculating ML state from historical data")
        
        # Load complete historical OHLCV data (last 2000 bars from database)
        # After gap filling, database now has complete data
        import sqlite3
        import pandas as pd
        
        conn = sqlite3.connect(db_path)
        df_15min = pd.read_sql_query(
            """
            SELECT timestamp, open, high, low, close, volume
            FROM ohlcv_zerodha
            WHERE timeframe = '15min'
            ORDER BY timestamp DESC
            LIMIT 2000
            """,
            conn
        )
        conn.close()
        
        # Reverse to oldest first
        df_15min = df_15min.iloc[::-1].reset_index(drop=True)
        
        # Convert timestamp
        df_15min['timestamp'] = pd.to_datetime(df_15min['timestamp'], unit='s', utc=True)
        df_15min['timestamp'] = df_15min['timestamp'].dt.tz_convert('Asia/Kolkata')
        
        if len(df_15min) < 200:
            logger.warning(f"⚠️ Not enough historical data ({len(df_15min)} bars) - minimum 200 bars needed")
            return False
        
        # Recalculate ML features/indicators from complete historical data
        logger.info(f"Recalculating ML state from {len(df_15min)} historical bars...")
        
        results = ml_system.generate_signals(
            high=df_15min['high'].values,
            low=df_15min['low'].values,
            close=df_15min['close'].values,
            start_bar=200  # Warmup period
        )
        
        logger.info("✅ ML state recalculated from complete historical data")
        return True
```

### **Step 7: Update Re-entry State**
```python
def update_re_entry_state_after_recovery(oms, missing_bars_count, saved_state):
    """
    Update re-entry state accounting for downtime
    """
    # If we had gaps, we might have missed exit bars
    # Need to be conservative: if position was exited during downtime,
    # we already handled it in reconcile_position()
    
    # If no position and we had gaps, check if we should update exit bars
    if oms.position.position_type == PositionType.NONE and missing_bars_count > 0:
        # We might have exited during downtime
        # Use current bar index minus gaps as conservative exit bar
        current_bar_index = len(historical_data) - 1
        
        # If saved position existed but is now gone (handled in reconcile_position)
        # Exit bars were already updated there
        
        # If no saved position, exit bars remain from saved state
        pass
    
    # Re-entry state from saved state (already loaded)
    last_long_exit_bar = saved_state.get('last_long_exit_bar', -1)
    last_short_exit_bar = saved_state.get('last_short_exit_bar', -1)
```

---

## 📋 **Complete Recovery Flow**

```python
def system_recovery_on_startup(oms, db_path, symbol, ml_system):
    """
    Complete system recovery flow on startup after crash/downtime.
    
    Uses existing Zerodha historical data fetch functions to fill gaps.
    Recalculates ML state if gaps existed (since we save every candle to DB).
    """
    logger.info("🔄 Starting system recovery...")
    
    # Step 1: Load last saved state
    state_manager = TradingStateManager(db_path)
    saved_state = state_manager.load_saved_state()
    
    if not saved_state:
        logger.warning("⚠️ No saved state found - starting fresh")
        saved_state = {}
    
    saved_timestamp = saved_state.get('last_processed_timestamp')
    
    # Step 2: Check broker position
    actual_position = get_broker_positions(oms)
    
    # Step 3: Reconcile position state
    reconcile_position(saved_state.get('position'), actual_position, oms)
    
    # Step 4: Detect data gaps
    # We save every candle to DB when it closes, so gaps = missing candles in DB
    current_time = datetime.now(KOLKATA_TZ)
    missing_bars = detect_data_gaps(saved_timestamp, current_time, db_path)
    missing_bars_count = len(missing_bars)
    
    logger.info(f"Detected {missing_bars_count} missing candles while system was down")
    
    # Step 5: Fill data gaps using existing Zerodha fetch functions
    # This uses scripts/fetch_zerodha_historical_data.py functions
    filled_count = 0
    if missing_bars_count > 0:
        filled_count = fill_data_gaps(missing_bars, oms, db_path, symbol)
        logger.info(f"Filled {filled_count}/{missing_bars_count} missing candles")
    
    # Step 6: Rebuild ML state
    # If gaps existed and were filled, recalculate from complete historical data
    # Otherwise, restore from saved state (faster)
    if missing_bars_count > 0 and filled_count > 0:
        # Gaps were filled - need to recalculate ML state
        rebuild_ml_state(missing_bars_count, saved_state, db_path, ml_system)
    elif missing_bars_count == 0:
        # No gaps - restore from saved state (fast)
        rebuild_ml_state(0, saved_state, db_path, ml_system)
    else:
        # Gaps exist but couldn't fill them - log warning
        logger.warning("⚠️ Gaps exist but couldn't fill them - ML state may be inaccurate")
    
    # Step 7: Update re-entry state
    update_re_entry_state_after_recovery(oms, missing_bars_count, saved_state)
    
    # Step 8: Verify system is ready
    verify_system_ready(oms, ml_system)
    
    logger.info("✅ System recovery complete - ready to trade")
    
    return {
        'gaps_detected': missing_bars_count,
        'gaps_filled': filled_count,
        'recovery_success': missing_bars_count == 0 or filled_count > 0
    }
```

---

## 🔄 **API Reconnection Strategy**

### **Zerodha API Issues**

```python
class ZerodhaReconnectionHandler:
    """
    Handle Zerodha API reconnection and token management
    """
    
    def __init__(self, authenticator, oms):
        self.authenticator = authenticator
        self.oms = oms
        self.max_retries = 5
        self.retry_delay = 5  # seconds
    
    def handle_api_down(self):
        """
        Handle API down scenario - retry with same request token
        """
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Attempting to reconnect to Zerodha API (attempt {attempt + 1}/{self.max_retries})")
                
                # Check if request token is still valid (before 6 AM)
                if self._is_token_valid():
                    # Retry with same token
                    if self.authenticator.login(auto_open_browser=False):
                        logger.info("✅ Reconnected to Zerodha API")
                        return True
                else:
                    # Token expired - need to re-login
                    logger.warning("Request token expired - need to re-login")
                    return self.handle_token_expired()
                    
            except Exception as e:
                logger.error(f"Reconnection attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
        
        logger.error("❌ Failed to reconnect after all attempts")
        return False
    
    def handle_token_expired(self):
        """
        Handle token expiration (after 6 AM) - generate new request token
        """
        try:
            logger.info("Generating new request token...")
            
            # Generate new request token (re-login)
            if self.authenticator.login(auto_open_browser=True):  # May need browser
                logger.info("✅ New request token generated - API connected")
                return True
            else:
                logger.error("❌ Failed to generate new request token")
                return False
                
        except Exception as e:
            logger.error(f"Error generating new token: {e}")
            return False
    
    def _is_token_valid(self):
        """
        Check if request token is still valid (before 6 AM next morning)
        """
        # Check token expiry time
        # Zerodha request tokens are valid till 6 AM next morning
        current_time = datetime.now(KOLKATA_TZ)
        tomorrow_6am = (current_time + timedelta(days=1)).replace(hour=6, minute=0, second=0)
        
        if current_time.hour >= 6:
            # After 6 AM - token valid till tomorrow 6 AM
            expiry_time = tomorrow_6am
        else:
            # Before 6 AM - token valid till today 6 AM
            expiry_time = current_time.replace(hour=6, minute=0, second=0)
            if expiry_time < current_time:
                expiry_time = tomorrow_6am
        
        return current_time < expiry_time
```

---

## 🚨 **Automatic State Saving (During Trading)**

```python
def auto_save_state_periodically(interval_minutes=15):
    """
    Auto-save state periodically during trading (not just at 3:30 PM)
    This ensures we have recent state in case of crash
    """
    while True:
        time.sleep(interval_minutes * 60)
        
        try:
            # Save current state
            state_manager.save_daily_state(
                ml_system=ml_system,
                historical_data=df_15min
            )
            logger.info(f"✅ Auto-saved state (periodic save every {interval_minutes} min)")
            
        except Exception as e:
            logger.error(f"Error auto-saving state: {e}")
```

---

## 📊 **Recovery Decision Matrix**

| Scenario | Saved Position | Broker Position | Action |
|----------|---------------|-----------------|--------|
| Match | LONG | LONG | Use saved state, continue |
| Crash after entry | None | LONG | Recover from broker, estimate entry_bar |
| Crash after exit | LONG | None | Mark exit bar, update re-entry state |
| Mismatch | LONG | SHORT | Use broker as source of truth, alert |
| No position | None | None | Continue normally |
| Data gaps | Any | Any | Fill gaps, recalculate ML state if needed |

---

## ✅ **Recovery Checklist**

- [ ] Load last saved state
- [ ] Check actual broker positions
- [ ] Reconcile position state (saved vs broker)
- [ ] Detect data gaps (missing candles)
- [ ] Fill data gaps from Zerodha historical data
- [ ] Rebuild ML state (restore or recalculate)
- [ ] Update re-entry state
- [ ] Verify system ready
- [ ] Resume trading

---

## 🔧 **Implementation Files**

1. **`src/trading_system/data/recovery_manager.py`** - Main recovery logic
2. **`src/trading_system/broker/zerodha_reconnection.py`** - API reconnection handler
3. **`src/trading_system/data/trading_state_manager.py`** - Enhanced with auto-save

---

## 🎯 **Key Principles**

1. **Broker is Source of Truth**: If position mismatch, trust broker position
2. **Fill Gaps Conservatively**: Fetch missing data, don't skip
3. **Recalculate When Needed**: If gaps exist, recalculate ML state
4. **Auto-Save Frequently**: Save state every 15min, not just at 3:30 PM
5. **Graceful Degradation**: If recovery fails, log errors, alert user, don't trade

---

**Ready to implement recovery system for robust continuous trading!**

