# Recovery State Simulation - System Crash/Glitch Scenarios

## 🎯 **Recovery Scenarios**

This document simulates recovery from system failures, crashes, WiFi disconnections, and API issues using the recovery decision matrix.

---

## 🔴 **Scenario 1: System Crash During Trading Day**

### **Setup:**
- **Time Before Crash**: 11:00 AM (bar 2005)
- **Position**: LONG entered at bar 2000 (9:15 AM), entry_price=58450.0
- **System State Saved**: Last auto-save at 10:45 AM (every 15min)
- **Crash Time**: 11:00 AM (system goes down)
- **Recovery Time**: 11:30 AM (system restarts)

### **What Happened While System Was Down:**
- ✅ 2 candles completed (11:00-11:15, 11:15-11:30)
- ✅ Position still exists in market (LONG, entered at 58450.0)
- ✅ Current market price: 58600.0 (position profitable)

---

## ⏰ **11:30 AM - System Recovery Starts**

### **Step 1: Load Last Saved State**

```python
# Load saved state from last auto-save (10:45 AM)
state_manager = TradingStateManager(db_path)
saved_state = state_manager.load_saved_state()

# Extract saved state:
last_long_exit_bar = saved_state.get('last_long_exit_bar', -1)  # e.g., 1850
last_short_exit_bar = saved_state.get('last_short_exit_bar', -1)  # e.g., 1890
saved_position = saved_state.get('position')
# saved_position = {
#     'direction': 'LONG',
#     'entry_price': 58450.0,
#     'entry_bar_index': 2000,
#     'entry_timestamp': '2024-12-01T09:15:05+05:30'
# }
saved_timestamp = saved_state.get('last_processed_timestamp')  # '2024-12-01T10:45:00+05:30'
```

**Saved State**: Position was LONG, entered at bar 2000.

---

### **Step 2: Check Actual Broker Position**

```python
# Get actual positions from Zerodha broker
try:
    broker_positions = oms.kite.positions()['net']
    
    actual_position = None
    for pos in broker_positions:
        if 'BANKNIFTY' in pos['tradingsymbol'] and pos['quantity'] != 0:
            # Found active position
            actual_position = {
                'direction': 'LONG' if pos['quantity'] > 0 else 'SHORT',
                'entry_price': pos['average_price'],
                'quantity': abs(pos['quantity']),
                'product': pos['product']
            }
            break
except Exception as e:
    logger.error(f"Failed to get broker positions: {e}")
    actual_position = None

# Result:
# actual_position = {
#     'direction': 'LONG',
#     'entry_price': 58450.0,  # Average entry price from broker
#     'quantity': 280,  # 8 lots * 35 units
#     'product': 'NRML'
# }
```

**Broker Position**: LONG exists, entry_price=58450.0 ✅

---

### **Step 3: Reconcile Position State**

```python
# Compare saved position vs broker position
saved_pos = saved_position
actual_pos = actual_position

# Decision Matrix: Both positions exist
if saved_pos and actual_pos:
    # Both exist - check if they match
    if (saved_pos['direction'] == actual_pos['direction'] and
        abs(saved_pos['entry_price'] - actual_pos['entry_price']) < 10):  # Allow 10 point difference
        # Positions match - use saved state (has entry_bar_index)
        logger.info("✅ Position state matches broker position")
        
        # Restore position from saved state
        oms.position.position_type = PositionType.LONG
        oms.position.entry_price = saved_pos['entry_price']  # 58450.0
        oms.position.entry_bar_index = saved_pos['entry_bar_index']  # 2000 (critical!)
        oms.position.entry_time = datetime.fromisoformat(saved_pos['entry_timestamp'])
        oms.position.atm_strike = saved_pos.get('atm_strike')
        oms.position.hedge_strike = saved_pos.get('hedge_strike')
        
        logger.info(f"✅ Position restored: LONG at {oms.position.entry_price}, bar {oms.position.entry_bar_index}")
    else:
        # Positions don't match - use broker as source of truth
        logger.warning("⚠️ Position mismatch: Saved and broker positions differ, using broker")
        oms.position.position_type = PositionType.LONG if actual_pos['direction'] == 'LONG' else PositionType.SHORT
        oms.position.entry_price = actual_pos['entry_price']
        # We don't know entry_bar_index - use current bar (conservative)
        oms.position.entry_bar_index = len(historical_data)  # Current bar index
```

**Result**: Positions match! ✅ Use saved state with `entry_bar_index=2000`.

---

### **Step 4: Detect Data Gaps**

```python
# Detect missing candles while system was down
saved_ts = datetime.fromisoformat(saved_timestamp)  # 2024-12-01 10:45:00
current_time = datetime.now(KOLKATA_TZ)  # 2024-12-01 11:30:00

# Calculate expected candles between 10:45 and 11:30
# Market hours: 9:15 AM - 3:30 PM
# 15min candles: 10:45, 11:00, 11:15, 11:30
expected_timestamps = [
    datetime(2024, 12, 1, 10, 45, 0, tzinfo=KOLKATA_TZ),  # Saved at this time
    datetime(2024, 12, 1, 11, 0, 0, tzinfo=KOLKATA_TZ),   # Missing!
    datetime(2024, 12, 1, 11, 15, 0, tzinfo=KOLKATA_TZ),  # Missing!
    datetime(2024, 12, 1, 11, 30, 0, tzinfo=KOLKATA_TZ)   # Current (running)
]

# Query database for existing candles
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute(
    """
    SELECT timestamp
    FROM ohlcv_zerodha
    WHERE timeframe = '15min'
    AND timestamp >= ? AND timestamp <= ?
    ORDER BY timestamp
    """,
    (int(saved_ts.timestamp()), int(current_time.timestamp()))
)
db_timestamps = set([row[0] for row in cursor.fetchall()])
conn.close()

# Find missing timestamps
missing_bars = []
for expected_ts in expected_timestamps[1:]:  # Skip first (saved at that time)
    expected_ts_int = int(expected_ts.timestamp())
    if expected_ts_int not in db_timestamps:
        missing_bars.append(expected_ts)

# Result:
# missing_bars = [
#     datetime(2024, 12, 1, 11, 0, 0),   # Missing candle
#     datetime(2024, 12, 1, 11, 15, 0)   # Missing candle
# ]
```

**Result**: 2 missing candles detected (11:00, 11:15).

---

### **Step 5: Fill Data Gaps from Zerodha**

```python
# Fill gaps using existing Zerodha fetch functions
from scripts.fetch_zerodha_historical_data import (
    fetch_historical_candles,
    store_candles_to_db
)

# Get futures token
futures_token = oms._get_futures_token()  # December contract

# Calculate date range for missing candles
from_date = min(missing_bars)  # 2024-12-01 11:00:00
to_date = max(missing_bars) + timedelta(minutes=15)  # 2024-12-01 11:30:00

# Fetch historical data for gap period
df = fetch_historical_candles(
    kite=oms.kite,
    instrument_token=futures_token,
    interval='15min',
    from_date=from_date,
    to_date=to_date,
    continuous=False,
    oi=False
)

# Filter to only missing timestamps
missing_timestamps = set([int(ts.timestamp()) for ts in missing_bars])
df_filtered = df[df['timestamp'].apply(lambda x: int(x.timestamp()) in missing_timestamps)]

# Store to database
success = store_candles_to_db(
    db_path=db_path,
    symbol="BANKNIFTY25DECFUT",
    timeframe='15min',
    df=df_filtered,
    table_name='ohlcv_zerodha'
)

# Result:
# ✅ Filled 2 missing candles:
#   - 2024-12-01 11:00:00: OHLCV={...}
#   - 2024-12-01 11:15:00: OHLCV={...}
```

**Result**: Gaps filled successfully! ✅

---

### **Step 6: Rebuild ML State (Recalculate)**

```python
# Since gaps existed and were filled, need to recalculate ML state
# (Cannot restore from saved state because we missed candles)

logger.info("Gaps detected (2 bars) - recalculating ML state from complete historical data")

# Load complete historical OHLCV data (last 2000 bars from database)
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

df_15min = df_15min.iloc[::-1].reset_index(drop=True)  # Oldest first
df_15min['timestamp'] = pd.to_datetime(df_15min['timestamp'], unit='s', utc=True)
df_15min['timestamp'] = df_15min['timestamp'].dt.tz_convert('Asia/Kolkata')

# Recalculate ML features/indicators from complete historical data
results = ml_system.generate_signals(
    high=df_15min['high'].values,
    low=df_15min['low'].values,
    close=df_15min['close'].values,
    start_bar=200  # Warmup period
)

logger.info("✅ ML state recalculated from complete historical data")
```

**Result**: ML state recalculated from complete data (including filled gaps). ✅

---

### **Step 7: Update Re-entry State**

```python
# Re-entry state from saved state (already loaded)
last_long_exit_bar = saved_state.get('last_long_exit_bar', -1)  # 1850
last_short_exit_bar = saved_state.get('last_short_exit_bar', -1)  # 1890

# Position exists (LONG) - no exit happened during downtime
# Re-entry state remains unchanged
```

**Result**: Re-entry state unchanged (position still active, no exit).

---

### **Step 8: Resume Trading**

```python
# System is now recovered:
# ✅ Position state: LONG at bar 2000, entry_price=58450.0
# ✅ Data gaps: Filled (2 candles from Zerodha)
# ✅ ML state: Recalculated from complete historical data
# ✅ Re-entry state: Unchanged

# Continue processing new ticks
# Current time: 11:30 AM
# Next candle: 11:30 - 11:45 (forming)

# Check current position status
if oms.position.position_type == PositionType.LONG:
    # Position exists - continue monitoring for exits
    # bars_held = current_bar_index - entry_bar_index
    # = 2007 - 2000 = 7 bars (if no exit, would exit at bar 2004 via 4-bar)
    # But position still exists, so we continue
    pass
```

**Result**: System recovered, trading continues! ✅

---

## 🔴 **Scenario 2: Position Exited During Downtime**

### **Setup:**
- **Time Before Crash**: 11:00 AM (bar 2005)
- **Position**: LONG entered at bar 2000 (9:15 AM)
- **Crash Time**: 11:00 AM (system goes down)
- **What Happened**: Position was exited by volume peak at 11:15 AM candle (bar 2006)
- **Recovery Time**: 11:30 AM (system restarts)

### **Recovery Flow:**

```python
# Step 1: Load saved state
saved_state = load_saved_state()
saved_position = {'direction': 'LONG', 'entry_bar_index': 2000, ...}
saved_timestamp = '2024-12-01T11:00:00+05:30'

# Step 2: Check broker position
broker_positions = oms.kite.positions()['net']
actual_position = None  # ❌ No position found!

# Step 3: Reconcile position state
# Decision Matrix: saved_position exists BUT actual_position is None
if saved_position and not actual_position:
    # Position existed in saved state but not in market
    # → Position was exited during downtime
    
    logger.warning("⚠️ Position mismatch: Position in saved state but not in market (exited during downtime)")
    
    # Estimate exit bar (conservative: use last processed bar)
    # We know exit happened between saved_timestamp and current_time
    # Use the bar that would have been processing at crash time
    estimated_exit_bar = len(historical_data) - 1  # Conservative estimate
    
    # Update re-entry state from saved position's entry_bar_index
    if saved_position['direction'] == 'LONG':
        last_long_exit_bar = estimated_exit_bar  # Approximate exit bar
    else:
        last_short_exit_bar = estimated_exit_bar
    
    # Reset position
    oms.position = Position()
    logger.info("✅ Cleared position (exited during downtime)")
```

**Result**: Position cleared, re-entry state updated (estimated exit bar).

---

### **Step 4-8: Same as Scenario 1**
- Detect gaps (2 candles: 11:00, 11:15)
- Fill gaps from Zerodha
- Recalculate ML state
- Update re-entry state (already done above)
- Resume trading

---

## 🔴 **Scenario 3: WiFi Down + API Reconnection**

### **Setup:**
- **Time**: 10:00 AM (actively trading)
- **Position**: LONG exists
- **WiFi Down**: 10:15 AM (WebSocket disconnects)
- **Recovery**: 10:20 AM (WiFi reconnected)

### **Recovery Flow:**

```python
# WebSocket disconnects
price_feed.is_connected = False

# Detection
if not price_feed.is_connected:
    logger.warning("⚠️ WebSocket disconnected. Attempting to reconnect...")
    
    # Try reconnection
    if zerodha_reconnection_handler.handle_api_down():
        # Check if request token is still valid (before 6 AM next morning)
        if _is_token_valid():
            # Retry with same token
            price_feed.start()  # Reconnect WebSocket
            logger.info("✅ Reconnected to Zerodha API")
        else:
            # Token expired - need re-login
            if zerodha_reconnection_handler.handle_token_expired():
                # Generate new request token (may need browser)
                authenticator.login(auto_open_browser=True)
                price_feed.start()  # Reconnect with new token
                logger.info("✅ Reconnected with new token")
```

**Result**: API reconnected, trading continues (small gap in data, but system continues).

---

## 🔴 **Scenario 4: Position Mismatch (Different Direction)**

### **Setup:**
- **Saved Position**: LONG at 58450.0 (bar 2000)
- **Broker Position**: SHORT at 58200.0
- **What Happened**: Signal reversed during downtime, system exited LONG and entered SHORT

### **Recovery Flow:**

```python
# Step 1-2: Load state, check broker
saved_position = {'direction': 'LONG', 'entry_price': 58450.0, ...}
actual_position = {'direction': 'SHORT', 'entry_price': 58200.0, ...}

# Step 3: Reconcile (Mismatch detected)
if saved_position and actual_position:
    if saved_position['direction'] != actual_position['direction']:
        # CRITICAL: Directions don't match!
        logger.error("⚠️ CRITICAL: Position direction mismatch!")
        logger.error(f"   Saved: {saved_position['direction']} at {saved_position['entry_price']}")
        logger.error(f"   Broker: {actual_position['direction']} at {actual_position['entry_price']}")
        
        # Broker is source of truth
        logger.warning("Using broker position as source of truth")
        
        oms.position.position_type = PositionType.SHORT  # Use broker
        oms.position.entry_price = actual_position['entry_price']  # 58200.0
        oms.position.entry_bar_index = len(historical_data)  # Estimate (conservative)
        
        # Update re-entry state for both sides (both exits happened)
        last_long_exit_bar = saved_position.get('entry_bar_index', len(historical_data))
        last_short_exit_bar = len(historical_data)  # SHORT just entered
```

**Result**: Broker position used (SHORT), both exit bars updated.

---

## 🔴 **Scenario 5: Large Gap (2000 Points) on Recovery**

### **Setup:**
- **Saved State**: LONG at 58450.0 (bar 2000)
- **Crash**: 3:00 PM
- **Recovery**: Next morning 9:15 AM
- **Gap**: Market opens at 60450.0 (gap up 2000 points)

### **Recovery Flow:**

```python
# Step 1-3: Load state, check broker, reconcile
# Position still exists in broker (LONG at 58450.0)
# Current market price: 60450.0 (gap up 2000 points)

# Step 4-5: Detect gaps, fill gaps
# Large gap period (entire night) - many missing candles
# Fill all missing candles from Zerodha historical data

# Step 6: Recalculate ML state
# Full recalculation from complete historical data (2000 bars)

# Step 7-8: Resume trading
# Position exists: LONG at 58450.0
# Current price: 60450.0 (gap up 2000 points)

# Check volume exit on first tick
running_candle.close = 60450.0

volume_exit, exit_price, _ = volume_exit_strategy.should_exit(
    trade_direction=1,  # LONG
    entry_bar=2000,
    current_bar=current_bar_index,
    historical_data=df_completed,
    current_high=60450.0,
    current_low=60450.0,
    current_close=60450.0,
    entry_price=58450.0
)

# Volume exit: Check peaks above entry (58450)
# Nearest peak: e.g., 58600.0
# Gap price (60450.0) >> 58600.0 → Peak CROSSED! ✅
# volume_exit = True
# exit_price = 60450.0

# Exit position immediately
oms.exit_position(exit_price=60450.0)

# Update re-entry state
last_long_exit_bar = current_bar_index
```

**Result**: Large gap triggers immediate volume exit (profitable!). ✅

---

## 📊 **Recovery Decision Matrix Applied**

| Scenario | Saved Position | Broker Position | Action | Result |
|----------|---------------|-----------------|--------|--------|
| **1. Normal Crash** | LONG @ 58450 | LONG @ 58450 | Use saved (has entry_bar_index) | ✅ Recovered |
| **2. Exit During Downtime** | LONG @ 58450 | None | Clear position, estimate exit bar | ✅ Cleared |
| **3. WiFi Down** | LONG @ 58450 | LONG @ 58450 | Reconnect API, continue | ✅ Reconnected |
| **4. Direction Mismatch** | LONG @ 58450 | SHORT @ 58200 | Use broker (source of truth) | ✅ Recovered |
| **5. Large Gap Recovery** | LONG @ 58450 | LONG @ 58450 | Recalculate, check exit | ✅ Exit triggered |

---

## ✅ **Key Recovery Principles**

1. **Broker is Source of Truth**: Always trust broker position over saved state
2. **Fill Gaps Conservatively**: Fetch all missing candles, don't skip
3. **Recalculate When Needed**: If gaps exist, recalculate ML state
4. **Estimate Conservatively**: If entry_bar_index unknown, use current bar
5. **Handle All Scenarios**: System continues regardless of what happened during downtime

---

## 🎯 **Recovery Success Criteria**

- ✅ Position state matches broker
- ✅ All data gaps filled
- ✅ ML state accurate (recalculated if needed)
- ✅ Re-entry state updated correctly
- ✅ Trading resumes seamlessly

**All scenarios handled correctly!** ✅

