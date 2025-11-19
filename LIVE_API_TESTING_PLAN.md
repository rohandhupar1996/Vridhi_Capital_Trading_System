# Live Zerodha API Testing Plan

## 🎯 **Goal**
Test all components with **REAL Zerodha API** in **dry-run mode** using **1 lot** to verify everything works correctly before live trading.

**Testing Approach**: Slow, careful, step-by-step verification of each component with real API responses.

---

## 📋 **Testing Phases**

### **Phase 1: Authentication & Connection** ✅
**Goal**: Verify Zerodha authentication works correctly

**Tests**:
- [x] Auto-connect using `ZerodhaAuthenticator`
- [x] OAuth callback server captures token automatically
- [x] Token saved to file for future use
- [x] KiteConnect instance initialized correctly
- [x] Profile retrieval works
- [x] Connection health check works

**Expected Output**:
- ✅ Authentication successful
- ✅ Token saved to `configs/zerodha_tokens.json`
- ✅ Profile retrieved: `user_name`, `user_id`
- ✅ Connection status: CONNECTED

---

### **Phase 2: Futures & Option Chain** ✅
**Goal**: Verify futures symbol/token retrieval and option chain management

**Tests**:
- [ ] Get current month BankNifty futures symbol (e.g., `BANKNIFTY25NOVFUT`)
- [ ] Get futures token (e.g., `260105`)
- [ ] Fetch option chain from Zerodha
- [ ] Verify option chain expiry date (last Tuesday of month)
- [ ] Test ATM strike calculation (nearest to futures LTP)
- [ ] Test hedge strike calculation (20 legs away)
- [ ] Verify option chain caching works

**Expected Output**:
- ✅ Futures symbol retrieved: `BANKNIFTY25NOVFUT`
- ✅ Futures token retrieved: `260105`
- ✅ Option chain fetched: 102 contracts
- ✅ Current expiry: `2025-11-25` (last Tuesday)
- ✅ ATM strike calculated correctly (e.g., 57300 for LTP 57250)
- ✅ Hedge strike calculated correctly (e.g., 55300 for LONG, 59300 for SHORT)
- ✅ Option chain cached for faster access

---

### **Phase 3: Margin Calculation (Real API)** ✅
**Goal**: Verify margin calculation using Zerodha's `basket_order_margins` API

**Tests**:
- [ ] Test LONG margin calculation (1 lot)
  - SELL PE (ATM)
  - BUY CE (ATM)
  - BUY PE (hedge, 20 legs down)
- [ ] Test SHORT margin calculation (1 lot)
  - SELL CE (ATM)
  - BUY PE (ATM)
  - BUY CE (hedge, 20 legs up)
- [ ] Verify spread benefit (~63% reduction with 3-leg strategy)
- [ ] Test available margin check
- [ ] Verify pre-calculation works

**Expected Output**:
- ✅ LONG margin (1 lot): ~₹46,250 (370,000 / 8)
- ✅ SHORT margin (1 lot): ~₹14,560 (116,480 / 8)
- ✅ Spread benefit: ~63% reduction
- ✅ Available margin > required margin
- ✅ Margins pre-calculated correctly

---

### **Phase 4: LONG Entry (1 Lot, Dry Run)** ✅
**Goal**: Test LONG entry execution with real API (dry run mode)

**Strategy**: 3-leg LONG
- **SELL**: ATM PE (e.g., 57300 PE)
- **BUY**: ATM CE (e.g., 57300 CE)
- **BUY**: Hedge PE (e.g., 55300 PE, 20 legs down)

**Tests**:
- [ ] Pre-calculate LONG margin (1 lot)
- [ ] Verify margin availability
- [ ] Get option symbols from option chain
- [ ] Place orders in correct sequence (BUY first, then SELL)
- [ ] Verify order types: MARKET, NRML
- [ ] Verify order quantities: 35 (1 lot × 35 contracts)
- [ ] Track order execution status
- [ ] Verify position established correctly
- [ ] Log option contracts to database

**Expected Output**:
- ✅ All 3 legs placed successfully
- ✅ Orders executed: BUY first, then SELL
- ✅ Position type: LONG
- ✅ Entry price: Futures LTP
- ✅ ATM strike: Nearest to futures LTP
- ✅ Hedge strike: 20 legs away
- ✅ Position logged to database

---

### **Phase 5: SHORT Entry (1 Lot, Dry Run)** ✅
**Goal**: Test SHORT entry execution with real API (dry run mode)

**Strategy**: 3-leg SHORT
- **SELL**: ATM CE (e.g., 57300 CE)
- **BUY**: ATM PE (e.g., 57300 PE)
- **BUY**: Hedge CE (e.g., 59300 CE, 20 legs up)

**Tests**:
- [ ] Exit LONG position first (if exists)
- [ ] Pre-calculate SHORT margin (1 lot)
- [ ] Verify margin availability
- [ ] Get option symbols from option chain
- [ ] Place orders in correct sequence (BUY first, then SELL)
- [ ] Verify order types: MARKET, NRML
- [ ] Verify order quantities: 35 (1 lot × 35 contracts)
- [ ] Track order execution status
- [ ] Verify position established correctly
- [ ] Log option contracts to database

**Expected Output**:
- ✅ LONG position exited (if exists)
- ✅ All 3 legs placed successfully
- ✅ Orders executed: BUY first, then SELL
- ✅ Position type: SHORT
- ✅ Entry price: Futures LTP
- ✅ ATM strike: Nearest to futures LTP
- ✅ Hedge strike: 20 legs away
- ✅ Position logged to database

---

### **Phase 6: Exit Position (1 Lot, Dry Run)** ✅
**Goal**: Test position exit with real API (dry run mode)

**Tests**:
- [ ] Exit all 3 legs of position
- [ ] Verify exit order types: MARKET, NRML
- [ ] Verify exit order quantities: 35 (1 lot × 35 contracts)
- [ ] Track exit order execution status
- [ ] Verify position cleared correctly
- [ ] Update position state in database

**Expected Output**:
- ✅ All 3 legs exited successfully
- ✅ Position cleared: PositionType.NONE
- ✅ Exit orders executed at market price
- ✅ Position state updated in database

---

### **Phase 7: WebSocket Price Feed** ✅
**Goal**: Verify real-time price feed from Zerodha WebSocket

**Tests**:
- [ ] Connect to Zerodha WebSocket (KiteTicker)
- [ ] Subscribe to futures token (MODE_LTP)
- [ ] Receive real-time price ticks
- [ ] Update OrderManager with latest futures price
- [ ] Verify price updates correctly
- [ ] Test reconnection on disconnect
- [ ] Verify connection state tracking

**Expected Output**:
- ✅ WebSocket connected successfully
- ✅ Futures token subscribed: `260105`
- ✅ Real-time ticks received (LTP updates)
- ✅ OrderManager updated with latest price
- ✅ Price updates every few seconds
- ✅ Reconnection works on disconnect

---

### **Phase 8: Integration Test - Complete Flow** ✅
**Goal**: Test complete flow from signal to order execution

**Tests**:
- [ ] Simulate LONG signal from ML algorithm
- [ ] Check position (none exists) → Proceed
- [ ] Generate LONG entry via RunningSignalExecutor
- [ ] Execute LONG entry via OrderManager (1 lot, dry run)
- [ ] Verify position established
- [ ] Simulate 4-bar exit signal
- [ ] Execute exit via OrderManager
- [ ] Verify position cleared

**Expected Output**:
- ✅ Signal → Entry → Position established
- ✅ Exit signal → Position cleared
- ✅ All orders executed correctly
- ✅ Position state updated correctly

---

## 🧪 **Testing Script Structure**

### **Script**: `scripts/test_live_zerodha_api.py`

**Functions**:
1. `test_authentication()` - Phase 1
2. `test_futures_and_option_chain()` - Phase 2
3. `test_margin_calculation()` - Phase 3
4. `test_long_entry()` - Phase 4
5. `test_short_entry()` - Phase 5
6. `test_exit_position()` - Phase 6
7. `test_websocket_price_feed()` - Phase 7
8. `test_complete_flow()` - Phase 8

---

## ⚙️ **Configuration**

### **Testing Parameters**:
- **Lot Size**: 1 lot (for safety)
- **Dry Run**: `True` (no real orders placed)
- **Margin Safety**: Check available margin before entry
- **Timeout**: 30 seconds per test phase
- **Retry Logic**: 3 attempts for API calls

### **Expected Results**:
- All API calls return successfully
- Orders placed in correct sequence
- Position state tracked correctly
- WebSocket feeds real-time prices
- All components integrate correctly

---

## 🔒 **Safety Measures**

1. **Dry Run Mode**: All orders are placed with `dry_run=True`
2. **1 Lot Only**: Minimal position size for testing
3. **Margin Check**: Verify available margin before entry
4. **Error Handling**: Graceful failure with detailed error messages
5. **Logging**: All operations logged for audit trail

---

## 📊 **Success Criteria**

✅ **All phases pass**:
- Authentication works
- Futures/option chain retrieved correctly
- Margins calculated correctly
- LONG entry executed (dry run)
- SHORT entry executed (dry run)
- Exit executed (dry run)
- WebSocket price feed works
- Complete flow works end-to-end

✅ **No errors**:
- All API calls successful
- No exceptions thrown
- Position state tracked correctly
- Orders executed in correct sequence

✅ **Ready for Live Trading**:
- All components verified with real API
- Dry run mode works correctly
- Ready to switch to `dry_run=False` for live trading

---

## 🚀 **Next Steps After Testing**

1. Review all test results
2. Verify all logs are correct
3. Switch to `dry_run=False` (with approval)
4. Start with 1 lot in live trading
5. Monitor first few trades closely
6. Gradually increase lot size if needed

---

**Last Updated**: Testing plan created
**Status**: Ready to begin Phase 1

