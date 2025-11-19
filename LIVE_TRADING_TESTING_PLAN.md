# Live Trading System - Comprehensive Testing Plan

## 🎯 **Goal**
Test every block of the system **carefully, slowly, and thoroughly** to ensure everything is complete and behaving as expected before live trading.

**Approach**: Test each component in isolation first, then integrate step by step.

---

## 📋 **Testing Phases**

### **Phase 1: Data Management & State Persistence** 🔵
**Status**: ⏳ In Progress  
**Goal**: Verify data loading, candle aggregation, and state save/load works correctly.

---

### **Phase 2: ML System Core** 🟢
**Status**: ⏸️ Pending  
**Goal**: Verify ML signal generation, feature calculation, and indicator computation.

---

### **Phase 3: Exit Strategies** 🟡
**Status**: ⏸️ Pending  
**Goal**: Verify 4-bar exit and volume peak exit logic works correctly.

---

### **Phase 4: OMS Components** 🟠
**Status**: ⏸️ Pending  
**Goal**: Verify order management, option chain lookup, and margin calculation.

---

### **Phase 5: Integration Testing** 🔴
**Status**: ⏸️ Pending  
**Goal**: Verify complete flow from tick → signal → order → exit.

---

### **Phase 6: Gap Protection & Recovery** 🟣
**Status**: ⏸️ Pending  
**Goal**: Verify gap detection, immediate exit, and recovery scenarios.

---

---

## 🔵 **PHASE 1: Data Management & State Persistence**

### **Block 1.1: Historical Data Loading** ✅
**File**: `src/trading_system/data/historical_loader.py`

**Tests**:
- [ ] Test loading data from `ohlcv_zerodha` table
- [ ] Test contract-agnostic loading (ignores symbol)
- [ ] Test loading last N bars (2000 bars)
- [ ] Test timezone handling (IST)
- [ ] Test data format (OHLCV with volume)
- [ ] Test error handling (empty table, missing data)

**Expected Output**:
- DataFrame with columns: `timestamp`, `open`, `high`, `low`, `close`, `volume`
- Data sorted by timestamp ascending
- All timestamps in IST timezone

**Verification Steps**:
1. Run test script
2. Verify DataFrame structure
3. Verify data integrity (no gaps, correct order)
4. Verify last 2000 bars loaded correctly

---

### **Block 1.2: Candle Aggregation** ✅
**File**: `src/trading_system/data/zerodha_candle_aggregator.py`

**Tests**:
- [ ] Test tick aggregation into 15min candles
- [ ] Test OHLC calculation from ticks
- [ ] Test volume aggregation (sum of tick volumes)
- [ ] Test candle completion (after 15min)
- [ ] Test running candle update (before completion)
- [ ] Test multiple timeframes (should only work for 15min)
- [ ] Test symbol handling (futures symbol)

**Expected Output**:
- Running candle updates on each tick
- Completed candle returned after 15min
- Correct OHLC values
- Correct volume sum

**Verification Steps**:
1. Simulate tick stream
2. Verify running candle updates
3. Verify candle completes after 15min
4. Verify OHLCV values correct

---

### **Block 1.3: State Manager (CREATE & TEST)** ❌
**File**: `src/trading_system/data/trading_state_manager.py` **(TO BE CREATED)**

**Tests**:
- [ ] Test `save_daily_state()` saves all required data:
  - Re-entry state (last_long_exit_bar, last_short_exit_bar)
  - Position state (direction, entry_price, entry_bar_index, atm_strike, hedge_strike)
  - ML system state (features, indicators, predictions, signals)
  - Historical OHLCV data (last 2000 bars)
  - Futures previous close
- [ ] Test `load_saved_state()` loads all data correctly
- [ ] Test state persistence across sessions
- [ ] Test missing state handling (first run)
- [ ] Test state update (overwrite previous state)
- [ ] Test data integrity (all fields present)

**Expected Output**:
- State saved to SQLite database
- State loaded correctly on next run
- All fields present and correct
- Missing state handled gracefully (return None/empty dict)

**Verification Steps**:
1. Create `trading_state_manager.py`
2. Implement `save_daily_state()` and `load_saved_state()`
3. Test save with sample data
4. Test load from saved data
5. Verify all fields present
6. Test missing state handling

---

### **Block 1.4: Live Data Manager** ✅
**File**: `src/trading_system/data/live_data_manager.py`

**Tests**:
- [ ] Test contract-agnostic initialization
- [ ] Test symbol update (after contract rollover)
- [ ] Test DataFrame retrieval (get_dataframe())
- [ ] Test deque operations (add_bar, get_latest)
- [ ] Test max_bars_back limit (2000 bars rolling)
- [ ] Test data appending (new candles added)

**Expected Output**:
- Manager initialized without symbol (contract-agnostic)
- Symbol updated after initialization
- DataFrame returns last 2000 bars
- New candles appended correctly
- Old candles removed when >2000 bars

**Verification Steps**:
1. Initialize manager without symbol
2. Load historical data
3. Update symbol
4. Verify DataFrame structure
5. Test deque operations
6. Test max_bars_back limit

---

### **Block 1.5: Zerodha Futures Utils** ✅
**File**: `src/trading_system/data/zerodha_futures_utils.py`

**Tests**:
- [ ] Test getting current month futures symbol
- [ ] Test token lookup from symbol
- [ ] Test contract rollover detection
- [ ] Test symbol format (BANKNIFTY25DECFUT)

**Expected Output**:
- Current month futures symbol returned
- Token lookup works
- Symbol format correct

**Verification Steps**:
1. Test with real Zerodha connection
2. Verify symbol format
3. Verify token lookup
4. Test contract rollover detection

---

**Phase 1 Summary**:
- ✅ Block 1.1: Historical Data Loading
- ✅ Block 1.2: Candle Aggregation
- ❌ Block 1.3: State Manager (NEEDS CREATION)
- ✅ Block 1.4: Live Data Manager
- ✅ Block 1.5: Zerodha Futures Utils

---

## 🟢 **PHASE 2: ML System Core**

### **Block 2.1: ML Extensions (Indicators)** ✅
**File**: `src/strategy/core/ml_extension.py`

**Tests**:
- [ ] Test `n_rsi()` calculation (normalized RSI)
- [ ] Test `n_cci()` calculation (normalized CCI)
- [ ] Test `n_wt()` calculation (normalized WaveTrend)
- [ ] Test `n_adx()` calculation (normalized ADX)
- [ ] Test `filter_volatility()` filter
- [ ] Test `regime_filter()` filter
- [ ] Test `filter_adx()` filter
- [ ] Test Numba JIT compilation (performance)
- [ ] Test output format (numpy arrays)
- [ ] Test edge cases (NaN handling, short arrays)

**Expected Output**:
- All indicators return normalized values (0-1 range)
- Filters return boolean arrays
- Fast execution (<1ms per indicator for 10k bars)
- No NaN values in output

**Verification Steps**:
1. Run existing benchmark (if `__main__` block exists)
2. Compare outputs with known values
3. Verify normalization (0-1 range)
4. Test performance (should be fast with Numba)

---

### **Block 2.2: Volume Profile** ✅
**File**: `src/strategy/core/volume_profile.py`

**Tests**:
- [ ] Test `compute_volume_profile_full()` calculation
- [ ] Test volume profile with sample data
- [ ] Test peak detection (local maxima)
- [ ] Test trough detection (local minima)
- [ ] Test Numba JIT compilation (performance)
- [ ] Test with different lookback values (240, 360)
- [ ] Test with different num_rows values (60, 100)
- [ ] Test edge cases (empty data, short arrays)

**Expected Output**:
- Volume profile computed correctly
- Peaks and troughs detected correctly
- Fast execution (<10ms for 240 bars, 60 rows)
- No NaN values

**Verification Steps**:
1. Test with sample OHLCV data
2. Verify volume profile shape
3. Verify peaks/troughs detection
4. Test performance with Numba
5. Compare with TradingView (if possible)

---

### **Block 2.3: Lorentzian Classifier** ✅
**File**: `src/strategy/core/lorentzian_classifier.py`

**Tests**:
- [ ] Test `lorentzian_distance()` calculation
- [ ] Test `find_k_nearest_neighbors()` function
- [ ] Test `generate_labels()` function
- [ ] Test KNN classification accuracy
- [ ] Test Numba JIT compilation (performance)
- [ ] Test with different neighbor counts (8, 12, 16)
- [ ] Test edge cases (NaN handling, empty arrays)

**Expected Output**:
- Distance calculation correct
- Nearest neighbors found correctly
- Labels generated correctly
- Fast execution (<50ms for 10k bars, 8 neighbors)

**Verification Steps**:
1. Test distance calculation with known values
2. Test KNN with sample data
3. Verify label generation
4. Test performance

---

### **Block 2.4: Trading System (ML Signal Generation)** ✅
**File**: `src/strategy/core/trading_system.py`

**Tests**:
- [ ] Test `LorentzianTradingSystem` initialization
- [ ] Test `generate_signals()` with historical data
- [ ] Test feature calculation (F1-F5)
- [ ] Test kernel filtering
- [ ] Test volatility filtering
- [ ] Test regime filtering
- [ ] Test re-entry logic (too soon, within window, outside window)
- [ ] Test signal generation (LONG, SHORT, NONE)
- [ ] Test `get_last_results()` method
- [ ] Test `restore_state()` method (if exists)

**Expected Output**:
- Signals generated correctly (LONG/SHORT/NONE)
- Features calculated correctly
- Filters applied correctly
- Re-entry logic working (3-50 bar window)
- Last results returned correctly

**Verification Steps**:
1. Initialize system with settings
2. Generate signals on historical data
3. Verify signal timing (not too soon after exit)
4. Verify filters applied
5. Test re-entry logic
6. Test state restoration (if implemented)

---

**Phase 2 Summary**:
- ✅ Block 2.1: ML Extensions (Indicators)
- ✅ Block 2.2: Volume Profile
- ✅ Block 2.3: Lorentzian Classifier
- ✅ Block 2.4: Trading System (ML Signal Generation)

---

## 🟡 **PHASE 3: Exit Strategies**

### **Block 3.1: 4-Bar Exit** ✅
**File**: `src/strategy/backtest/exit_strategies.py`

**Tests**:
- [ ] Test `ExitController.check_exit()` with 4 bars held
- [ ] Test exit at candle close (not running candle)
- [ ] Test bar counting (entry_bar_index to current_bar)
- [ ] Test edge cases (bars_held < 4, bars_held == 4, bars_held > 4)
- [ ] Test exit reason logging

**Expected Output**:
- Exit triggered after 4 bars held
- Exit happens at candle close
- Bar counting correct
- Exit reason logged correctly

**Verification Steps**:
1. Create test trade with entry_bar_index
2. Simulate 4 candles passing
3. Verify exit triggered at 4th candle close
4. Verify exit reason ("4_bars")

---

### **Block 3.2: Volume Peak Exit** ✅
**File**: `src/strategy/backtest/volume_node_exit.py`

**Tests**:
- [ ] Test `VolumeNodeExitDetector.check_exit()` for LONG trades
- [ ] Test `VolumeNodeExitDetector.check_exit()` for SHORT trades
- [ ] Test nearest peak selection (nearest to entry_price in trade direction)
- [ ] Test peak filtering by direction (LONG → upward peaks, SHORT → downward peaks)
- [ ] Test exit when price crosses peak (LONG: high crosses peak, SHORT: low crosses peak)
- [ ] Test exit price calculation (LONG: min(crossed_peak, current_close), SHORT: max(crossed_peak, current_close))
- [ ] Test volume profile recomputation (only on candle close)
- [ ] Test intra-bar caching (peaks cached for running candle)
- [ ] Test edge cases (no peaks, all peaks crossed, peak at entry)

**Expected Output**:
- LONG: Exit when high crosses nearest upward peak
- SHORT: Exit when low crosses nearest downward peak
- Exit price correct (nearest crossed peak or current close, whichever is better)
- Volume profile recomputed only on candle close
- Peaks cached for running candle

**Verification Steps**:
1. Create test trade (LONG) with entry_price
2. Generate volume profile with peaks
3. Filter peaks by direction (upward for LONG)
4. Find nearest peak to entry_price
5. Simulate price crossing peak
6. Verify exit triggered
7. Verify exit price correct
8. Repeat for SHORT trade

---

**Phase 3 Summary**:
- ✅ Block 3.1: 4-Bar Exit
- ✅ Block 3.2: Volume Peak Exit

---

## 🟠 **PHASE 4: OMS Components**

### **Block 4.1: Option Chain Manager** ✅
**File**: `src/trading_system/oms/option_chain_manager.py`

**Tests**:
- [ ] Test `get_atm_strike()` calculation (nearest to futures LTP)
- [ ] Test `get_hedge_strike()` calculation (20 legs away)
- [ ] Test option symbol generation (CE/PE)
- [ ] Test token lookup from symbol
- [ ] Test option chain caching
- [ ] Test contract rollover handling

**Expected Output**:
- ATM strike correct (nearest to futures LTP)
- Hedge strike correct (20 legs away)
- Option symbols correct (BANKNIFTY25DEC57800CE)
- Tokens looked up correctly
- Option chain cached for performance

**Verification Steps**:
1. Test with real Zerodha connection
2. Verify ATM strike calculation
3. Verify hedge strike calculation
4. Test option symbol generation
5. Test token lookup

---

### **Block 4.2: Margin Calculator** ✅
**File**: `src/trading_system/oms/margin_calculator.py`

**Tests**:
- [ ] Test `calculate_margin()` for 3-leg position
- [ ] Test basket order margins API call
- [ ] Test margin reduction with hedging (spread benefit)
- [ ] Test sequential lot reduction (if margin insufficient)
- [ ] Test margin calculation for LONG (SELL PE + BUY CE + BUY Hedge PE)
- [ ] Test margin calculation for SHORT (SELL CE + BUY PE + BUY Hedge CE)

**Expected Output**:
- Margin calculated correctly (~₹8.5L for 8 lots with spread benefit)
- Basket margins API called correctly
- Margin reduction applied correctly (63% reduction with hedging)
- Lot reduction works if margin insufficient

**Verification Steps**:
1. Test margin calculation for LONG
2. Test margin calculation for SHORT
3. Verify basket margins API response
4. Verify spread benefit (margin reduction)
5. Test lot reduction logic

---

### **Block 4.3: Order Manager** ✅
**File**: `src/trading_system/oms/order_manager.py`

**Tests**:
- [ ] Test `enter_long()` execution (3-leg position)
- [ ] Test `enter_short()` execution (3-leg position)
- [ ] Test `exit_position()` execution (close all legs)
- [ ] Test `execute_stop_loss()` execution
- [ ] Test BUY-first sequence (BUY orders before SELL orders)
- [ ] Test NRML product type usage
- [ ] Test MARKET order execution
- [ ] Test partial fill handling
- [ ] Test position tracking (entry_price, entry_bar_index, atm_strike, hedge_strike)

**Expected Output**:
- Orders executed correctly (3 legs for entry)
- BUY orders before SELL orders
- All orders use NRML product type
- All orders use MARKET execution
- Partial fills handled gracefully
- Position tracked correctly

**Verification Steps**:
1. Test with paper trading (if possible)
2. Verify order sequence (BUY first)
3. Verify product type (NRML)
4. Verify order type (MARKET)
5. Test partial fill handling
6. Verify position tracking

---

### **Block 4.4: Running Signal Executor** ✅
**File**: `src/trading_system/oms/running_signal_executor.py`

**Tests**:
- [ ] Test running-candle signal handling (not waiting for close)
- [ ] Test flicker detection (signal disappears on candle close)
- [ ] Test reversal detection (signal changes direction on candle close)
- [ ] Test signal confirmation (signal persists on candle close)
- [ ] Test position exit on flicker/reversal
- [ ] Test position entry on confirmation

**Expected Output**:
- Signals processed on running candle (not waiting for close)
- Flickers detected correctly (signal gone on close → exit)
- Reversals detected correctly (signal changed → exit old, enter new)
- Confirmations detected correctly (signal persists → enter)

**Verification Steps**:
1. Simulate running candle signals
2. Test flicker scenario
3. Test reversal scenario
4. Test confirmation scenario
5. Verify position handling

---

### **Block 4.5: WebSocket Price Feed** ✅
**File**: `src/trading_system/oms/websocket_price_feed.py`

**Tests**:
- [ ] Test WebSocket connection to Zerodha
- [ ] Test tick data reception (price, volume, timestamp)
- [ ] Test subscription to futures token
- [ ] Test reconnection logic (if connection drops)
- [ ] Test error handling (API errors, network errors)
- [ ] Test tick callback execution

**Expected Output**:
- WebSocket connects successfully
- Ticks received in real-time
- Futures token subscribed correctly
- Reconnection works on disconnection
- Errors handled gracefully

**Verification Steps**:
1. Test with real Zerodha connection
2. Verify tick reception
3. Test reconnection
4. Test error handling

---

**Phase 4 Summary**:
- ✅ Block 4.1: Option Chain Manager
- ✅ Block 4.2: Margin Calculator
- ✅ Block 4.3: Order Manager
- ✅ Block 4.4: Running Signal Executor
- ✅ Block 4.5: WebSocket Price Feed

---

## 🔴 **PHASE 5: Integration Testing**

### **Block 5.1: Complete Flow (Tick → Signal → Order)** ⏸️
**Files**: Multiple (integration)

**Tests**:
- [ ] Test complete flow: Tick → Candle → Signal → Order
- [ ] Test position-first logic (no ML signals if position exists)
- [ ] Test entry execution (signal → order → position tracked)
- [ ] Test exit execution (4-bar or volume → order → position cleared)
- [ ] Test re-entry logic (after exit, wait 3-50 bars before re-entry)
- [ ] Test running-candle signal generation (not waiting for close)
- [ ] Test flicker/reversal handling (on candle close)

**Expected Output**:
- Complete flow works end-to-end
- Position-first logic enforced
- Entries executed correctly
- Exits executed correctly
- Re-entry logic respected
- Running-candle signals work
- Flicker/reversal handled correctly

**Verification Steps**:
1. Simulate tick stream
2. Verify candle aggregation
3. Verify signal generation (on running candle)
4. Verify entry execution (if no position)
5. Verify exit execution (if position exists)
6. Verify re-entry logic
7. Test flicker/reversal scenarios

---

### **Block 5.2: State Persistence Integration** ⏸️
**Files**: `trading_state_manager.py` + Integration

**Tests**:
- [ ] Test state save at 3:30 PM (all components save state)
- [ ] Test state load at 9:15 AM (all components restore state)
- [ ] Test state continuity across sessions (same signals, same positions)
- [ ] Test state update after each trade (position updated)
- [ ] Test state update after each exit (re-entry bars updated)
- [ ] Test missing state handling (first run, fresh start)

**Expected Output**:
- State saved correctly at 3:30 PM
- State loaded correctly at 9:15 AM
- System continues seamlessly (like Pine Script)
- State updated after each trade/exit
- Missing state handled gracefully

**Verification Steps**:
1. Run system for one day
2. Save state at 3:30 PM
3. Load state next morning
4. Verify system continues correctly
5. Verify state updated after trades/exits

---

**Phase 5 Summary**:
- ⏸️ Block 5.1: Complete Flow (Tick → Signal → Order)
- ⏸️ Block 5.2: State Persistence Integration

---

## 🟣 **PHASE 6: Gap Protection & Recovery**

### **Block 6.1: Gap Detection** ⏸️
**Files**: Gap detection logic (to be integrated)

**Tests**:
- [ ] Test gap calculation (futures_today_open - futures_previous_close)
- [ ] Test gap detection for LONG (gap down adverse, gap up favorable)
- [ ] Test gap detection for SHORT (gap up adverse, gap down favorable)
- [ ] Test immediate exit on adverse gap (LONG + gap down, SHORT + gap up)
- [ ] Test normal trading on favorable gap (LONG + gap up, SHORT + gap down)
- [ ] Test gap threshold (300 points default)
- [ ] Test futures_previous_close loading (from saved state)

**Expected Output**:
- Gap calculated correctly (using futures prices)
- Adverse gaps trigger immediate exit
- Favorable gaps continue normal trading
- Gap threshold respected
- Futures previous close loaded correctly

**Verification Steps**:
1. Test gap calculation with sample data
2. Test adverse gap (LONG + gap down → exit)
3. Test favorable gap (LONG + gap up → continue)
4. Test gap threshold
5. Test futures_previous_close loading

---

### **Block 6.2: Recovery Scenarios** ⏸️
**Files**: Recovery logic (from `SYSTEM_RECOVERY_PLAN.md`)

**Tests**:
- [ ] Test crash recovery (system restarts, loads state)
- [ ] Test position mismatch detection (broker position vs saved position)
- [ ] Test data gap detection (missing candles)
- [ ] Test data gap filling (using `fetch_zerodha_historical_data.py`)
- [ ] Test ML state recalculation (if gaps filled)
- [ ] Test WiFi downtime handling (reconnection)
- [ ] Test API downtime handling (error handling, retry)

**Expected Output**:
- System recovers gracefully after crash
- Position mismatches detected and reconciled
- Data gaps detected and filled
- ML state recalculated if needed
- Reconnection works on network issues
- API errors handled gracefully

**Verification Steps**:
1. Simulate crash (kill process)
2. Restart system, verify state loaded
3. Simulate position mismatch, verify reconciliation
4. Simulate data gaps, verify filling
5. Simulate network issues, verify reconnection

---

**Phase 6 Summary**:
- ⏸️ Block 6.1: Gap Detection
- ⏸️ Block 6.2: Recovery Scenarios

---

## 🎯 **Testing Checklist Summary**

### **Phase 1: Data Management & State Persistence** (5 blocks)
- ✅ Block 1.1: Historical Data Loading
- ✅ Block 1.2: Candle Aggregation
- ❌ Block 1.3: State Manager **(NEEDS CREATION)**
- ✅ Block 1.4: Live Data Manager
- ✅ Block 1.5: Zerodha Futures Utils

### **Phase 2: ML System Core** (4 blocks)
- ✅ Block 2.1: ML Extensions (Indicators)
- ✅ Block 2.2: Volume Profile
- ✅ Block 2.3: Lorentzian Classifier
- ✅ Block 2.4: Trading System (ML Signal Generation)

### **Phase 3: Exit Strategies** (2 blocks)
- ✅ Block 3.1: 4-Bar Exit
- ✅ Block 3.2: Volume Peak Exit

### **Phase 4: OMS Components** (5 blocks)
- ✅ Block 4.1: Option Chain Manager
- ✅ Block 4.2: Margin Calculator
- ✅ Block 4.3: Order Manager
- ✅ Block 4.4: Running Signal Executor
- ✅ Block 4.5: WebSocket Price Feed

### **Phase 5: Integration Testing** (2 blocks)
- ⏸️ Block 5.1: Complete Flow (Tick → Signal → Order)
- ⏸️ Block 5.2: State Persistence Integration

### **Phase 6: Gap Protection & Recovery** (2 blocks)
- ⏸️ Block 6.1: Gap Detection
- ⏸️ Block 6.2: Recovery Scenarios

---

## 📝 **Testing Protocol**

### **For Each Block**:
1. ✅ Read the code file
2. ✅ Understand what it does
3. ✅ Write test script (if needed)
4. ✅ Run tests
5. ✅ Verify outputs match expected
6. ✅ Document any issues
7. ✅ Fix issues (if any)
8. ✅ Re-test until passing

### **Before Moving to Next Block**:
- ✅ All tests pass
- ✅ No errors or warnings
- ✅ Outputs verified
- ✅ Edge cases handled
- ✅ Documentation updated

---

## 🚀 **Next Step: Phase 1, Block 1.3**

**Start with**: Create `trading_state_manager.py` and test state save/load.

**This is the foundation** - everything else depends on state persistence working correctly.

---

**Last Updated**: Testing plan created  
**Status**: Ready to begin Phase 1, Block 1.3

