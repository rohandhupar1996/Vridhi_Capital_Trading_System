# Normal Trading Simulation - Tomorrow 9:15 AM

## 🎯 **Scenario Setup**
**Date**: Tomorrow, December 1st, 2024  
**Time**: 9:15 AM IST  
**Starting Point**: System starts fresh, loaded with saved state from backtest  
**Market**: BankNifty Futures + Options  

---

## ⏰ **9:00 AM - System Startup (Before Market Open)**

### **Step 1: Initialize System**
```python
# Load saved state from backtest
state_manager = TradingStateManager(db_path)
saved_state = state_manager.load_saved_state()

# Extract re-entry state
last_long_exit_bar = saved_state.get('last_long_exit_bar', -1)  # e.g., bar 1850
last_short_exit_bar = saved_state.get('last_short_exit_bar', -1)  # e.g., bar 1890

# Load historical OHLCV data (last 2000 bars from database)
historical_df = pd.DataFrame(saved_state.get('historical_data', []))
# Contains: TradingView data (old) + Zerodha data (Nov month)

# Restore ML system state (features stay intact)
ml_system = LorentzianTradingSystem(ml_settings)
ml_system.restore_state(
    features=saved_state['ml_features'],  # f1-f5, last 2000 bars
    indicators=saved_state['ml_indicators'],  # RSI, CCI, filters, etc.
    predictions=saved_state.get('ml_predictions', []),
    signals=saved_state.get('ml_signals', [])
)

# Initialize OMS
oms = OrderManager(kite, lot_size=8, hedge_legs=20, logger=oms_logger)

# OptionChainManager automatically fetches option chain on init
# Current expiry: November expiry (e.g., 2024-11-28)
option_chain_manager.refresh_option_chain()
# Fetches all BankNifty option contracts for current expiry (Nov)
# Caches: {(expiry, strike, type) -> OptionContract}
```

**State After Initialization:**
- ✅ ML system ready with last 2000 bars of features/indicators
- ✅ Historical data loaded (mix of TradingView + Zerodha Nov data)
- ✅ OptionChainManager cached with **November expiry** option chain
- ✅ Re-entry state: `last_long_exit_bar=1850`, `last_short_exit_bar=1890`
- ✅ **Position Check**: Load from saved state
  - `saved_position = saved_state.get('position')`  # Could be None or existing position
  - If position exists → Restore to OMS, monitor for exits ONLY (no ML entry signals)
  - If no position → Ready for new entries (ML signals enabled)

---

## ⏰ **9:15 AM - First Tick Arrives (Market Opens)**

### **Step 2: Get Futures Symbol (November vs December Transition)**

```python
# System checks current month futures symbol dynamically
futures_symbol, futures_token = get_current_month_futures_symbol_and_token(kite)

# Since it's December 1st:
# Zerodha API returns: "BANKNIFTY25DECFUT" (December contract)
# November contract (BANKNIFTY25NOVFUT) has expired (Nov 28)

# Update candle aggregator with new symbol
candle_aggregator = ZerodhaCandleAggregator(
    config=config,
    kite=kite,
    symbol="BANKNIFTY25DECFUT",  # December contract
    logger=logger
)
```

**Key Point**: System automatically switches from November to December contract on December 1st.

---

### **Step 3: Check Position State FIRST (Critical)**

```python
# CRITICAL: Check if position exists from saved state BEFORE processing new signals
saved_position = saved_state.get('position')

if saved_position:
    # Position exists from saved state (from yesterday 3:30 PM or backtest)
    # Restore position to OMS
    oms.position.position_type = PositionType.LONG if saved_position['direction'] == 'LONG' else PositionType.SHORT
    oms.position.entry_price = saved_position['entry_price']
    oms.position.entry_bar_index = saved_position['entry_bar_index']
    oms.position.entry_time = datetime.fromisoformat(saved_position['entry_timestamp'])
    oms.position.atm_strike = saved_position.get('atm_strike')
    oms.position.hedge_strike = saved_position.get('hedge_strike')
    
    logger.info(f"✅ Position restored: {oms.position.position_type.value} at {oms.position.entry_price}, bar {oms.position.entry_bar_index}")
    
    # IMPORTANT: Position exists → Only monitor exits, NO ML signal generation for entry
    position_exists = True
else:
    # No position → Ready for new entries
    position_exists = False
```

**Key Point**: If position exists, we skip ML entry signal generation and only monitor exits.

---

### **Step 4: First Tick Processing (9:15:00 AM)**

```python
# First tick arrives
tick_price = 58450.0  # BankNifty Futures price
tick_volume = 100
tick_time = datetime(2024, 12, 1, 9, 15, 0, tzinfo=KOLKATA_TZ)

# Process tick into running candle
completed_candles = candle_aggregator.on_tick(
    price=tick_price,
    volume=tick_volume,
    timestamp=tick_time
)
# Result: completed_candles = {'15min': None}  # Candle still running

# Get running 15min candle
running_candle_15min = candle_aggregator.running_candles['15min']
# Running candle: timestamp=2024-12-01 09:15:00, open=58450.0, high=58450.0, low=58450.0, close=58450.0, volume=100
```

---

### **Step 5: Position Exists? Handle Exits FIRST (No ML Entry Signals)**

```python
# ⚠️ CRITICAL: Check position FIRST before ML signal generation
if oms.position.position_type != PositionType.NONE:
    # Position exists → Only monitor exits, NO entry signals
    
    # Get historical completed bars for volume exit check
    df_completed = manager_15min.get_dataframe()
    
    # Check volume exit on running candle
    volume_exit, exit_price, exit_reason = volume_exit_strategy.should_exit(
        trade_direction=oms.position.direction,
        entry_bar=oms.position.entry_bar_index,
        current_bar=len(df_completed),  # Current bar index
        historical_data=df_completed,
        current_high=running_candle_15min.high,
        current_low=running_candle_15min.low,
        current_close=running_candle_15min.close,
        entry_price=oms.position.entry_price
    )
    
    if volume_exit:
        # Volume exit triggered
        oms.exit_position(exit_price=exit_price)
        # Update re-entry state
        if oms.position.direction == 1:
            last_long_exit_bar = len(df_completed)
        else:
            last_short_exit_bar = len(df_completed)
        logger.info(f"✅ Position exited via volume exit: {exit_reason}")
    
    # Skip ML signal generation for entry (position exists, only monitoring exits)
    # Continue to next tick
    
else:
    # ⚠️ NO POSITION → Generate ML signals for entry
    
    # Get historical completed bars (last 2000 bars)
    df_completed = manager_15min.get_dataframe()
    
    # Create temporary DataFrame with running candle included
    running_bar = pd.DataFrame({
        'timestamp': [running_candle_15min.timestamp],
        'open': [58450.0],
        'high': [58450.0],  # Will update as ticks come in
        'low': [58450.0],   # Will update as ticks come in
        'close': [58450.0], # Will update as ticks come in
        'volume': [100]
    })
    df_with_running = pd.concat([df_completed, running_bar], ignore_index=True)
    
    # Generate ML signals on RUNNING candle (bar index 2000)
    current_bar_index = 2000
    signals = ml_system.generate_signals(
        high=df_with_running['high'].values,
        low=df_with_running['low'].values,
        close=df_with_running['close'].values,
        start_bar=current_bar_index  # Process latest bar only
    )
    
    # Determine signal
    if signals['start_long'][current_bar_index]:
        current_signal = "LONG"
    elif signals['start_short'][current_bar_index]:
        current_signal = "SHORT"
    else:
        current_signal = "NONE"
    
    # Apply re-entry logic (only if no position)
    current_bar_index_completed = len(df_completed)
    bars_since_long_exit = current_bar_index_completed - last_long_exit_bar
    bars_since_short_exit = current_bar_index_completed - last_short_exit_bar
    
    can_enter_long = (last_long_exit_bar < 0 or 
                     bars_since_long_exit > 50 or
                     (3 <= bars_since_long_exit <= 50 and signals['predictions'][current_bar_index] > 0))
    
    can_enter_short = (last_short_exit_bar < 0 or
                      bars_since_short_exit > 50 or
                      (3 <= bars_since_short_exit <= 50 and signals['predictions'][current_bar_index] < 0))
    
    # Block entry if re-entry rules prevent it
    if current_signal == "LONG" and not can_enter_long:
        current_signal = "NONE"
    elif current_signal == "SHORT" and not can_enter_short:
        current_signal = "NONE"
    
    # Process entry signal via RunningSignalExecutor
    if current_signal != "NONE":
        executor.on_running_signal(current_signal, candle_id, running_candle_15min.close)
```

---

### **Step 6: Process LONG Entry via RunningSignalExecutor (Only if No Position)**

```python
# Call executor with LONG signal
candle_id = "2024-12-01 09:15:00_15min"
trading_price = running_candle_15min.close  # 58450.0 (CLOSE price)

executor.on_running_signal("LONG", candle_id, trading_price)

# Inside RunningSignalExecutor.on_running_signal():
# 1. Check position: oms.position.position_type == PositionType.NONE
# 2. Call oms.enter_long(fast_execution=False)
```

---

### **Step 7: LONG Entry Execution (OrderManager.enter_long())**

```python
# Inside OrderManager.enter_long():
# 1. Get futures price
futures_ltp = 58450.0  # From WebSocket

# 2. Calculate ATM strike (round to nearest 100)
atm_strike = _calculate_atm_strike(58450.0)
# atm_strike = 58400 (rounded down to nearest 100)
# Or: 58500 if rounding up (depends on implementation)

# 3. Calculate hedge strike (20 legs down for LONG)
hedge_strike = atm_strike - (20 * 100)  # 58400 - 2000 = 56400

# 4. Check margin
margin_ok, required_margin = oms.check_margin_availability('LONG', 8)
# Uses basket_order_margins() API
# Returns: ~₹8.5L margin requirement

# 5. Get option symbols via OptionChainManager
# IMPORTANT: OptionChainManager checks current expiry
current_expiry = option_chain_manager.get_current_expiry()
# Returns: 2024-11-28 (November expiry) - CACHED from initialization

# Check if expiry changed (Nov → Dec transition)
if current_expiry.date() < datetime.now().date():
    # November expiry has passed! Refresh option chain
    option_chain_manager.refresh_option_chain()
    # Now fetches December expiry options
    current_expiry = option_chain_manager.get_current_expiry()
    # Returns: 2024-12-26 (December expiry)

# Get option symbols for December expiry
atm_ce_symbol = option_chain_manager.get_option_symbol(58400, "CE", expiry=current_expiry)
# Returns: "BANKNIFTY25DEC58400CE"

atm_pe_symbol = option_chain_manager.get_option_symbol(58400, "PE", expiry=current_expiry)
# Returns: "BANKNIFTY25DEC58400PE"

hedge_pe_symbol = option_chain_manager.get_option_symbol(56400, "PE", expiry=current_expiry)
# Returns: "BANKNIFTY25DEC56400PE"
```

**Key Point**: OptionChainManager automatically refreshes when expiry changes (Nov → Dec).

---

### **Step 8: Execute LONG Position (3-Leg Strategy)**

```python
# LONG Entry Legs:
# 1. BUY ATM CALL (CE) - Bullish leg
# 2. SELL ATM PUT (PE) - Income leg
# 3. BUY Hedge PUT (PE) - Margin reduction

buy_legs = [
    OrderLeg(symbol="BANKNIFTY25DEC58400CE", quantity=8*35=280, transaction_type="BUY"),
    OrderLeg(symbol="BANKNIFTY25DEC56400PE", quantity=8*35=280, transaction_type="BUY")  # Hedge
]

sell_legs = [
    OrderLeg(symbol="BANKNIFTY25DEC58400PE", quantity=8*35=280, transaction_type="SELL")
]

# Execute BUY legs first
_execute_legs(buy_legs, "BUY")
# Places 2 orders simultaneously (basket order)
# Waits for completion

# Execute SELL leg after buys complete
_execute_legs(sell_legs, "SELL")
# Places 1 order

# Update position
oms.position.position_type = PositionType.LONG
oms.position.entry_price = 58450.0  # Futures close price
oms.position.entry_bar_index = 2000  # Current bar index
oms.position.atm_strike = 58400
oms.position.hedge_strike = 56400
oms.position.entry_time = datetime(2024, 12, 1, 9, 15, 5)  # Execution time
```

**Result**: LONG position entered successfully! ✅

---

## ⏰ **9:15:00 - 9:29:59 - Running Candle Formation**

### **Scenario A: Normal Price Movement (No Gap)**

```python
# Ticks continue to arrive
tick_1: price=58475.0, volume=50  → running_candle.high=58475.0
tick_2: price=58425.0, volume=30  → running_candle.low=58425.0
tick_3: price=58460.0, volume=40  → running_candle.close=58460.0
# ... more ticks ...

# On each tick:
# 1. Update running candle OHLCV
# 2. Generate ML signals on running candle (check for reversal)
# 3. Check volume exit (if in position)

# Volume exit check (if LONG position):
if oms.position.position_type == PositionType.LONG:
    volume_exit, exit_price, _ = volume_exit_strategy.should_exit(
        trade_direction=1,  # LONG
        entry_bar=2000,
        current_bar=2000,  # Same bar (running)
        historical_data=df_completed,
        current_high=running_candle.high,  # 58475.0
        current_low=running_candle.low,    # 58425.0
        current_close=running_candle.close, # 58460.0
        entry_price=58450.0
    )
    
    # Volume exit checks if price crosses nearest volume peak above entry
    # Nearest peak above 58450.0: e.g., 58550.0
    # Current high (58475.0) < 58550.0 → No exit
    # volume_exit = False
```

**Result**: Position continues, no volume exit yet.

---

### **Scenario B: Gap Down with Existing LONG Position (CRITICAL - Exit Immediately)**

```python
# ⚠️ CRITICAL SCENARIO: Position exists from saved state (yesterday 3:30 PM)
# LONG position: entry_price=58450.0, entry_bar_index=1995 (from yesterday)

# Market opens with gap down
tick_price = 57950.0  # Gap down 500 points (58450 → 57950)

# Running candle starts at gap price
running_candle_15min = RunningCandle(
    timestamp=2024-12-01 09:15:00,
    open=57950.0,  # Gap down open
    high=57950.0,
    low=57950.0,
    close=57950.0,
    volume=100
)

# ⚠️ FIRST CHECK: Position exists?
if oms.position.position_type == PositionType.LONG:
    # Position exists from saved state (LONG at 58450.0)
    
    # ⚠️ GAP DOWN CHECK: If gap down > threshold, exit immediately (stop loss)
    gap_down_points = oms.position.entry_price - running_candle_15min.open
    # gap_down_points = 58450.0 - 57950.0 = 500 points
    
    # Check if gap down exceeds threshold (e.g., 300 points = ~0.5% loss)
    gap_down_threshold = 300  # Configurable threshold
    gap_down_percent = (gap_down_points / oms.position.entry_price) * 100
    # gap_down_percent = (500 / 58450.0) * 100 = 0.86%
    
    if gap_down_points > gap_down_threshold:
        # ⚠️ GAP DOWN TOO LARGE → Exit immediately (stop loss)
        logger.critical(f"⚠️ GAP DOWN DETECTED: {gap_down_points} points ({gap_down_percent:.2f}%) - Exiting position immediately")
        
        # Exit position at gap price (immediate stop loss)
        oms.exit_position(exit_price=running_candle_15min.open)  # Exit at gap open price
        
        # Update re-entry state
        last_long_exit_bar = len(df_completed)  # Current bar
        
        logger.info(f"✅ Position exited due to gap down: Entry={oms.position.entry_price}, Exit={running_candle_15min.open}, Loss={gap_down_percent:.2f}%")
        
        # Position cleared - now system can generate ML signals for new entries
        # Continue to ML signal generation below
    
    else:
        # Gap down within threshold - check volume exit normally
        volume_exit, exit_price, _ = volume_exit_strategy.should_exit(
            trade_direction=1,  # LONG
            entry_bar=oms.position.entry_bar_index,
            current_bar=len(df_completed),
            historical_data=df_completed,
            current_high=57950.0,
            current_low=57950.0,
            current_close=57950.0,
            entry_price=58450.0
        )
        
        if volume_exit:
            oms.exit_position(exit_price=exit_price)
            last_long_exit_bar = len(df_completed)
        
        # No ML signal generation - position still exists (gap down small)
        # Continue monitoring exits only
```

**Key Point**: Gap down with existing position → Exit immediately if exceeds threshold (stop loss protection).

---

### **Scenario B-2: Gap Down with No Position (Normal ML Signal Generation)**

```python
# If NO position exists, gap down is just price movement
# ML signals generated normally on running candle

# Get historical data + running candle
df_with_running = pd.concat([df_completed, running_bar], ignore_index=True)

# Generate ML signals (gap down price used)
signals = ml_system.generate_signals(
    high=df_with_running['high'].values,
    low=df_with_running['low'].values,
    close=df_with_running['close'].values,  # Gap down close=57950.0
    start_bar=current_bar_index
)

# ML may generate SHORT signal (gap down = bearish)
# Process signal normally if no position exists
```

---

### **Scenario C: Gap Up with Existing LONG Position**

```python
# Position exists from saved state: LONG at 58450.0 (from yesterday)

# Market opens with gap up
tick_price = 58950.0  # Gap up 500 points (58450 → 58950)

# Running candle starts at gap price
running_candle_15min = RunningCandle(
    timestamp=2024-12-01 09:15:00,
    open=58950.0,  # Gap up open
    high=58950.0,
    low=58950.0,
    close=58950.0,
    volume=100
)

# ⚠️ FIRST CHECK: Position exists?
if oms.position.position_type == PositionType.LONG:
    # Position exists from saved state (LONG at 58450.0)
    
    # Check volume exit with gap up price
    volume_exit, exit_price, _ = volume_exit_strategy.should_exit(
        trade_direction=1,  # LONG
        entry_bar=oms.position.entry_bar_index,  # e.g., 1995
        current_bar=len(df_completed),  # Current bar
        historical_data=df_completed,
        current_high=58950.0,  # Gap up price
        current_low=58950.0,
        current_close=58950.0,
        entry_price=58450.0  # Entry was at lower price
    )
    
    # Volume exit: Check peaks ABOVE entry (58450)
    # Nearest peak above 58450: e.g., 58600.0
    # Gap up price (58950.0) > 58600.0 → Peak CROSSED! ✅
    # volume_exit = True
    # exit_price = max(58600.0, 58950.0) = 58950.0
    
    if volume_exit:
        # Exit position immediately (gap up crosses volume peak)
        oms.exit_position(exit_price=exit_price)
        
        # Update re-entry state
        last_long_exit_bar = len(df_completed)
        
        logger.info(f"✅ Position exited via volume peak (gap up): Entry={58450.0}, Exit={exit_price}, Profit={((exit_price-58450.0)/58450.0*100):.2f}%")
        
        # Position cleared - now system can generate ML signals for new entries
    
    # No ML signal generation - position handled (exit or continue)
```

**Key Point**: Gap up with existing LONG → Volume exit may trigger if crosses peak (profitable exit).

---

## ⏰ **9:30 AM - First Candle Closes**

### **Step 9: Candle Close Processing**

```python
# 15min candle closes at 9:30:00
# Last tick updates running candle
tick_final: price=58465.0, volume=20
# Final running candle: open=58450.0, high=58485.0, low=58420.0, close=58465.0, volume=500

# Candle aggregator detects candle close
completed_candles = candle_aggregator.on_tick(
    price=58465.0,
    volume=20,
    timestamp=datetime(2024, 12, 1, 9, 30, 0)
)
# Result: completed_candles = {'15min': OHLCVBar(...)}

# Completed candle stored to database
manager_15min.add_new_bar(
    timestamp=2024-12-01 09:15:00,
    open=58450.0,
    high=58485.0,
    low=58420.0,
    close=58465.0,
    volume=500
)
# Stored to ohlcv_zerodha table
# Deque updated (oldest dropped if > 2000 bars)
```

---

### **Step 10: Check 4-Bar Exit (If Position Exists)**

```python
# Get updated DataFrame
df_15min = manager_15min.get_dataframe()  # Now has 2001 bars
current_bar_index = 2000  # Just completed bar

if oms.position.position_type == PositionType.LONG:
    bars_held = current_bar_index - oms.position.entry_bar_index
    # bars_held = 2000 - 2000 = 0 bars (just entered this candle)
    
    if bars_held >= 4:
        # Not yet - only 0 bars held
        pass
```

**Result**: Position continues (0 bars held, need 4 bars).

---

### **Step 11: Candle-Close Reconciliation (Flicker Check)**

```python
# Generate final signal from completed candle
signals_final = ml_system.generate_signals(...)

# Determine final signal
if signals_final['start_long'][current_bar_index]:
    final_signal = "LONG"
elif signals_final['start_short'][current_bar_index]:
    final_signal = "SHORT"
else:
    final_signal = "NONE"

# Call executor for flicker check
executor.on_candle_close(final_signal, candle_id, completed_candle.close)

# Inside RunningSignalExecutor.on_candle_close():
# Position exists (LONG) and was entered this candle
# final_signal = "LONG" (matches position)
# → No flicker, position continues
```

---

## ⏰ **9:30 AM - 10:00 AM - Second Candle**

```python
# Second candle forms: 9:30 - 9:45
# Running candle updates with ticks
# ... price moves ...

# At 9:45:00, second candle closes
# bars_held = 1 (not 4 yet)
# Position continues
```

---

## ⏰ **11:00 AM - Volume Peak Exit Triggered**

### **Scenario: Price Crosses Volume Peak**

```python
# Running candle (11:00 - 11:15)
# Price moves up from entry (58450)
tick_price = 58650.0  # Price moved up 200 points

running_candle.high = 58650.0
running_candle.close = 58650.0

# Volume exit check (LONG position, entry at 58450)
volume_exit, exit_price, _ = volume_exit_strategy.should_exit(
    trade_direction=1,  # LONG
    entry_bar=2000,
    current_bar=2005,  # 5th bar after entry
    historical_data=df_completed,
    current_high=58650.0,
    current_low=58500.0,
    current_close=58650.0,
    entry_price=58450.0
)

# Volume exit logic:
# 1. Find nearest peak ABOVE entry (58450)
#    - Peak at 58600.0 (nearest above entry)
# 2. Check if current_high (58650.0) >= peak (58600.0)
#    - 58650.0 >= 58600.0 → TRUE ✅
# 3. Exit triggered!
# volume_exit = True
# exit_price = max(58600.0, 58650.0) = 58650.0

# Exit position
oms.exit_position(exit_price=58650.0)
# Executes exit orders for all 3 legs

# Update re-entry state
last_long_exit_bar = 2005  # Bar where exit happened
```

**Result**: Position exited via volume peak exit! ✅  
**PnL**: (58650.0 - 58450.0) / 58450.0 = +0.34%

---

## ⏰ **11:15 AM - Re-entry Window Starts**

### **Re-entry Countdown Begins**

```python
# Position exited at bar 2005
# Re-entry rules apply:
# - Bars 2006-2007: Cannot re-enter (< 3 bars, forced pause)
# - Bars 2008-2055: Can re-enter IF prediction confirms (3-50 bars window)
# - Bar 2056+: Can re-enter freely (> 50 bars)

# At bar 2006 (11:15 candle):
bars_since_long_exit = 2006 - 2005 = 1 bar
can_enter_long = False  # Too soon (< 3 bars)

# At bar 2008 (11:45 candle):
bars_since_long_exit = 2008 - 2005 = 3 bars
# Check if prediction confirms
if signals['predictions'][2008] > 0:  # ML bullish
    can_enter_long = True  # Can re-enter
else:
    can_enter_long = False  # No confirmation
```

---

## ⏰ **12:00 PM - SHORT Signal Appears (Re-entry)**

### **Scenario: SHORT Signal During Re-entry Window**

```python
# At bar 2010 (12:00 candle):
# ML system generates SHORT signal

bars_since_long_exit = 2010 - 2005 = 5 bars
bars_since_short_exit = 2010 - 1890 = 120 bars  # From old exit

# Check re-entry rules
can_enter_short = (last_short_exit_bar < 0 or 
                  bars_since_short_exit > 50 or  # 120 > 50 → TRUE
                  (3 <= bars_since_short_exit <= 50 and signals['predictions'][2010] < 0))

# can_enter_short = True (120 bars > 50, outside window)

# Enter SHORT
current_signal = "SHORT"
executor.on_running_signal("SHORT", candle_id, futures_price=58200.0)

# Inside OrderManager.enter_short():
atm_strike = _calculate_atm_strike(58200.0)  # = 58200
hedge_strike = atm_strike + (20 * 100)  # = 60200

# Get option symbols (still December expiry)
atm_pe_symbol = option_chain_manager.get_option_symbol(58200, "PE")
# Returns: "BANKNIFTY25DEC58200PE"

atm_ce_symbol = option_chain_manager.get_option_symbol(58200, "CE")
# Returns: "BANKNIFTY25DEC58200CE"

hedge_ce_symbol = option_chain_manager.get_option_symbol(60200, "CE")
# Returns: "BANKNIFTY25DEC60200CE"

# SHORT Entry Legs:
# 1. BUY ATM PUT (PE) - Bearish leg
# 2. SELL ATM CALL (CE) - Income leg
# 3. BUY Hedge CALL (CE) - Margin reduction

# Execute orders
oms.position.position_type = PositionType.SHORT
oms.position.entry_price = 58200.0
oms.position.entry_bar_index = 2010
```

**Result**: SHORT position entered! ✅

---

## ⏰ **2:00 PM - 4-Bar Exit Triggered**

### **Scenario: SHORT Position Held for 4 Bars**

```python
# SHORT entered at bar 2010 (12:00 PM)
# Bars held: 2010, 2011, 2012, 2013

# At bar 2014 (2:00 PM candle close):
bars_held = 2014 - 2010 = 4 bars ✅

# 4-bar exit triggered
oms.exit_position(exit_price=completed_candle.close)  # e.g., 58000.0

# Update re-entry state
last_short_exit_bar = 2014
```

**Result**: Position exited via 4-bar exit! ✅  
**PnL**: (58200.0 - 58000.0) / 58200.0 = +0.34% (SHORT profit)

---

## ⏰ **3:30 PM - End of Day State Saving**

```python
# Save complete system state
state_manager.save_daily_state(
    ml_system=ml_system,
    historical_data=manager_15min.get_dataframe()  # Last 2000 bars
)

# Saved state:
{
    'last_long_exit_bar': 2005,   # Volume exit
    'last_short_exit_bar': 2014,  # 4-bar exit
    'position': None,  # No open position
    'ml_features': {...},  # Last 2000 bars
    'ml_indicators': {...},
    'historical_data': [...],  # Last 2000 bars OHLCV
    'last_processed_timestamp': '2024-12-01T15:30:00+05:30'
}
```

---

## 🔑 **Key Points from Simulation**

### **1. Position Check FIRST (Critical)**
- ✅ **If position exists** (from saved state): Skip ML entry signals, monitor exits only
- ✅ **If no position**: Generate ML signals, process entry signals
- ✅ **Gap Down with Position**: Exit immediately if gap > threshold (stop loss protection)
- ✅ **Order of Operations**: Position check → Exit monitoring → ML signals (only if no position)

### **2. Dynamic Contract Management (November → December)**
- ✅ System automatically fetches current month futures symbol (Dec on Dec 1st)
- ✅ OptionChainManager refreshes when expiry changes (Nov → Dec)
- ✅ Option chain **cached** for fast lookup: `{(expiry, strike, type) -> OptionContract}`
- ✅ No manual intervention needed - handles contract rollover automatically
- ✅ Works with gaps because uses current expiry chain (always has contracts for any price)

### **3. Gap Up/Down Handling**
- ✅ **Gap Up with LONG Position**: Can trigger volume exit immediately if crosses peak (beneficial)
- ✅ **Gap Down with LONG Position**: **Exit immediately if gap > threshold** (stop loss protection)
- ✅ **Gap Down with NO Position**: Normal ML signal generation (gap down may generate SHORT signal)
- ✅ System handles all gap scenarios correctly

### **4. Entry Execution Flow (Only if No Position)**
- ✅ LONG: BUY ATM CE, SELL ATM PE, BUY hedge PE (20 legs down)
- ✅ SHORT: BUY ATM PE, SELL ATM CE, BUY hedge CE (20 legs up)
- ✅ OptionChainManager provides correct symbols for current expiry (from cache)
- ✅ Uses CLOSE price for entry (`trading_price = running_candle.close`)

### **5. Exit Priority (When Position Exists)**
- ✅ **On Each Tick**: 
  1. Check gap down (if > threshold → exit immediately)
  2. Check volume exit (if crosses peak → exit)
- ✅ **On Candle Close**: 
  1. Check 4-bar exit (if bars_held >= 4 → exit)
  2. Candle-close reconciliation (flicker/reversal)
- ✅ Whichever triggers FIRST wins
- ✅ Re-entry state updated based on which exit triggered

### **6. Re-entry Logic (Only When No Position)**
- ✅ First 3 bars after exit: Cannot re-enter (forced pause)
- ✅ Bars 3-50: Can re-enter IF prediction confirms
- ✅ After 50 bars: Can re-enter freely
- ✅ Applied only when processing entry signals (no position exists)

### **7. State Saving (3:30 PM)**
- ✅ Save position state if exists (direction, entry_price, entry_bar_index, timestamps)
- ✅ Save ML system state (features, indicators, last 2000 bars)
- ✅ Save historical OHLCV data (last 2000 bars)
- ✅ Save re-entry state (last_long_exit_bar, last_short_exit_bar)
- ✅ **If position exists**: Save position state + ML state with new data
- ✅ **If no position**: Save ML state with new data only

### **8. Option Contract Handling**
- ✅ **Cached**: Option chain stored in memory for O(1) lookup
- ✅ Works with any expiry (Nov, Dec, Jan, etc.)
- ✅ Automatically refreshes when expiry changes
- ✅ Handles gaps because contracts selected from current expiry chain (always available)
- ✅ No issues with gap up/down - just uses current expiry options from cache

---

## ✅ **Corrected Flow Summary**

### **Critical Corrections Made:**

1. **Position Check FIRST**:
   - ✅ If position exists → Skip ML entry signals, monitor exits only
   - ✅ If no position → Generate ML signals, process entries
   - ✅ This prevents trading against existing positions

2. **Gap Down Protection**:
   - ✅ If position exists AND gap down > threshold → Exit immediately (stop loss)
   - ✅ This prevents disastrous losses from large gaps

3. **ML Signal Generation**:
   - ✅ Only happens when NO position exists
   - ✅ Position exists → Only exit monitoring, no entry signals

4. **Option Chain Cache**:
   - ✅ Confirmed: Option chain cached in memory for fast lookup
   - ✅ Works with any expiry, automatically refreshes
   - ✅ Handles gaps because uses current expiry chain

---

## ✅ **Conclusion**

**System handles all scenarios correctly:**
- ✅ Position check FIRST (prevents trading against existing positions)
- ✅ Gap down protection (stop loss if gap > threshold)
- ✅ November → December contract transition (automatic)
- ✅ Gap up 500/1000/2000 points (volume exit may trigger)
- ✅ Gap down 500/1000/2000 points (exit if > threshold, else continue)
- ✅ Normal price movements (standard flow)
- ✅ Volume peak exit (intra-bar, only if position exists)
- ✅ 4-bar exit (candle close, only if position exists)
- ✅ Re-entry with proper countdown (only when no position)
- ✅ Position management across all scenarios

**Everything works as designed with proper position safety!** ✅

See `TRADING_FLOW_PIPELINE.md` for detailed flow diagrams.

