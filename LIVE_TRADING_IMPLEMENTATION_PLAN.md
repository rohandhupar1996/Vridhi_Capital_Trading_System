# Live Trading System Implementation Plan

## 🎯 **Goal**
Build live trading system that runs continuously like Pine Script on TradingView, starting tomorrow at 9:15 AM with Zerodha data.

---

## ✅ **Confirmed Understanding**

### **1. Starting Point**
- ✅ Backtest already completed (has max_bars_back historical data)
- ✅ Can use saved state from last backtest result
- ✅ Tomorrow: Live trading starts at 9:15 AM IST
- ✅ Load historical 15min OHLCV data (last 2000+ bars)

### **2. Data Flow (From Zerodha)**
- ✅ Incoming tick data from Zerodha starting 9:15 AM
- ✅ Aggregate ticks into 15min candles (OHLCV)
- ✅ On each 15min candle CLOSE: Store OHLCV to database (`ohlcv_zerodha` table)
- ✅ Volume stored with each candle (required for volume profile)

### **3. Decision Timing**
- ✅ **ML signals generated on RUNNING candle** (using current OHLC from forming candle)
  - Like TradingView: Signals visible on running candle, not waiting for close
  - Use running candle's current high/low/close in ML calculations
  - Allows immediate entry/exits based on current price action
  - Prevents missing entry opportunities (prices will be gone if we wait for close)
- ✅ Volume exit checked during candle formation (on tick updates, intra-bar)
- ✅ Flicker/Reversal logic handled by OMS (`RunningSignalExecutor`)
  - **Flicker**: Signal appeared during candle but faded at close → exit (no re-entry impact)
  - **Reversal**: Signal reversed during candle → exit previous and enter new (no re-entry impact)
- ✅ Deque operations applied AFTER candle closes (cleanup/append)
- ✅ **Important**: Flicker/reversal exits do NOT impact ML re-entry state (only volume/4-bar exits do)

### **4. Exit Strategy (Priority)**
- ✅ Volume peak exit OR 4-bar exit (whichever triggers FIRST)
- ✅ Re-entry state tracked based on WHICH exit triggered
- ✅ System continues seamlessly
- ✅ Volume exit: Nearest peak in trade direction (checked intra-bar)
- ✅ 4-bar exit: After 4 bars held (checked on candle close)

### **5. State Continuity (Daily Cycle) - Like Pine Script**
- ✅ **Market doesn't close, just pauses** - Next bar at 9:15 AM is just another bar in continuous stream
- ✅ **What we SAVE (3:30 PM)** - Complete system state (like Pine Script):
  1. **Re-entry state**:
     - `last_long_exit_bar` - Bar index where LONG exited (for re-entry logic)
     - `last_short_exit_bar` - Bar index where SHORT exited (for re-entry logic)
  2. **Position state** (if any):
     - `position` - Current position (direction, entry_price, entry_bar_index, entry_timestamp)
  3. **ML System State** (features stay intact, like Pine Script):
     - Features arrays (f1, f2, f3, f4, f5) - Last 2000 bars
     - Indicators (RSI, CCI, WaveTrend, ADX) - Last 2000 bars
     - ML Classifier state (feature arrays, labels, predictions)
     - Filter states (volatility, regime, ADX filters)
     - Kernel filter state
  4. **Historical OHLCV data**:
     - Last 2000 bars OHLCV (already in database, but save for fast restore)
- ✅ **What we LOAD (9:15 AM)**:
  1. Load saved state (re-entry bars + position + ML system state + historical OHLCV)
  2. Restore ML system with saved features/indicators (no recalculation needed)
  3. Continue processing - next bar at 9:15 AM is just bar #2001 in continuous stream
  4. **No need to pull 2000 bars from database** - already in saved state
  5. **No need to recalculate features** - restore from saved state
- ✅ **Benefits of saving ML state**:
  - Faster startup (no recalculation of 2000 bars)
  - Exact continuity (features stay intact, like Pine Script)
  - System is ready immediately - just process new bars
- ✅ **Data Source Transition**:
  - **From**: TradingView OHLCV data (historical)
  - **To**: Zerodha OHLCV data (live trading)
  - All new bars come from Zerodha and stored in `ohlcv_zerodha` table
  - System gradually transitions: Old TradingView data → New Zerodha data
- ✅ **Continuous operation like Pine Script**:
  - Pine Script: Script state (features, indicators) persists, processes bars sequentially
  - Our system: Same - save complete state, restore, process new bars as continuous stream

---

## 🔧 **Architecture Flow**

### **Live Trading Flow (Step by Step)**

```
┌─────────────────────────────────────────────────────────────┐
│  STARTUP (Before 9:15 AM)                                    │
│  1. Load saved state from backtest                           │
│     - last_long_exit_bar, last_short_exit_bar                │
│     - Position state (if any)                                │
│  2. Load historical 15min OHLCV data (last 2000+ bars)      │
│  3. Initialize ML system with historical data                │
│  4. Initialize volume profile (for volume exit)              │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  9:15 AM: Zerodha Tick Data Starts                           │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  For Each Tick:                                        │  │
│  │  1. Update running 15min candle (OHLCV)                │  │
│  │     - Update high/low/close from tick price            │  │
│  │     - Accumulate volume                                │  │
│  │  2. Check volume exit (if in position):                │  │
│  │     - Get running candle OHLC (high, low, close)       │  │
│  │     - Check if price crosses nearest volume peak       │  │
│  │     - If crossed → Exit immediately                    │  │
│  │  3. Update OMS with latest price                       │  │
│  └───────────────────────────────────────────────────────┘  │
│                    │                                          │
│                    ▼                                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  On 15min Candle CLOSE:                                │  │
│  │  1. Store completed candle OHLCV to database           │  │
│  │  2. Append to deque (rolling buffer)                   │  │
│  │     - Drop oldest if exceeds max_bars_back (2000)      │  │
│  │  3. Check 4-bar exit (if in position):                 │  │
│  │     - Count bars since entry                           │  │
│  │     - If >= 4 bars → Exit at candle close              │  │
│  │     - Update re-entry state (last_long_exit_bar or     │  │
│  │       last_short_exit_bar)                             │  │
│  │  4. Candle-close reconciliation (flicker/reversal):    │  │
│  │     - Check if signal faded at close → exit            │  │
│  │     - Check if signal reversed → exit+enter            │  │
│  │     - Generate final signal from completed candle       │  │
│  │     - Call RunningSignalExecutor.on_candle_close()     │  │
│  │     - Handles flicker (signal faded at close → exit)    │  │
│  │     - Handles reversal (signal reversed → exit+enter)  │  │
│  │     - Note: Flicker/reversal exits do NOT update       │  │
│  │       re-entry state (only volume/4-bar exits do)      │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 **Implementation Steps**

### **Step 1: Load Saved State (9:15 AM) - Restore Complete System**
**File**: `src/trading_system/data/trading_state_manager.py` (to be re-implemented)

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
    position = Position(
        direction=position_dict['direction'],
        entry_price=position_dict['entry_price'],
        entry_bar_index=position_dict['entry_bar_index'],
        entry_timestamp=datetime.fromisoformat(position_dict['entry_timestamp'])
    )
else:
    position = None

# Load historical OHLCV data (from saved state, no database pull needed)
historical_df = pd.DataFrame(saved_state.get('historical_data', []))
if historical_df.empty:
    # Fallback: Load from database if saved state missing
    historical_df = load_from_database(last_n_bars=2000)

# Restore ML system state (features stay intact, like Pine Script)
ml_features = saved_state.get('ml_features', {})
ml_indicators = saved_state.get('ml_indicators', {})
ml_predictions = saved_state.get('ml_predictions', [])
ml_signals = saved_state.get('ml_signals', [])

# Initialize ML system with restored state
ml_system = LorentzianTradingSystem(ml_settings)
ml_system.restore_state(
    features=ml_features,
    indicators=ml_indicators,
    predictions=ml_predictions,
    signals=ml_signals
)

# System is ready - no recalculation needed!
# Next bar at 9:15 AM is just bar #2001 in continuous stream
```

**What to Load**:
- `last_long_exit_bar`: Last bar where LONG exited (from backtest)
- `last_short_exit_bar`: Last bar where SHORT exited (from backtest)
- Position state (if backtest ended with open position)
- Last processed timestamp

---

### **Step 2: Initialize Historical Data**
**File**: `src/trading_system/data/live_data_manager.py`

```python
# Load historical 15min OHLCV data (contract-agnostic)
manager_15min = LiveDataManager(
    config=config,
    symbol="",  # Will be set after loading
    timeframe='15min',
    max_bars_back=3000,
    use_zerodha_table=True
)

# Load by timeframe only (ignores symbol for continuity)
manager_15min.initialize_contract_agnostic()

# Get current futures symbol
current_symbol = get_current_month_futures_symbol(kite)
manager_15min.update_symbol(current_symbol)

# Get DataFrame for ML system
df_15min = manager_15min.get_dataframe()  # Last 3000 bars with volume
```

---

### **Step 3: Initialize ML System (Restore State)**
**File**: `src/strategy/core/trading_system.py`

```python
# Initialize ML system
ml_settings = TradingSettings(
    neighbors_count=8,
    # ... other settings
)

ml_system = LorentzianTradingSystem(ml_settings)

# Option 1: Restore from saved state (fast, no recalculation)
if saved_state and 'ml_features' in saved_state:
    ml_system.restore_state(
        features=saved_state['ml_features'],
        indicators=saved_state['ml_indicators'],
        predictions=saved_state.get('ml_predictions', []),
        signals=saved_state.get('ml_signals', [])
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

**Benefits of State Restoration:**
- **No recalculation**: Features/indicators restored from saved state
- **Faster startup**: Ready immediately, no 2000-bar calculation
- **Exact continuity**: Like Pine Script - features stay intact

---

### **Step 4: Initialize Volume Exit System**
**File**: `src/strategy/backtest/volume_node_exit.py`

```python
# Initialize volume exit detector (if enabled)
volume_exit_strategy = VolumeNodeExitStrategy(
    default_exit_bars=4,
    use_volume_exit=True,  # or volume_exit_short=True
    volume_lookback=240,
    volume_num_rows=60,
    # ... other params
)

# Volume profile will be computed on first completed candle
```

---

### **Step 5: Initialize Candle Aggregator**
**File**: `src/trading_system/data/zerodha_candle_aggregator.py`

```python
# Initialize aggregator with current symbol
candle_aggregator = ZerodhaCandleAggregator(
    config=config,
    kite=kite,
    symbol=current_symbol,  # From Step 2
    logger=logger
)

candle_aggregator.initialize()
```

---

### **Step 6: Daily State Saving (3:30 PM) - Complete System State**
**File**: `src/trading_system/data/trading_state_manager.py`

```python
def save_daily_state(self, ml_system, historical_data):
    """
    Save complete system state at end of trading day (3:30 PM).
    
    Like Pine Script: Save everything (features, indicators, state) so system
    can continue seamlessly without recalculation.
    """
    
    # Get last computed ML results (features, indicators, predictions)
    last_results = ml_system.get_last_results()  # Or store during trading
    
    state = {
        # 1. Re-entry state (bar indices)
        'last_long_exit_bar': self.last_long_exit_bar,
        'last_short_exit_bar': self.last_short_exit_bar,
        
        # 2. Position state (if any)
        'position': {
            'direction': self.position.direction if self.position else None,
            'entry_price': self.position.entry_price if self.position else None,
            'entry_bar_index': self.position.entry_bar_index if self.position else None,
            'entry_timestamp': self.position.entry_timestamp.isoformat() if self.position and self.position.entry_timestamp else None
        } if self.position else None,
        
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
        'historical_data': historical_data.tail(2000).to_dict('records'),
        
        # 5. ML Classifier state (if needed)
        'classifier_state': ml_system.classifier.get_state() if hasattr(ml_system.classifier, 'get_state') else None,
        
        # 6. Metadata
        'last_processed_timestamp': self.last_timestamp.isoformat() if self.last_timestamp else None,
        'save_time': datetime.now(KOLKATA_TZ).isoformat(),
        'data_source': 'zerodha'  # Mark that we're using Zerodha data now
    }
    
    # Save to database (or pickle file for large state)
    self._save_to_db(state)
```

**When to Run**: At 3:30 PM (end of trading day)

**Why Save Complete State?**
- **Like Pine Script**: Features/indicators stay intact between sessions
- **Faster startup**: No recalculation of 2000 bars every morning
- **Exact continuity**: System continues seamlessly as if no pause
- **No database pull needed**: Historical data already in saved state

---

### **Step 7: Main Trading Loop**

```python
def main_live_trading_loop():
    """Main live trading loop - runs continuously"""
    
    # Start WebSocket price feed
    price_feed = WebSocketPriceFeed(kite, futures_token, oms, logger)
    price_feed.start()
    
    # Initialize signal executor
    executor = RunningSignalExecutor(oms, earnings_filter, logger)
    
    while running:
        # Get latest tick from WebSocket
        if price_feed.has_new_tick():
            tick_price = oms.futures_ltp
            tick_volume = price_feed.last_tick_volume  # If available
            tick_time = datetime.now(KOLKATA_TZ)
            
            # Process tick into running candle
            completed_candles = candle_aggregator.on_tick(
                price=tick_price,
                volume=tick_volume or 0,  # Accumulate volume
                timestamp=tick_time
            )
            
            # Get current running candle (for ML signals and volume exit)
            running_candle_15min = candle_aggregator.running_candles['15min']
            
            # ===== INTRABAR CHECKS (During Candle Formation) =====
            # Generate ML signals on RUNNING candle (like TradingView)
            
            # Get historical completed bars
            df_completed = manager_15min.get_dataframe()
            
            # Create temporary DataFrame with running candle included
            # Use running candle's current OHLC for ML calculation
            running_high = running_candle_15min.high
            running_low = running_candle_15min.low
            running_close = running_candle_15min.close
            running_open = running_candle_15min.open
            
            # Append running candle to DataFrame (temporary, for ML calculation)
            import pandas as pd
            import numpy as np
            running_bar = pd.DataFrame({
                'timestamp': [running_candle_15min.timestamp],
                'open': [running_open],
                'high': [running_high],
                'low': [running_low],
                'close': [running_close],
                'volume': [running_candle_15min.volume]
            })
            df_with_running = pd.concat([df_completed, running_bar], ignore_index=True)
            
            # Generate ML signals on RUNNING candle (like TradingView)
            current_bar_index = len(df_with_running) - 1  # Index of running candle
            
            signals = ml_system.generate_signals(
                high=df_with_running['high'].values,
                low=df_with_running['low'].values,
                close=df_with_running['close'].values,
                start_bar=current_bar_index  # Process latest bar (running candle)
            )
            
            # Determine current signal from running candle
            # IMPORTANT: Use CLOSE price for signal generation (not high/low/open)
            if signals['start_long'][current_bar_index]:
                current_signal = "LONG"
            elif signals['start_short'][current_bar_index]:
                current_signal = "SHORT"
            elif signals['end_long'][current_bar_index]:
                current_signal = "EXIT_LONG"
            elif signals['end_short'][current_bar_index]:
                current_signal = "EXIT_SHORT"
            else:
                current_signal = "NONE"
            
            # Trade on CLOSE price of running candle (not high/low/open)
            trading_price = running_close  # Use close price for entry/exit
            
            # Process ML signals via RunningSignalExecutor (handles entry/exit/reversal)
            # Apply re-entry logic before calling executor
            if oms.position.position_type == PositionType.NONE:
                bars_since_long_exit = len(df_completed) - last_long_exit_bar if last_long_exit_bar >= 0 else -1
                bars_since_short_exit = len(df_completed) - last_short_exit_bar if last_short_exit_bar >= 0 else -1
                
                # Check if entry is allowed based on re-entry rules
                can_enter_long = (
                    last_long_exit_bar < 0 or
                    bars_since_long_exit > reentry_end or
                    (reentry_start <= bars_since_long_exit <= reentry_end and 
                     signals['predictions'][current_bar_index] > 0)
                )
                
                can_enter_short = (
                    last_short_exit_bar < 0 or
                    bars_since_short_exit > reentry_end or
                    (reentry_start <= bars_since_short_exit <= reentry_end and 
                     signals['predictions'][current_bar_index] < 0)
                )
                
                # Block entry if re-entry rules prevent it
                if current_signal == "LONG" and not can_enter_long:
                    current_signal = "NONE"
                elif current_signal == "SHORT" and not can_enter_short:
                    current_signal = "NONE"
            
            # Call executor with current signal (handles immediate entry/exit/reversal)
            # This may enter a position on the running candle
            # IMPORTANT: Use CLOSE price for trading (not high/low/open)
            candle_id = running_candle_15min.timestamp.strftime("%Y-%m-%d %H:%M:%S_15min")
            executor.on_running_signal(current_signal, candle_id, trading_price)  # trading_price = running_close
            
            # ⚠️ IMPORTANT: Check volume exit AFTER entry processing
            # This handles the case where:
            # 1. Signal generated on running candle → Trade entered
            # 2. On SAME running candle, momentum is fast → Price crosses volume peak
            # 3. Should exit immediately on same candle (riding momentum)
            if oms.position.position_type != PositionType.NONE:
                # Use running candle's OHLC for volume exit check
                volume_exit, exit_price, _ = volume_exit_strategy.should_exit(
                    trade_direction=oms.position.direction,
                    entry_bar=oms.position.entry_bar_index,
                    current_bar=len(df_completed),  # Bar index in completed bars (same candle if just entered)
                    historical_data=df_completed,
                    current_high=running_high,
                    current_low=running_low,
                    current_close=running_close,
                    entry_price=oms.position.entry_price
                )
                
                if volume_exit:
                    # Volume exit triggered on SAME candle as entry!
                    # This happens when momentum is very fast
                    oms.exit_position(exit_price=exit_price)
                    # Update re-entry state (volume exit counts as ML exit)
                    # Mark this candle as exit bar for re-entry countdown
                    if oms.position.direction == 1:
                        last_long_exit_bar = len(df_completed)  # Same candle index
                    else:
                        last_short_exit_bar = len(df_completed)  # Same candle index
                    # Re-entry countdown starts: cannot re-enter for 3 bars, then can re-enter if prediction confirms (3-50 bars)
            
            # ===== CANDLE CLOSE PROCESSING =====
            
            if completed_candles.get('15min'):
                completed_candle = completed_candles['15min']
                
                # Candle closed! Process it:
                # 1. Candle already stored to DB by add_new_bar()
                # 2. Deque already updated by add_new_bar()
                
                # Get updated DataFrame (completed candle is now in deque)
                df_15min = manager_15min.get_dataframe()
                
                # Check 4-bar exit (if in position) - on candle close
                if oms.position.position_type != PositionType.NONE:
                    bars_held = current_bar_index - oms.position.entry_bar_index
                    
                    if bars_held >= 4:
                        # 4-bar exit at candle close
                        oms.exit_position(exit_price=completed_candle.close)
                        # Update re-entry state (4-bar exit counts as ML exit)
                        if oms.position.direction == 1:
                            last_long_exit_bar = current_bar_index
                        else:
                            last_short_exit_bar = current_bar_index
                
                # Candle-close reconciliation (flicker/reversal check)
                # Get final signal from completed candle for reconciliation
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
                # This checks:
                # - Flicker: Signal appeared during candle but faded at close → exit
                # - Reversal: Signal reversed → exit previous and enter new
                # Note: Flicker/reversal exits do NOT update re-entry state
                candle_id = completed_candle.timestamp.strftime("%Y-%m-%d %H:%M:%S_15min")
                executor.on_candle_close(final_signal, candle_id, completed_candle.close)
```

---

## 🔍 **Key Design Decisions**

### **1. Volume Exit Timing**
- **Decision**: Check volume exit on every tick during candle formation
- **Reason**: Volume exit can trigger intra-bar (like TradingView if enabled)
- **Implementation**: Check `running_candle.high` and `running_candle.low` against volume peaks

### **2. ML Signal Generation & Flicker/Reversal Logic**
- **Decision**: Generate ML signals on RUNNING candle (like TradingView)
  - Use historical completed bars + current running candle's OHLC
  - Signals visible on running candle, not waiting for close
  - Prevents missing entry opportunities (prices will be gone if we wait)
  - ML calculations use running candle's current high/low/close
- **Optimization**: Only process latest bar (incremental) instead of full DataFrame
- **Implementation**: 
  - On each tick: Update running candle OHLC → Generate ML signals → Process entry/exit
  - Use running candle's current values in ML calculations
- **Flicker/Reversal**: Handled by `RunningSignalExecutor` in OMS
  - **on_running_signal()**: Handles intra-bar signals (immediate entry/reversal)
  - **on_candle_close()**: Handles flicker cleanup (signal faded → exit)
  - **Important**: Flicker/reversal exits do NOT update ML re-entry state
  - **Only volume/4-bar exits update re-entry state** (last_long_exit_bar, last_short_exit_bar)

### **3. Re-entry State**
- **Decision**: Load from backtest state OR track during live trading
- **Implementation**: 
  - Start with backtest state (`last_long_exit_bar`, `last_short_exit_bar`)
  - Update during live trading on each exit
  - Save to state for restart continuity

### **4. Deque Operation**
- **Decision**: Append to deque AFTER candle closes
- **Implementation**: 
  - `add_new_bar()` appends to deque
  - Deque auto-drops oldest if exceeds `max_bars_back` (3000)
  - Rolling buffer maintains last 3000 bars for ML system

### **5. Exit Priority & Re-entry State**
- **Volume exit**: Checked intra-bar (every tick)
- **4-bar exit**: Checked on candle close
- **Whichever triggers FIRST**: Exit immediately
- **Re-entry state update**: Only volume/4-bar exits update re-entry state
  - `last_long_exit_bar` updated on LONG exit (volume or 4-bar)
  - `last_short_exit_bar` updated on SHORT exit (volume or 4-bar)
- **Flicker/reversal exits**: Do NOT update re-entry state
  - Flicker exit (signal faded): OMS cleanup only, no ML state change
  - Reversal exit (signal reversed): OMS position change only, no ML state change
  - Reason: These are OMS-level protections, not ML algorithm exits

---

## 📝 **Files to Create/Modify**

### **New Files**:
1. `src/trading_system/data/trading_state_manager.py` - State persistence
2. `scripts/live_trading_integrated.py` - Main live trading script (updated)

### **Modified Files**:
1. `src/trading_system/data/live_data_manager.py` - Contract-agnostic loading
2. `src/trading_system/data/zerodha_candle_aggregator.py` - Already simplified to 15min
3. `src/strategy/backtest/volume_node_exit.py` - Already fixed for nearest peak
4. `src/trading_system/oms/running_signal_executor.py` - May need volume exit integration

---

## ✅ **Implementation Checklist**

### **Phase 1: State Management**
- [ ] Re-implement `TradingStateManager` (load/save backtest state)
- [ ] Save state from backtest (last_long_exit_bar, last_short_exit_bar)
- [ ] Load state on live trading startup

### **Phase 2: Data Loading**
- [ ] Modify `LiveDataManager.initialize()` for contract-agnostic loading
- [ ] Load 15min OHLCV data by timeframe only (ignore symbol)
- [ ] Test with historical data (Nov contract → Dec contract)

### **Phase 3: Live Trading Loop**
- [ ] Integrate `ZerodhaCandleAggregator` with WebSocket feed
- [ ] Implement intra-bar volume exit checking
- [ ] Implement candle-close ML signal generation
- [ ] Implement 4-bar exit checking on candle close
- [ ] Implement re-entry logic with state tracking

### **Phase 4: Volume Exit Integration**
- [ ] Integrate volume exit into live trading loop
- [ ] Check volume exit on every tick (if in position)
- [ ] Update re-entry state on volume exit
- [ ] Test volume exit priority (vs 4-bar exit)

### **Phase 5: Daily State Saving**
- [ ] Implement 3:30 PM state saving
- [ ] Save re-entry state (last_long_exit_bar, last_short_exit_bar)
- [ ] Save position state (if any)
- [ ] Save last processed timestamp

### **Phase 6: Testing**
- [ ] Test with paper trading (dry_run=True)
- [ ] Verify state continuity across restarts
- [ ] Verify daily continuity (3:30 PM save → 9:15 AM load)
- [ ] Verify contract rollover handling
- [ ] Verify volume exit triggers correctly
- [ ] Verify flicker/reversal exits do NOT update re-entry state
- [ ] Verify only volume/4-bar exits update re-entry state
- [ ] Verify re-entry logic works correctly

---

## 🛠️ **System Recovery & Glitch Handling**

**See `SYSTEM_RECOVERY_PLAN.md` for complete recovery strategy.**

### **Failure Scenarios:**
1. **Zerodha API Issues**:
   - API down → Retry with same request token (valid till 6 AM)
   - Token expired (after 6 AM) → Re-login, generate new token

2. **System Crashes / WiFi Down**:
   - Detect data gaps (missing candles while system was off)
   - Fill gaps from Zerodha historical data
   - Rebuild ML state (restore or recalculate)

3. **Position Mismatch**:
   - Compare saved position vs broker position
   - Reconcile position state (broker is source of truth)
   - Update re-entry state accordingly

4. **Auto-Save During Trading**:
   - Save state every 15min (not just at 3:30 PM)
   - Ensures recent state available if crash happens

### **Recovery Flow:**
1. Load last saved state
2. Check broker positions (`oms.kite.positions()['net']`)
3. Reconcile position state (saved vs broker)
4. Detect data gaps (missing candles)
5. Fill data gaps from Zerodha historical data
6. Rebuild ML state (restore from saved state OR recalculate if gaps exist)
7. Update re-entry state
8. Resume trading

**Key Principle**: Broker is source of truth - if position mismatch, trust broker position.

---

## 🚀 **Ready to Build?**

**Clarifications Confirmed**:
- ✅ **ML signals: Generated on RUNNING candle** (like TradingView)
  - Use historical completed bars + running candle's current OHLC
  - Signals visible on running candle, not waiting for close
  - Prevents missing entry opportunities (prices will be gone if we wait)
- ✅ Flicker/Reversal: Handled by `RunningSignalExecutor` in OMS
  - Flicker exit (signal faded at close): Does NOT update re-entry state
  - Reversal exit (signal reversed): Does NOT update re-entry state
- ✅ Re-entry state: Only updated by volume/4-bar exits (ML algorithm exits)
- ✅ Volume exit: Checked intra-bar (every tick during candle formation)
- ✅ 4-bar exit: Checked on candle close
- ✅ Deque operation: After candle closes (append to rolling buffer)
- ✅ Daily continuity: Save state at 3:30 PM, load next morning at 9:15 AM
- ✅ Rolling buffer: `max_bars_back=2000` (old data + new data continuously)

**Architecture Summary**:
```
For Each Tick:
  1. Update running 15min candle (OHLCV)
  2. Generate ML signals on RUNNING candle (historical + running OHLC)
  3. Apply re-entry logic (check last_long_exit_bar, last_short_exit_bar)
  4. Process entry/exit via RunningSignalExecutor.on_running_signal()
     - Immediate entry/exit/reversal based on current signal
  5. Check volume exit (if in position) → exit + update re-entry state

On Candle Close:
  1. Store completed candle OHLCV to database
  2. Append to deque (rolling buffer, drop oldest if > 2000)
  3. Check 4-bar exit → exit + update re-entry state
  4. Call RunningSignalExecutor.on_candle_close()
     - Handles flicker (signal faded at close → exit, NO re-entry update)
     - Handles reversal (signal reversed → exit+enter, NO re-entry update)

End of Day (3:30 PM):
  - Save re-entry state (last_long_exit_bar, last_short_exit_bar)
  - Save position state
  - Save last processed timestamp

Next Morning (9:15 AM):
  - Load saved state
  - Load historical 15min OHLCV (last 2000 bars)
  - Continue seamlessly
```

**Next Steps**:
1. **Today**: Implement state management and data loading
2. **Tonight**: Test with historical data
3. **Tomorrow 9:15 AM**: Start live trading!
4. **Tomorrow 3:30 PM**: Save daily state automatically

---

**Are we on the same page? Ready to start building step by step!**

