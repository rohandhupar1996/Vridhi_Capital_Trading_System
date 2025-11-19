# Live Trading System - Complete Implementation Guide

## 🎯 **Goal**
Build live trading system that runs continuously like Pine Script on TradingView, starting tomorrow at 9:15 AM with Zerodha data.

**Development Approach**: Step-by-step, test each component as we add it. No rushing.

---

## 📋 **Table of Contents**

1. [System Startup (Before 9:15 AM)](#1-system-startup-before-915-am)
2. [Position Check (Critical First Step)](#2-position-check-critical-first-step)
3. [Tick Processing Loop (9:15 AM Onwards)](#3-tick-processing-loop-915-am-onwards)
4. [Signal Generation on Running Candle](#4-signal-generation-on-running-candle)
5. [Entry Execution Flow](#5-entry-execution-flow)
6. [Exit Strategy Flow](#6-exit-strategy-flow)
7. [Candle Close Processing](#7-candle-close-processing)
8. [Daily State Saving (3:30 PM)](#8-daily-state-saving-330-pm)

---

## 1. System Startup (Before 9:15 AM)

### **Step 1.1: Load Saved State**
**File**: `src/trading_system/data/trading_state_manager.py`

```python
# On startup (9:15 AM):
state_manager = TradingStateManager(db_path)

# Load saved state (from yesterday 3:30 PM or from backtest)
saved_state = state_manager.load_saved_state()

# Extract re-entry state (bar indices):
last_long_exit_bar = saved_state.get('last_long_exit_bar', -1)
last_short_exit_bar = saved_state.get('last_short_exit_bar', -1)

# Load position state (if any):
position_dict = saved_state.get('position')
if position_dict:
    # Position exists from saved state
    saved_position = {
        'direction': position_dict['direction'],  # 'LONG' or 'SHORT'
        'entry_price': position_dict['entry_price'],
        'entry_bar_index': position_dict['entry_bar_index'],
        'entry_timestamp': datetime.fromisoformat(position_dict['entry_timestamp']),
        'atm_strike': position_dict.get('atm_strike'),
        'hedge_strike': position_dict.get('hedge_strike')
    }
else:
    saved_position = None

# Load historical OHLCV data (from saved state, no database pull needed)
historical_df = pd.DataFrame(saved_state.get('historical_data', []))
if historical_df.empty:
    # Fallback: Load from database if saved state missing
    historical_df = load_from_database(last_n_bars=2000)

# Load ML system state (features, indicators, predictions)
ml_features = saved_state.get('ml_features', {})
ml_indicators = saved_state.get('ml_indicators', {})
ml_predictions = saved_state.get('ml_predictions', [])
ml_signals = saved_state.get('ml_signals', [])
```

### **Step 1.2: Initialize Historical Data Manager**
**File**: `src/trading_system/data/live_data_manager.py`

```python
# Load historical 15min OHLCV data (contract-agnostic)
manager_15min = LiveDataManager(
    config=config,
    symbol="",  # Will be set after loading
    timeframe='15min',
    max_bars_back=2000,  # Rolling buffer size
    use_zerodha_table=True  # Use ohlcv_zerodha table
)

# Load by timeframe only (ignores symbol for continuity across contract rollovers)
manager_15min.initialize_contract_agnostic()

# Get current month futures symbol dynamically
current_symbol, current_token = get_current_month_futures_symbol_and_token(kite)
# Example: "BANKNIFTY25DECFUT" (December contract)

# Update symbol in manager
manager_15min.update_symbol(current_symbol)

# Get DataFrame for ML system (last 2000 bars)
df_15min = manager_15min.get_dataframe()  # Contains historical OHLCV data
```

### **Step 1.3: Initialize ML System (Restore State)**
**File**: `src/strategy/core/trading_system.py`

```python
# Initialize ML system with settings
ml_settings = TradingSettings(
    neighbors_count=8,
    # ... other settings
)

ml_system = LorentzianTradingSystem(ml_settings)

# Restore ML system state from saved state (fast, no recalculation)
if saved_state and 'ml_features' in saved_state and ml_features:
    ml_system.restore_state(
        features=ml_features,  # f1-f5, last 2000 bars
        indicators=ml_indicators,  # RSI, CCI, filters, etc.
        predictions=ml_predictions,
        signals=ml_signals
    )
    # System ready immediately - features stay intact like Pine Script
else:
    # Option 2: First time - calculate from historical data
    # (Only if saved state doesn't exist, e.g., first day from backtest)
    results = ml_system.generate_signals(
        high=df_15min['high'].values,
        low=df_15min['low'].values,
        close=df_15min['close'].values,
        start_bar=200  # Warmup period
    )
```

### **Step 1.4: Initialize Volume Exit System**
**File**: `src/strategy/backtest/volume_node_exit.py`

```python
# Initialize volume exit detector (if enabled)
volume_exit_strategy = VolumeNodeExitStrategy(
    default_exit_bars=4,
    use_volume_exit=True,  # or volume_exit_long/volume_exit_short
    volume_lookback=240,  # Optimized: 240 bars (~60 hours of 15min data)
    volume_num_rows=60,   # Optimized: 60 price levels
    volume_exit_value_area=0.7,
    volume_exit_peak_percent=0.09,
    volume_exit_trough_percent=0.07,
    volume_exit_threshold=0.01
)

# Volume profile will be computed on first completed candle
```

### **Step 1.5: Initialize Candle Aggregator**
**File**: `src/trading_system/data/zerodha_candle_aggregator.py`

```python
# Initialize aggregator with current symbol
candle_aggregator = ZerodhaCandleAggregator(
    config=config,
    kite=kite,
    symbol=current_symbol,  # "BANKNIFTY25DECFUT"
    logger=logger
)

candle_aggregator.initialize()
```

### **Step 1.6: Initialize OMS (Order Management System)**
**File**: `src/trading_system/oms/order_manager.py`

```python
# Initialize OMS
oms = OrderManager(
    kite=kite,
    lot_size=8,
    hedge_legs=20,
    logger=oms_logger
)

# OptionChainManager automatically fetches option chain on init
# Current expiry: December expiry (e.g., 2024-12-26)
# Caches: {(expiry, strike, type) -> OptionContract}

# Initialize signal executor
executor = RunningSignalExecutor(oms, earnings_filter, logger)
```

### **Step 1.7: Get Futures Previous Close (For Gap Calculation)**

```python
# Get futures previous close (last completed candle's close from previous day)
# This is needed for gap calculation (futures today open vs futures previous close)
# IMPORTANT: We're trading OPTIONS, but gap is calculated using FUTURES prices

# Try to load from saved state first (from yesterday 3:30 PM)
saved_futures_previous_close = saved_state.get('futures_previous_close')

if saved_futures_previous_close:
    # Load from saved state (from yesterday 3:30 PM)
    futures_previous_close = saved_futures_previous_close
    logger.info(f"✅ Futures previous close loaded from saved state: {futures_previous_close:.2f}")
else:
    # Fallback: Get from last completed candle in historical data
    df_completed = manager_15min.get_dataframe()
    
    if len(df_completed) > 0:
        # Get last completed candle's close (from previous day or historical data)
        futures_previous_close = df_completed.iloc[-1]['close']
        logger.info(f"✅ Futures previous close from historical data: {futures_previous_close:.2f}")
    else:
        # No historical data (first run) - use current price as fallback
        futures_previous_close = oms.futures_ltp if oms.futures_ltp else None
        logger.warning("⚠️ No historical data - using current price as previous close fallback")
```

**Key Points**: 
- Gap calculation uses **FUTURES prices** (previous close vs today open)
- **NOT** option entry price (we're trading options but gap is measured on underlying futures)
- Previous close is saved at 3:30 PM and loaded next morning for gap calculation
- This gives accurate gap measurement for stop loss protection

---

## 2. Position Check (Critical First Step)

### **⚠️ CRITICAL: Check Position FIRST Before Processing Any Signals**

```python
# After startup, check if position exists from saved state
if saved_position:
    # Position exists from saved state (from yesterday 3:30 PM or backtest)
    # Restore position to OMS
    oms.position.position_type = PositionType.LONG if saved_position['direction'] == 'LONG' else PositionType.SHORT
    oms.position.entry_price = saved_position['entry_price']
    oms.position.entry_bar_index = saved_position['entry_bar_index']
    oms.position.entry_time = saved_position['entry_timestamp']
    oms.position.atm_strike = saved_position.get('atm_strike')
    oms.position.hedge_strike = saved_position.get('hedge_strike')
    
    logger.info(f"✅ Position restored: {oms.position.position_type.value} at {oms.position.entry_price}, bar {oms.position.entry_bar_index}")
    
    # IMPORTANT: Position exists → Only monitor exits, NO ML signal generation for entry
    position_exists = True
else:
    # No position → Ready for new entries
    position_exists = False
```

**Key Principle**: 
- **If position exists** → Skip ML entry signals, monitor exits only (volume exit, 4-bar exit, gap down protection)
- **If no position** → Generate ML signals, process entries

---

## 3. Tick Processing Loop (9:15 AM Onwards)

### **Main Loop Structure**

```python
def main_live_trading_loop():
    """Main live trading loop - runs continuously"""
    
    # Start WebSocket price feed
    price_feed = WebSocketPriceFeed(kite, futures_token, oms, logger)
    price_feed.start()
    
    # Initialize futures_previous_close (from Step 1.7)
    futures_previous_close = get_futures_previous_close()  # Loaded from saved state or historical data
    
    while running:
        # Get latest tick from WebSocket
        if price_feed.has_new_tick():
            tick_price = oms.futures_ltp
            tick_volume = price_feed.last_tick_volume or 0
            tick_time = datetime.now(KOLKATA_TZ)
            
            # Process tick into running candle
            completed_candles = process_tick(tick_price, tick_volume, tick_time, futures_previous_close)
            
            # Check for completed candles
            if completed_candles and completed_candles.get('15min'):
                # Update futures_previous_close after candle close (for next day gap check)
                futures_previous_close = process_candle_close(completed_candles['15min'], futures_previous_close)

def process_tick(tick_price, tick_volume, tick_time, futures_previous_close):
    """Process each incoming tick"""
    
    # Step 1: Update running candle
    completed_candles = candle_aggregator.on_tick(
        price=tick_price,
        volume=tick_volume,
        timestamp=tick_time
    )
    # Result: completed_candles = {'15min': None}  # Candle still running
    
    # Get current running candle
    running_candle_15min = candle_aggregator.running_candles['15min']
    
    # Step 2: Check position FIRST
    if oms.position.position_type != PositionType.NONE:
        # Position exists → Handle exits only
        handle_exits_on_tick(running_candle_15min, futures_previous_close)
    else:
        # No position → Generate ML signals and process entries
        handle_entry_on_tick(running_candle_15min)
    
    # Return completed candles (if any) for candle close processing
    return completed_candles
```

---

## 4. Signal Generation on Running Candle

### **Step 4.1: Generate ML Signals (Only if No Position)**

```python
def handle_entry_on_tick(running_candle_15min):
    """Handle entry signals when no position exists"""
    
    # Get historical completed bars (last 2000 bars)
    df_completed = manager_15min.get_dataframe()
    
    # Create temporary DataFrame with running candle included
    running_bar = pd.DataFrame({
        'timestamp': [running_candle_15min.timestamp],
        'open': [running_candle_15min.open],
        'high': [running_candle_15min.high],   # Updates as ticks come in
        'low': [running_candle_15min.low],     # Updates as ticks come in
        'close': [running_candle_15min.close], # Updates as ticks come in
        'volume': [running_candle_15min.volume]
    })
    
    # Append running candle to historical data (temporary, for ML calculation)
    df_with_running = pd.concat([df_completed, running_bar], ignore_index=True)
    
    # Generate ML signals on RUNNING candle (like TradingView)
    current_bar_index = len(df_with_running) - 1  # Index of running candle
    
    signals = ml_system.generate_signals(
        high=df_with_running['high'].values,
        low=df_with_running['low'].values,
        close=df_with_running['close'].values,
        start_bar=current_bar_index  # Process latest bar only (running candle)
    )
    
    # Determine current signal from running candle
    # IMPORTANT: Signal based on CLOSE price, not high/low/open
    if signals['start_long'][current_bar_index]:
        current_signal = "LONG"
    elif signals['start_short'][current_bar_index]:
        current_signal = "SHORT"
    else:
        current_signal = "NONE"
```

### **Step 4.2: Apply Re-entry Logic**

```python
    # Apply re-entry logic (only if no position)
    current_bar_index_completed = len(df_completed)  # Index in completed bars
    
    bars_since_long_exit = current_bar_index_completed - last_long_exit_bar if last_long_exit_bar >= 0 else -1
    bars_since_short_exit = current_bar_index_completed - last_short_exit_bar if last_short_exit_bar >= 0 else -1
    
    # Re-entry window: 3-50 bars
    # - Bars 0-2: Cannot re-enter (forced pause)
    # - Bars 3-50: Can re-enter IF prediction confirms
    # - Bars 51+: Can re-enter freely
    
    can_enter_long = (
        last_long_exit_bar < 0 or  # Never traded LONG before
        bars_since_long_exit > 50 or  # Outside re-entry window (free entry)
        (3 <= bars_since_long_exit <= 50 and signals['predictions'][current_bar_index] > 0)  # Within window + prediction confirms
    )
    
    can_enter_short = (
        last_short_exit_bar < 0 or  # Never traded SHORT before
        bars_since_short_exit > 50 or  # Outside re-entry window (free entry)
        (3 <= bars_since_short_exit <= 50 and signals['predictions'][current_bar_index] < 0)  # Within window + prediction confirms
    )
    
    # Block entry if re-entry rules prevent it
    if current_signal == "LONG" and not can_enter_long:
        current_signal = "NONE"  # Block entry
    elif current_signal == "SHORT" and not can_enter_short:
        current_signal = "NONE"  # Block entry
```

### **Step 4.3: Process Entry Signal via RunningSignalExecutor**

```python
    # Process entry signal via RunningSignalExecutor
    if current_signal != "NONE":
        # IMPORTANT: Use CLOSE price for trading (not high/low/open)
        trading_price = running_candle_15min.close
        
        candle_id = running_candle_15min.timestamp.strftime("%Y-%m-%d %H:%M:%S_15min")
        
        # Call executor with signal (handles immediate entry/reversal)
        executor.on_running_signal(current_signal, candle_id, trading_price)
        
        # After entry, check volume exit on SAME candle (momentum case)
        if oms.position.position_type != PositionType.NONE:
            # Position just entered - check volume exit immediately
            check_volume_exit_on_tick(running_candle_15min)
```

---

## 5. Entry Execution Flow

### **Step 5.1: RunningSignalExecutor.on_running_signal()**

```python
# Inside RunningSignalExecutor.on_running_signal():
def on_running_signal(self, signal: str, candle_id: str, price: float):
    """
    Handle signal on running candle (intra-bar entry/reversal)
    
    Args:
        signal: "LONG", "SHORT", "NONE"
        candle_id: Candle identifier
        price: Trading price (CLOSE price of running candle)
    """
    
    # Check current position
    pos_type = self.oms.position.position_type.value if self.oms.position.position_type != PositionType.NONE else "NONE"
    
    # Case 1: No position → Enter new position
    if pos_type == "NONE":
        if signal == "LONG":
            # Enter LONG position
            success = self.oms.enter_long(fast_execution=False)
            if success:
                logger.info(f"✅ LONG position entered at {price}")
        elif signal == "SHORT":
            # Enter SHORT position
            success = self.oms.enter_short(fast_execution=False)
            if success:
                logger.info(f"✅ SHORT position entered at {price}")
    
    # Case 2: Position exists → Handle reversal
    elif pos_type == "LONG" and signal == "SHORT":
        # Reversal: Exit LONG, enter SHORT
        self.oms.exit_position(exit_price=price)
        self.oms.enter_short(fast_execution=False)
        logger.info(f"🔄 Reversal: LONG → SHORT at {price}")
        # Note: Reversal exits do NOT update re-entry state (OMS-level protection)
    
    elif pos_type == "SHORT" and signal == "LONG":
        # Reversal: Exit SHORT, enter LONG
        self.oms.exit_position(exit_price=price)
        self.oms.enter_long(fast_execution=False)
        logger.info(f"🔄 Reversal: SHORT → LONG at {price}")
        # Note: Reversal exits do NOT update re-entry state (OMS-level protection)
```

### **Step 5.2: OrderManager.enter_long()**

```python
# Inside OrderManager.enter_long():
def enter_long(self, fast_execution: bool = False) -> bool:
    """
    Enter LONG position:
    - BUY ATM CALL (CE) - Bullish leg
    - SELL ATM PUT (PE) - Income leg
    - BUY 20 legs down PUT (PE) - Margin reduction (hedge)
    """
    
    # 1. Get futures price
    futures_ltp = self.futures_ltp  # From WebSocket
    
    # 2. Calculate ATM strike (round to nearest 100)
    atm_strike = self._calculate_atm_strike(futures_ltp)
    # Example: futures_ltp = 58450.0 → atm_strike = 58400
    
    # 3. Calculate hedge strike (20 legs down for LONG)
    hedge_strike = atm_strike - (self.hedge_legs * 100)
    # Example: 58400 - 2000 = 56400
    
    # 4. Check margin availability
    if not fast_execution:
        margin_ok, required_margin = self.check_margin_availability('LONG', self.lot_size)
        if not margin_ok:
            logger.warning("Insufficient margin for LONG entry")
            return False
    
    # 5. Get option symbols via OptionChainManager (from cache)
    current_expiry = self.option_chain_manager.get_current_expiry()
    
    # Check if expiry changed (Nov → Dec transition)
    if current_expiry and current_expiry.date() < datetime.now().date():
        # Expiry has passed! Refresh option chain
        self.option_chain_manager.refresh_option_chain()
        current_expiry = self.option_chain_manager.get_current_expiry()
    
    # Get option symbols for current expiry
    atm_ce_symbol = self.option_chain_manager.get_option_symbol(atm_strike, "CE", expiry=current_expiry)
    # Example: "BANKNIFTY25DEC58400CE"
    
    atm_pe_symbol = self.option_chain_manager.get_option_symbol(atm_strike, "PE", expiry=current_expiry)
    # Example: "BANKNIFTY25DEC58400PE"
    
    hedge_pe_symbol = self.option_chain_manager.get_option_symbol(hedge_strike, "PE", expiry=current_expiry)
    # Example: "BANKNIFTY25DEC56400PE"
    
    # 6. Execute 3-leg strategy
    # Step 1: Execute BUY legs first
    buy_legs = [
        OrderLeg(symbol=atm_ce_symbol, quantity=8*35, transaction_type="BUY"),   # BUY ATM CE
        OrderLeg(symbol=hedge_pe_symbol, quantity=8*35, transaction_type="BUY")  # BUY hedge PE
    ]
    
    buy_success = self._execute_legs(buy_legs, "BUY")
    if not buy_success:
        logger.error("BUY legs failed")
        return False
    
    # Step 2: Execute SELL leg after buys complete
    sell_legs = [
        OrderLeg(symbol=atm_pe_symbol, quantity=8*35, transaction_type="SELL")  # SELL ATM PE
    ]
    
    sell_success = self._execute_legs(sell_legs, "SELL", allow_partial=True)
    if not sell_success:
        logger.error("SELL leg failed")
        self._exit_partial_positions()
        return False
    
    # 7. Update position state
    self.position.position_type = PositionType.LONG
    self.position.entry_price = futures_ltp  # Entry price (futures close price)
    self.position.entry_bar_index = len(manager_15min.get_dataframe())  # Current bar index
    self.position.entry_time = datetime.now(KOLKATA_TZ)
    self.position.atm_strike = atm_strike
    self.position.hedge_strike = hedge_strike
    self.position.lot_size = self.lot_size
    
    logger.info(f"✅ LONG position entered: Entry={futures_ltp}, ATM={atm_strike}, Hedge={hedge_strike}")
    
    return True
```

### **Step 5.3: OrderManager.enter_short()**

```python
# Inside OrderManager.enter_short():
def enter_short(self, fast_execution: bool = False) -> bool:
    """
    Enter SHORT position:
    - BUY ATM PUT (PE) - Bearish leg
    - SELL ATM CALL (CE) - Income leg
    - BUY 20 legs up CALL (CE) - Margin reduction (hedge)
    """
    
    # Similar flow as enter_long(), but:
    # - BUY ATM PE (instead of CE)
    # - SELL ATM CE (instead of PE)
    # - BUY hedge CE 20 legs UP (instead of PE 20 legs down)
    
    hedge_strike = atm_strike + (self.hedge_legs * 100)  # 20 legs UP for SHORT
    
    # Rest of the flow is similar...
```

---

## 6. Exit Strategy Flow

### **Step 6.1: Exit Checks on Each Tick (If Position Exists)**

```python
def handle_exits_on_tick(running_candle_15min, futures_previous_close):
    """Handle exits when position exists"""
    
    # Step 1: Check gap protection (gap up/down based on position direction)
    # IMPORTANT: Gap is calculated using FUTURES prices (previous close vs today open)
    # NOT option entry price
    gap_check(running_candle_15min, futures_previous_close)
    
    # Step 2: Check volume exit (intra-bar)
    check_volume_exit_on_tick(running_candle_15min)
    
    # Note: ML signal generation is SKIPPED when position exists

def gap_check(running_candle_15min, futures_previous_close):
    """
    Check gap up/down using FUTURES prices and exit if adverse gap exceeds threshold.
    
    IMPORTANT: We're trading OPTIONS, but gap is calculated using FUTURES prices:
    - Gap = futures_today_open - futures_previous_close
    
    Rules:
    - LONG position + Gap DOWN (adverse) → Exit immediately if > threshold
    - LONG position + Gap UP (favorable) → Continue normally, exit on 4-bar
    - SHORT position + Gap UP (adverse) → Exit immediately if > threshold
    - SHORT position + Gap DOWN (favorable) → Continue normally, exit on 4-bar
    """
    
    if oms.position.position_type == PositionType.NONE:
        return  # No position, skip
    
    # Get futures current open (from running candle - this is futures price)
    futures_current_open = running_candle_15min.open  # Futures open price
    
    # Calculate gap using FUTURES prices (not option entry price)
    gap_points = futures_current_open - futures_previous_close
    gap_percent = (gap_points / futures_previous_close) * 100 if futures_previous_close > 0 else 0
    
    # Gap threshold (configurable, e.g., 300 points = ~0.5% loss)
    gap_threshold = 300
    
    if oms.position.position_type == PositionType.LONG:
        # LONG position: Gap DOWN is adverse (bad), Gap UP is favorable (good)
        if gap_points < -gap_threshold:  # Gap DOWN exceeds threshold
            # ⚠️ ADVERSE GAP DOWN → Exit immediately (stop loss)
            logger.critical(
                f"⚠️ GAP DOWN DETECTED (LONG): {abs(gap_points):.2f} points ({abs(gap_percent):.2f}%) - "
                f"Previous Close={futures_previous_close:.2f}, Today Open={futures_current_open:.2f} - "
                f"Exiting position immediately"
            )
            
            # Exit position at futures open price (immediate stop loss)
            oms.exit_position(exit_price=futures_current_open)
            
            # Update re-entry state
            last_long_exit_bar = len(manager_15min.get_dataframe())
            
            logger.info(
                f"✅ LONG position exited due to gap down: "
                f"Entry={oms.position.entry_price}, Exit={futures_current_open:.2f}, "
                f"Gap Loss={abs(gap_percent):.2f}%"
            )
            
            # Position cleared - now system can generate ML signals for new entries
        else:
            # Gap up (favorable) OR small gap down → Continue normally
            # Exit will happen on 4-bar held exit or volume exit
            pass
    
    elif oms.position.position_type == PositionType.SHORT:
        # SHORT position: Gap UP is adverse (bad), Gap DOWN is favorable (good)
        if gap_points > gap_threshold:  # Gap UP exceeds threshold
            # ⚠️ ADVERSE GAP UP → Exit immediately (stop loss)
            logger.critical(
                f"⚠️ GAP UP DETECTED (SHORT): {gap_points:.2f} points ({gap_percent:.2f}%) - "
                f"Previous Close={futures_previous_close:.2f}, Today Open={futures_current_open:.2f} - "
                f"Exiting position immediately"
            )
            
            # Exit position at futures open price (immediate stop loss)
            oms.exit_position(exit_price=futures_current_open)
            
            # Update re-entry state
            last_short_exit_bar = len(manager_15min.get_dataframe())
            
            logger.info(
                f"✅ SHORT position exited due to gap up: "
                f"Entry={oms.position.entry_price}, Exit={futures_current_open:.2f}, "
                f"Gap Loss={gap_percent:.2f}%"
            )
            
            # Position cleared - now system can generate ML signals for new entries
        else:
            # Gap down (favorable) OR small gap up → Continue normally
            # Exit will happen on 4-bar held exit or volume exit
            pass
```

<｜tool▁calls▁begin｜><｜tool▁call▁begin｜>
read_file

def check_volume_exit_on_tick(running_candle_15min):
    """Check volume exit on each tick (if in position)"""
    
    if oms.position.position_type == PositionType.NONE:
        return  # No position, skip
    
    # Get historical completed bars for volume profile
    df_completed = manager_15min.get_dataframe()
    
    # Check volume exit using running candle's OHLC
    volume_exit, exit_price, exit_reason = volume_exit_strategy.should_exit(
        trade_direction=oms.position.direction,  # 1 for LONG, -1 for SHORT
        entry_bar=oms.position.entry_bar_index,
        current_bar=len(df_completed),  # Current bar index (same candle if just entered)
        historical_data=df_completed,
        current_high=running_candle_15min.high,   # Running candle high
        current_low=running_candle_15min.low,     # Running candle low
        current_close=running_candle_15min.close, # Running candle close
        entry_price=oms.position.entry_price      # Entry price for peak filtering
    )
    
    if volume_exit:
        # Volume exit triggered on running candle!
        logger.info(f"✅ Volume exit triggered: {exit_reason}, Exit price={exit_price}")
        
        # Exit position
        oms.exit_position(exit_price=exit_price)
        
        # Update re-entry state (volume exit counts as ML exit)
        if oms.position.direction == 1:  # LONG
            last_long_exit_bar = len(df_completed)
        else:  # SHORT
            last_short_exit_bar = len(df_completed)
        
        logger.info(f"✅ Re-entry state updated: last_long_exit_bar={last_long_exit_bar}, last_short_exit_bar={last_short_exit_bar}")
        
        # Position cleared - now system can generate ML signals for new entries
```

### **Step 6.2: Volume Exit Logic (VolumeNodeExitStrategy)**

```python
# Inside VolumeNodeExitStrategy.should_exit():
def should_exit(self, trade_direction, entry_bar, current_bar, historical_data, 
                current_high, current_low, current_close, entry_price):
    """
    Check if volume exit should trigger
    
    For LONG:
    - Find nearest volume peak ABOVE entry price
    - Exit if current_high >= nearest_peak_price
    
    For SHORT:
    - Find nearest volume peak BELOW entry price
    - Exit if current_low <= nearest_peak_price
    """
    
    # Update volume profile if new candle completed
    if current_bar != self._last_computed_bar:
        self._update_volume_profile(historical_data, current_bar)
    
    # Get detected peaks
    peak_prices = self._peak_prices  # All detected peaks
    peak_volumes = self._peak_volumes  # Peak volumes
    
    if trade_direction == 1:  # LONG
        # Filter peaks ABOVE entry price
        directional_peaks = []
        for i, peak_price in enumerate(peak_prices):
            if peak_price > entry_price:  # Only peaks above entry
                directional_peaks.append((peak_price, peak_volumes[i]))
        
        if not directional_peaks:
            return False, None, None  # No peaks above entry
        
        # Find NEAREST peak in upward direction
        nearest_peak_price, nearest_peak_vol = min(
            directional_peaks, 
            key=lambda x: abs(x[0] - entry_price)  # Minimum distance from entry
        )
        
        # Check if price crossed the peak
        if current_high >= nearest_peak_price:
            # Peak crossed! Exit triggered
            exit_price = max(nearest_peak_price, current_close)
            return True, exit_price, f"volume_peak_exit (peak={nearest_peak_price})"
    
    else:  # SHORT
        # Filter peaks BELOW entry price
        directional_peaks = []
        for i, peak_price in enumerate(peak_prices):
            if peak_price < entry_price:  # Only peaks below entry
                directional_peaks.append((peak_price, peak_volumes[i]))
        
        if not directional_peaks:
            return False, None, None  # No peaks below entry
        
        # Find NEAREST peak in downward direction
        nearest_peak_price, nearest_peak_vol = min(
            directional_peaks,
            key=lambda x: abs(x[0] - entry_price)  # Minimum distance from entry
        )
        
        # Check if price crossed the peak
        if current_low <= nearest_peak_price:
            # Peak crossed! Exit triggered
            exit_price = min(nearest_peak_price, current_close)
            return True, exit_price, f"volume_peak_exit (peak={nearest_peak_price})"
    
    return False, None, None  # No exit
```

### **Step 6.3: 4-Bar Exit (On Candle Close)**

```python
def process_candle_close(completed_candle, futures_previous_close):
    """Process candle close (check 4-bar exit)"""
    
    # Candle already stored to DB by candle_aggregator
    # Deque already updated by add_new_bar()
    
    # Get updated DataFrame (completed candle is now in deque)
    df_15min = manager_15min.get_dataframe()
    current_bar_index = len(df_15min) - 1  # Index of completed candle
    
    # Update futures previous close for next day gap check
    # This will be used tomorrow morning for gap calculation
    # Update with completed candle's close (futures price)
    futures_previous_close = completed_candle.close
    logger.debug(f"Updated futures_previous_close: {futures_previous_close:.2f}")
    
    # Check 4-bar exit (if in position) - on candle close
    if oms.position.position_type != PositionType.NONE:
        bars_held = current_bar_index - oms.position.entry_bar_index
        
        if bars_held >= 4:
            # 4-bar exit triggered!
            logger.info(f"✅ 4-bar exit triggered: Bars held={bars_held}")
            
            # Exit position at candle close
            oms.exit_position(exit_price=completed_candle.close)
            
            # Update re-entry state (4-bar exit counts as ML exit)
            if oms.position.direction == 1:  # LONG
                last_long_exit_bar = current_bar_index
            else:  # SHORT
                last_short_exit_bar = current_bar_index
            
            logger.info(f"✅ Re-entry state updated: last_long_exit_bar={last_long_exit_bar}, last_short_exit_bar={last_short_exit_bar}")
    
    # Continue to candle-close reconciliation...
    
    # Return updated futures_previous_close for next iteration/day
    return futures_previous_close
```

---

## 7. Candle Close Processing

### **Step 7.1: Candle-Close Reconciliation (Flicker/Reversal)**

```python
def process_candle_close(completed_candle):
    """Process candle close - reconciliation"""
    
    # Get final signal from completed candle for reconciliation
    df_15min = manager_15min.get_dataframe()
    current_bar_index = len(df_15min) - 1
    
    signals = ml_system.generate_signals(
        high=df_15min['high'].values,
        low=df_15min['low'].values,
        close=df_15min['close'].values,
        start_bar=current_bar_index
    )
    
    # Determine final signal for completed candle
    if signals['start_long'][current_bar_index]:
        final_signal = "LONG"
    elif signals['start_short'][current_bar_index]:
        final_signal = "SHORT"
    else:
        final_signal = "NONE"
    
    # Call executor for candle-close reconciliation (handles flicker/reversal)
    candle_id = completed_candle.timestamp.strftime("%Y-%m-%d %H:%M:%S_15min")
    executor.on_candle_close(final_signal, candle_id, completed_candle.close)
```

### **Step 7.2: RunningSignalExecutor.on_candle_close()**

```python
# Inside RunningSignalExecutor.on_candle_close():
def on_candle_close(self, final_signal: str, candle_id: str, price: float):
    """
    Handle candle-close reconciliation (flicker/reversal cleanup)
    
    This handles:
    - Flicker: Signal appeared during candle but faded at close → exit
    - Reversal: Signal reversed → exit previous and enter new
    
    IMPORTANT: Flicker/reversal exits do NOT update re-entry state
    (Only volume/4-bar exits update re-entry state)
    """
    
    pos_type = self.oms.position.position_type.value if self.oms.position.position_type != PositionType.NONE else "NONE"
    
    # Case 1: Flicker - Position exists but signal faded at close
    if pos_type == "LONG" and final_signal != "LONG":
        # Signal faded → Exit (flicker cleanup)
        self.oms.exit_position(exit_price=price)
        logger.info(f"🔄 Flicker: LONG signal faded at close → Exit")
        # Note: Does NOT update re-entry state (OMS-level protection)
    
    elif pos_type == "SHORT" and final_signal != "SHORT":
        # Signal faded → Exit (flicker cleanup)
        self.oms.exit_position(exit_price=price)
        logger.info(f"🔄 Flicker: SHORT signal faded at close → Exit")
        # Note: Does NOT update re-entry state (OMS-level protection)
    
    # Case 2: Reversal at close
    elif pos_type == "LONG" and final_signal == "SHORT":
        # Reversal: Exit LONG, enter SHORT
        self.oms.exit_position(exit_price=price)
        self.oms.enter_short(fast_execution=False)
        logger.info(f"🔄 Reversal at close: LONG → SHORT")
        # Note: Does NOT update re-entry state (OMS-level protection)
    
    elif pos_type == "SHORT" and final_signal == "LONG":
        # Reversal: Exit SHORT, enter LONG
        self.oms.exit_position(exit_price=price)
        self.oms.enter_long(fast_execution=False)
        logger.info(f"🔄 Reversal at close: SHORT → LONG")
        # Note: Does NOT update re-entry state (OMS-level protection)
```

---

## 8. Daily State Saving (3:30 PM)

### **Step 8.1: Save Complete System State**

```python
def save_daily_state(ml_system, manager_15min, oms, last_long_exit_bar, last_short_exit_bar, futures_previous_close):
    """
    Save complete system state at end of trading day (3:30 PM).
    
    Like Pine Script: Save everything (features, indicators, state) so system
    can continue seamlessly without recalculation.
    """
    
    # Get historical OHLCV data (last 2000 bars)
    historical_df = manager_15min.get_dataframe().tail(2000)
    
    # Get last computed ML results (features, indicators, predictions)
    last_results = ml_system.get_last_results()  # Or store during trading
    
    state = {
        # 1. Re-entry state (bar indices)
        'last_long_exit_bar': last_long_exit_bar,
        'last_short_exit_bar': last_short_exit_bar,
        
        # 2. Position state (if any)
        'position': {
            'direction': oms.position.position_type.value if oms.position.position_type != PositionType.NONE else None,
            'entry_price': oms.position.entry_price if oms.position.position_type != PositionType.NONE else None,
            'entry_bar_index': oms.position.entry_bar_index if oms.position.position_type != PositionType.NONE else None,
            'entry_timestamp': oms.position.entry_time.isoformat() if oms.position.position_type != PositionType.NONE and oms.position.entry_time else None,
            'atm_strike': oms.position.atm_strike if oms.position.position_type != PositionType.NONE else None,
            'hedge_strike': oms.position.hedge_strike if oms.position.position_type != PositionType.NONE else None
        } if oms.position.position_type != PositionType.NONE else None,
        
        # 3. ML System State (features stay intact, like Pine Script)
        'ml_features': {
            'f1': last_results['features']['f1'].tolist()[-2000:],  # Last 2000 bars
            'f2': last_results['features']['f2'].tolist()[-2000:],
            'f3': last_results['features']['f3'].tolist()[-2000:],
            'f4': last_results['features']['f4'].tolist()[-2000:],
            'f5': last_results['features']['f5'].tolist()[-2000:],
        },
        'ml_indicators': {
            'filter_all': last_results['filter_all'].tolist()[-2000:],
            'kernel_estimate': last_results['kernel_estimate'].tolist()[-2000:],
            'is_bullish': last_results.get('is_bullish', []).tolist()[-2000:] if 'is_bullish' in last_results else [],
            'is_bearish': last_results.get('is_bearish', []).tolist()[-2000:] if 'is_bearish' in last_results else [],
        },
        'ml_predictions': last_results['predictions'].tolist()[-2000:] if 'predictions' in last_results else [],
        'ml_signals': last_results['signals'].tolist()[-2000:] if 'signals' in last_results else [],
        
        # 4. Historical OHLCV data (last 2000 bars)
        'historical_data': historical_df.to_dict('records'),
        
        # 5. Futures previous close (for gap calculation next day)
        'futures_previous_close': futures_previous_close,  # Last completed candle's close
        
        # 6. Metadata
        'last_processed_timestamp': datetime.now(KOLKATA_TZ).isoformat(),
        'save_time': datetime.now(KOLKATA_TZ).isoformat(),
        'data_source': 'zerodha'  # Mark that we're using Zerodha data
    }
    
    # Save to database
    state_manager.save_daily_state(state)
    
    logger.info("✅ Daily state saved: Re-entry bars, Position, ML state, Historical data")
```

---

## 📊 **Complete Flow Diagram**

```
┌─────────────────────────────────────────────────────────────────┐
│  STARTUP (Before 9:15 AM)                                        │
│  1. Load saved state (re-entry bars, position, ML state)        │
│  2. Initialize historical data manager (2000 bars)              │
│  3. Restore ML system state (no recalculation)                  │
│  4. Initialize volume exit system                                │
│  5. Initialize candle aggregator                                 │
│  6. Initialize OMS + signal executor                             │
│  7. ⚠️ CRITICAL: Check if position exists from saved state      │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ Position Exists?      │
              └───────────────────────┘
                  │              │
        YES ──────┘              ┘────── NO
                  │                      │
                  ▼                      ▼
┌─────────────────────────────┐  ┌──────────────────────────────┐
│ POSITION EXISTS             │  │ NO POSITION                  │
│ (Monitor Exits ONLY)        │  │ (Generate ML Signals)        │
│                             │  │                              │
│ On Each Tick:               │  │ On Each Tick:                │
│ 1. Check gap down           │  │ 1. Update running candle     │
│ 2. Check volume exit        │  │ 2. Generate ML signals       │
│                             │  │ 3. Apply re-entry logic      │
│ Skip ML signal generation   │  │ 4. Process entry via OMS     │
└─────────────────────────────┘  │ 5. Check volume exit         │
                  │              └──────────────────────────────┘
                  │                      │
                  └──────────┬───────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │  On 15min Candle CLOSE:      │
              │  1. Store candle to DB        │
              │  2. Append to deque           │
              │  3. Check 4-bar exit          │
              │  4. Candle-close reconciliation│
              │     (flicker/reversal)        │
              └──────────────────────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │  End of Day (3:30 PM)        │
              │  Save complete system state  │
              │  (re-entry, position, ML, data)│
              └──────────────────────────────┘
```

---

## ✅ **Key Principles**

### **1. Position Check FIRST**
- **If position exists** → Skip ML entry signals, monitor exits only
- **If no position** → Generate ML signals, process entries

### **2. Signal Generation**
- Generated on **RUNNING candle** (like TradingView)
- Uses **CLOSE price** for trading decisions (not high/low/open)
- Only generated when **NO position exists**

### **3. Exit Priority**
- **Volume exit**: Checked intra-bar (every tick) - triggers FIRST if crosses peak
- **4-bar exit**: Checked on candle close - triggers if bars_held >= 4
- **Gap down protection**: Exit immediately if gap > threshold (stop loss)

### **4. Re-entry State Updates**
- **Volume exit** → Updates re-entry state (`last_long_exit_bar` or `last_short_exit_bar`)
- **4-bar exit** → Updates re-entry state
- **Flicker exit** → Does NOT update re-entry state (OMS-level protection)
- **Reversal exit** → Does NOT update re-entry state (OMS-level protection)

### **5. Entry Execution**
- **LONG**: BUY ATM CE, SELL ATM PE, BUY hedge PE (20 legs down)
- **SHORT**: BUY ATM PE, SELL ATM CE, BUY hedge CE (20 legs up)
- Option chain cached for fast lookup
- Contracts selected from current expiry (handles rollovers)

### **6. Gap Protection Logic**
- **Gap calculation**: Uses **FUTURES prices** (previous close vs today open)
  - NOT option entry price (we're trading options but gap measured on underlying)
- **LONG position**:
  - Gap DOWN (adverse) > threshold → Exit immediately (stop loss)
  - Gap UP (favorable) → Continue normally, exit on 4-bar or volume exit
- **SHORT position**:
  - Gap UP (adverse) > threshold → Exit immediately (stop loss)
  - Gap DOWN (favorable) → Continue normally, exit on 4-bar or volume exit
- **Previous close tracking**: Last completed candle's close (updated on each candle close)

---

## 🧪 **Testing Checklist**

Test each component as we implement:

- [ ] **State Management**: Load/save state works correctly
- [ ] **Position Check**: Position exists → Skip ML signals, monitor exits
- [ ] **Signal Generation**: ML signals generated on running candle (no position)
- [ ] **Entry Execution**: LONG/SHORT entries execute correctly (3-leg strategy)
- [ ] **Volume Exit**: Triggers correctly when price crosses nearest peak
- [ ] **4-Bar Exit**: Triggers correctly after 4 bars held
- [ ] **Gap Down**: Exit immediately if gap > threshold
- [ ] **Re-entry Logic**: Blocks entries during re-entry window correctly
- [ ] **Candle Close**: Flicker/reversal handled correctly (no re-entry update)
- [ ] **Daily State Save**: Complete state saved at 3:30 PM
- [ ] **Daily State Load**: State restored correctly next morning

---

## 📁 **Files to Create/Modify**

### **New Files**:
1. `src/trading_system/data/trading_state_manager.py` - State persistence
2. `scripts/live_trading_integrated.py` - Main live trading script

### **Modified Files**:
1. `src/trading_system/data/live_data_manager.py` - Contract-agnostic loading
2. `src/trading_system/data/zerodha_candle_aggregator.py` - Already 15min only
3. `src/strategy/backtest/volume_node_exit.py` - Already fixed for nearest peak
4. `src/trading_system/oms/running_signal_executor.py` - May need updates

---

**This is the complete, step-by-step implementation guide for live trading system!** ✅

