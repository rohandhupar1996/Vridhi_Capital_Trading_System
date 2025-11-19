# Comprehensive Testing Plan - ALL Scenarios

## 🎯 **Goal**
Test **EVERY** scenario from **ALL** test files and documents with **REAL Zerodha API** (dry-run mode, 1 lot) and maintain detailed logs for each component.

**Approach**: Run all test suites systematically, one by one, with comprehensive logging.

---

## 📋 **Complete Test Suite Inventory**

### **Phase 1: Data Management & State Persistence** (5 test files)

#### **1.1: Trading State Manager** ✅
**File**: `scripts/test_trading_state_manager.py`
**Scenarios**:
- [ ] Test state save (position, ML state, historical data)
- [ ] Test state load (restore from database)
- [ ] Test missing state handling
- [ ] Test state clear
- [ ] Test state with no position

**Log File**: `logs/test_trading_state_manager_YYYYMMDD_HHMMSS.log`

---

#### **1.2: Live Data Manager** ✅
**File**: `scripts/test_live_data_manager.py`
**Scenarios**:
- [ ] Test initialization (contract-agnostic loading)
- [ ] Test adding new bars
- [ ] Test max bars limit (rolling buffer)
- [ ] Test numpy array conversion
- [ ] Test contract-agnostic loading
- [ ] Test symbol update (contract rollover)

**Log File**: `logs/test_live_data_manager_YYYYMMDD_HHMMSS.log`

---

#### **1.3: Zerodha Futures Utils** ✅
**File**: `scripts/test_zerodha_futures_utils.py`
**Scenarios**:
- [ ] Test expiry detection from option chain
- [ ] Test rollover logic (before expiry)
- [ ] Test rollover logic (after expiry)
- [ ] Test current month symbol retrieval
- [ ] Test current month token retrieval
- [ ] Test symbol and token retrieval together
- [ ] Test error handling (no option chain)

**Log File**: `logs/test_zerodha_futures_utils_YYYYMMDD_HHMMSS.log`

---

### **Phase 2: ML System Core** (4 test files)

#### **2.1: ML Extensions (Indicators)** ✅
**File**: `scripts/test_ml_extensions.py`
**Scenarios**:
- [ ] Test normalized RSI (n_rsi)
- [ ] Test normalized CCI (n_cci)
- [ ] Test normalized WaveTrend (n_wt)
- [ ] Test normalized ADX (n_adx)
- [ ] Test volatility filter
- [ ] Test regime filter
- [ ] Test ADX filter
- [ ] Test edge cases (short arrays, NaN, constant values)

**Log File**: `logs/test_ml_extensions_YYYYMMDD_HHMMSS.log`

---

#### **2.2: Volume Profile** ✅
**File**: `scripts/test_volume_profile.py`
**Scenarios**:
- [ ] Test basic volume profile computation
- [ ] Test peak detection
- [ ] Test trough detection
- [ ] Test different lookback values
- [ ] Test different num_rows values
- [ ] Test performance (large datasets)
- [ ] Test edge cases (short arrays, constant prices, NaN volumes)
- [ ] Test value area (POC, VAH, VAL)

**Log File**: `logs/test_volume_profile_YYYYMMDD_HHMMSS.log`

---

#### **2.3: Lorentzian Classifier** ✅
**File**: `scripts/test_lorentzian_classifier.py`
**Scenarios**:
- [ ] Test Lorentzian distance calculation
- [ ] Test label generation
- [ ] Test find K nearest neighbors
- [ ] Test full Lorentzian classifier
- [ ] Test real trading parameters (neighbors_count=5, max_bars_back=2000, reentry_window=[3, 50])
- [ ] Test different neighbor counts
- [ ] Test performance (large datasets)
- [ ] Test edge cases (small datasets, NaN features, constant features)
- [ ] Test single bar classification (for live trading)

**Log File**: `logs/test_lorentzian_classifier_YYYYMMDD_HHMMSS.log`

---

#### **2.4: Trading System (ML Signal Generation)** ✅
**File**: `scripts/test_trading_system.py`
**Scenarios**:
- [ ] Test system initialization
- [ ] Test feature generation (F1-F5)
- [ ] Test filter application (volatility, regime, ADX)
- [ ] Test kernel filter
- [ ] Test complete signal generation pipeline
- [ ] Test re-entry logic verification (too soon, within window, outside window)
- [ ] Test performance (large datasets)
- [ ] Test edge cases (small datasets, constant prices, large datasets)

**Log File**: `logs/test_trading_system_YYYYMMDD_HHMMSS.log`

---

### **Phase 3: Exit Strategies** (2 test files)

#### **3.1: 4-Bar Exit** ✅
**File**: `scripts/test_exit_strategies.py`
**Scenarios**:
- [ ] Test basic 4-bar exit (LONG)
- [ ] Test 4-bar exit (SHORT)
- [ ] Test bar counting accuracy
- [ ] Test exit at candle close
- [ ] Test P&L calculation (LONG/SHORT)
- [ ] Test edge cases (None trade, entry bar, exact 4 bars, >4 bars)

**Log File**: `logs/test_exit_strategies_YYYYMMDD_HHMMSS.log`

---

#### **3.2: Volume Peak Exit** ✅
**File**: `scripts/test_volume_exit.py`
**Scenarios**:
- [ ] Test LONG volume exit (price crosses nearest upward peak)
- [ ] Test SHORT volume exit (price crosses nearest downward peak)
- [ ] Test nearest peak selection (nearest to entry price)
- [ ] Test peak filtering by direction (LONG/SHORT)
- [ ] Test exit price calculation (max(peak, close) for LONG, min(peak, close) for SHORT)
- [ ] Test volume profile recomputation (only on new bars, caching for intra-bar)
- [ ] Test combined exit strategy (4-bar OR volume exit)
- [ ] Test edge cases (insufficient data, no peaks)

**Log File**: `logs/test_volume_exit_YYYYMMDD_HHMMSS.log`

---

### **Phase 4: OMS Components** (5 test files)

#### **4.1: Option Chain Manager** ✅
**File**: `scripts/test_option_chain_manager.py`
**Scenarios**:
- [ ] Test option chain refresh (fetch from Zerodha)
- [ ] Test get option contract (by strike and type)
- [ ] Test get option symbol
- [ ] Test get option token
- [ ] Test get available strikes
- [ ] Test get contracts summary
- [ ] Test ATM strike calculation (nearest to futures LTP)
- [ ] Test hedge strike calculation (20 legs away)
- [ ] Test option chain caching

**Log File**: `logs/test_option_chain_manager_YYYYMMDD_HHMMSS.log`

---

#### **4.2: Margin Calculator** ✅
**File**: `scripts/test_margin_calculator.py`
**Scenarios**:
- [ ] Test LONG margin calculation (1 lot)
- [ ] Test basket margins API integration
- [ ] Test margin reduction with hedging (spread benefit ~63%)
- [ ] Test SHORT margin calculation (1 lot)
- [ ] Test fallback margin calculation (when API fails)
- [ ] Test available margin check
- [ ] Test pre-calculate daily margins (both LONG/SHORT)
- [ ] Test margin for different lot sizes

**Log File**: `logs/test_margin_calculator_YYYYMMDD_HHMMSS.log`

---

#### **4.3: Order Manager** ✅
**File**: `scripts/test_order_manager.py`
**Scenarios**:
- [ ] Test OMS initialization
- [ ] Test enter LONG (3-leg: SELL PE, BUY CE, BUY Hedge PE)
- [ ] Test enter SHORT (3-leg: SELL CE, BUY PE, BUY Hedge CE)
- [ ] Test exit position (close all 3 legs)
- [ ] Test execute stop loss
- [ ] Test BUY-first sequence (BUY before SELL)
- [ ] Test NRML product type
- [ ] Test MARKET order type
- [ ] Test position tracking
- [ ] Test partial fill handling
- [ ] Test ATM strike calculation

**Log File**: `logs/test_order_manager_YYYYMMDD_HHMMSS.log`

---

#### **4.4: Running Signal Executor** ✅
**File**: `scripts/test_running_signal_executor.py`
**Scenarios**:
- [ ] Test running candle signal handling (immediate action)
- [ ] Test flicker detection (signal faded at candle close)
- [ ] Test reversal detection (signal reversed at candle close)
- [ ] Test signal confirmation (signal persists at candle close)
- [ ] Test ML exit signal (EXIT_LONG, EXIT_SHORT)
- [ ] Test same candle reversal (exit old, enter new in same candle)
- [ ] Test earnings filter blocking
- [ ] Test candle context tracking
- [ ] Test NONE signal handling
- [ ] Test fast execution with pre-calculated margins

**Log File**: `logs/test_running_signal_executor_YYYYMMDD_HHMMSS.log`

---

#### **4.5: WebSocket Price Feed** ✅
**File**: `scripts/test_websocket_price_feed.py`
**Scenarios**:
- [ ] Test WebSocket initialization
- [ ] Test WebSocket connection
- [ ] Test futures token subscription (MODE_LTP)
- [ ] Test tick data reception
- [ ] Test tick filtering (only futures token)
- [ ] Test connection close handling
- [ ] Test error handling
- [ ] Test stop functionality
- [ ] Test multiple ticks processing
- [ ] Test connection state tracking
- [ ] Test invalid tick handling

**Log File**: `logs/test_websocket_price_feed_YYYYMMDD_HHMMSS.log`

---

### **Phase 5: Integration Testing** (2 test files)

#### **5.1: Complete Flow Integration** ✅
**File**: `scripts/test_integration_complete_flow.py`
**Scenarios**:
- [ ] Test tick processing (WebSocket → Candle aggregator)
- [ ] Test candle aggregation (tick → 15min candle)
- [ ] Test ML signal generation on running candle
- [ ] Test position-first logic (no ML signals if position exists)
- [ ] Test entry execution (LONG/SHORT)
- [ ] Test exit execution (4-bar, volume, ML exit)
- [ ] Test re-entry logic (too soon, within window, outside window)
- [ ] Test flicker/reversal handling
- [ ] Test same-candle reversal

**Log File**: `logs/test_integration_complete_flow_YYYYMMDD_HHMMSS.log`

---

#### **5.2: State Persistence Integration** ✅
**File**: `scripts/test_integration_state_persistence.py`
**Scenarios**:
- [ ] Test state save at 3:30 PM (complete system state)
- [ ] Test state load at 9:15 AM (restore from database)
- [ ] Test state continuity across sessions
- [ ] Test state update after trade (position saved)
- [ ] Test state update after exit (position cleared, exit bars updated)
- [ ] Test missing state handling (start fresh)
- [ ] Test state with OMS integration (position restored)

**Log File**: `logs/test_integration_state_persistence_YYYYMMDD_HHMMSS.log`

---

### **Phase 6: Gap Protection & Recovery** (2 test files)

#### **6.1: Gap Detection** ✅
**File**: `scripts/test_gap_detection.py`
**Scenarios**:
- [ ] Test gap calculation (futures_today_open - futures_previous_close)
- [ ] Test LONG + Gap DOWN (adverse) → Exit immediately
- [ ] Test LONG + Gap UP (favorable) → Continue normally
- [ ] Test SHORT + Gap UP (adverse) → Exit immediately
- [ ] Test SHORT + Gap DOWN (favorable) → Continue normally
- [ ] Test gap threshold (300 points default, configurable)
- [ ] Test futures previous close loading from saved state
- [ ] Test gap exit integration with OMS
- [ ] Test no position gap check (gap calculated but no exit)

**Log File**: `logs/test_gap_detection_YYYYMMDD_HHMMSS.log`

---

#### **6.2: Recovery Scenarios** ✅
**File**: `scripts/test_recovery_scenarios.py`
**Scenarios**:
- [ ] Test crash recovery (system restarts, loads state)
- [ ] Test position mismatch (broker has position, saved state doesn't)
- [ ] Test position mismatch (saved state has position, broker doesn't)
- [ ] Test position mismatch (both match)
- [ ] Test data gap detection (missing candles)
- [ ] Test no data gaps (continuous data)
- [ ] Test expected timestamps generation (market hours only)
- [ ] Test complete recovery flow (all steps)
- [ ] Test WiFi downtime detection (data gaps from network issues)
- [ ] Test API downtime handling (error handling, graceful recovery)

**Log File**: `logs/test_recovery_scenarios_YYYYMMDD_HHMMSS.log`

---

### **Phase 7: End-to-End Integration** (1 test file)

#### **7.1: End-to-End Integration** ✅
**File**: `scripts/test_end_to_end_integration.py`
**Scenarios**:
- [ ] Test system startup and initialization (all components)
- [ ] Test complete tick to order flow (WebSocket → Candle → Signal → Order)
- [ ] Test gap protection integration (adverse gap → immediate exit)
- [ ] Test candle close flicker and reversal handling
- [ ] Test daily state save and reload (3:30 PM → 9:15 AM)
- [ ] Test recovery flow integration (crash recovery, position mismatch, data gaps)
- [ ] Test position-first logic (complete flow verification)
- [ ] Test complete trading day simulation (9:15 AM → 3:30 PM)

**Log File**: `logs/test_end_to_end_integration_YYYYMMDD_HHMMSS.log`

---

### **Phase 8: Live Zerodha API Testing** (1 test file)

#### **8.1: Live Zerodha API Testing** ✅
**File**: `scripts/test_live_zerodha_api.py`
**Scenarios**:
- [ ] Test authentication & connection (auto-connect)
- [ ] Test futures & option chain (real API)
- [ ] Test margin calculation (real API, basket_order_margins)
- [ ] Test LONG entry (1 lot, dry-run mode)
- [ ] Test SHORT entry (1 lot, dry-run mode)
- [ ] Test exit position (1 lot, dry-run mode)
- [ ] Test WebSocket price feed (real-time ticks)
- [ ] Test complete flow (signal → entry → exit)

**Log File**: `logs/live_api_test_YYYYMMDD_HHMMSS.log`

---

## 🎯 **Test Execution Plan**

### **Execution Order**:
1. **Phase 1**: Data Management & State Persistence (3 test files)
2. **Phase 2**: ML System Core (4 test files)
3. **Phase 3**: Exit Strategies (2 test files)
4. **Phase 4**: OMS Components (5 test files)
5. **Phase 5**: Integration Testing (2 test files)
6. **Phase 6**: Gap Protection & Recovery (2 test files)
7. **Phase 7**: End-to-End Integration (1 test file)
8. **Phase 8**: Live Zerodha API Testing (1 test file)

**Total**: 20 test files, ~150+ test scenarios

---

## 📊 **Test Execution Script**

**Script**: `scripts/run_all_tests.py`
- Runs all test files sequentially
- Maintains logs for each component
- Generates summary report
- Continues on failures (doesn't stop on first error)

---

## ✅ **Success Criteria**

- All test files execute successfully
- All test scenarios pass
- All logs generated correctly
- No errors or warnings (except expected ones)
- Real API tests pass (dry-run mode)
- All components verified end-to-end

---

**Last Updated**: Comprehensive testing plan created
**Status**: Ready to execute all test suites

