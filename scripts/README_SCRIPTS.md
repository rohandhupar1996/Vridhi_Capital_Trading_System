# Scripts Guide - Which Script to Run When

## 🔐 Authentication & Token Management

### 1. `zerodha_login.py` - Get/Refresh Access Token
**When to run:**
- First time setup
- When access token expires (daily)
- When you get "token invalid" errors

**Command:**
```bash
PYTHONPATH=. python scripts/zerodha_login.py
```

**What it does:**
- Opens browser for Zerodha login
- Gets request_token from redirect URL
- Converts to access_token
- Saves to `configs/zerodha_tokens.json`

**Run this:** ✅ **If token is expired or invalid**

---

## ✅ WebSocket Testing

### 2. `check_websocket_simple.py` - Quick WebSocket Check
**When to run:**
- Check if KiteTicker is available
- Verify credentials are valid
- Quick setup verification

**Command:**
```bash
PYTHONPATH=. python scripts/check_websocket_simple.py
```

**What it does:**
- Checks if KiteTicker class exists
- Validates API key and token
- Tests KiteTicker initialization
- **Does NOT connect to WebSocket** (just checks setup)

**Run this:** ✅ **To verify basic setup**

---

### 3. `test_websocket_direct.py` - Full WebSocket Test
**When to run:**
- Test actual WebSocket connection
- Verify Connect subscription includes WebSocket
- Test during market hours for real-time ticks

**Command:**
```bash
PYTHONPATH=. python scripts/test_websocket_direct.py
```

**What it does:**
- Validates token
- Connects to Zerodha WebSocket
- Subscribes to BankNifty futures
- Receives tick data
- **Shows if WebSocket is working**

**Run this:** ✅ **To test WebSocket connection (works anytime, but best during market hours)**

---

### 4. `test_websocket_access.py` - Full Authentication + WebSocket Test
**When to run:**
- Complete end-to-end test
- If you want to re-authenticate and test

**Command:**
```bash
PYTHONPATH=. python scripts/test_websocket_access.py
```

**What it does:**
- Handles authentication
- Tests WebSocket connection
- More comprehensive test

**Run this:** ⚠️ **Usually not needed - use `test_websocket_direct.py` instead**

---

## 🔄 Token Conversion (DEPRECATED)

### 5. `convert_token.py` - Convert Request Token to Access Token
**⚠️ NOT NEEDED** - `zerodha_login.py` already does this automatically!

**When to run:**
- ~~If you have a request_token from login URL~~ ❌ Use `zerodha_login.py` instead
- ~~Need to manually convert token~~ ❌ Use `zerodha_login.py` instead

**Command:**
```bash
PYTHONPATH=. python scripts/convert_token.py
```

**What it does:**
- Takes request_token or access_token
- Converts/validates it
- Saves to token file

**Run this:** ❌ **Don't use - `zerodha_login.py` handles everything automatically**

---

## 🚀 Live Trading

### 6. `live_trading.py` - **LIVE TRADING SCRIPT** ⭐
**When to run:**
- **For actual live trading** during market hours
- Real-time WebSocket price feed
- Live order execution

**Command:**
```bash
PYTHONPATH=. python scripts/live_trading.py
```

**What it does:**
- Connects to Zerodha WebSocket for real-time prices
- Initializes OMS for order execution
- Sets up signal executor (flicker, reversal handling)
- Dynamic timeframe (expiry day 5min switch)
- Earnings filter
- **Executes real trades** (set `dry_run=False` in script)

**⚠️ IMPORTANT:**
- This executes **REAL TRADES** with real money!
- Make sure you understand the system before running
- Test with `dry_run=True` first
- Run during market hours (9:15 AM - 3:30 PM IST)

**Run this:** ✅ **For live trading (after thorough testing)**

---

## 📊 System Simulation

### 7. `system_simulation.py` - End-to-End System Test
**When to run:**
- Test entire trading system with historical data
- Test OMS, signals, order placement
- Uses October-November data with 2-minute delays

**Command:**
```bash
PYTHONPATH=. python scripts/system_simulation.py
```

**What it does:**
- Loads historical candles from DB
- Generates signals
- Tests OMS entry/exit
- Attempts real orders (will fail if market closed)
- Tests rate limiting, margin management, etc.

**Run this:** ✅ **To test full system logic**

---

## 📋 Quick Reference

### Daily Startup (Before Trading):
```bash
# 1. Check/refresh token if needed
PYTHONPATH=. python scripts/zerodha_login.py

# 2. Quick WebSocket check
PYTHONPATH=. python scripts/check_websocket_simple.py

# 3. Full WebSocket test (during market hours)
PYTHONPATH=. python scripts/test_websocket_direct.py
```

### Testing System:
```bash
# Test full system with historical data
PYTHONPATH=. python scripts/system_simulation.py
```

### Troubleshooting:
```bash
# If token issues
PYTHONPATH=. python scripts/zerodha_login.py

# If WebSocket not working
PYTHONPATH=. python scripts/test_websocket_direct.py
```

---

## 🎯 Most Common Scripts

### ✅ **For WebSocket Testing:**
```bash
PYTHONPATH=. python scripts/test_websocket_direct.py
```
**This is the main script to test WebSocket!**

### ✅ **For Token Refresh:**
```bash
PYTHONPATH=. python scripts/zerodha_login.py
```
**Run this when token expires (daily)**

### ✅ **For System Testing:**
```bash
PYTHONPATH=. python scripts/system_simulation.py
```
**Test full trading system**

---

## 📝 Notes

- **All scripts need:** `PYTHONPATH=.` prefix
- **Token expires:** Daily (refresh before trading)
- **WebSocket works:** Anytime, but best during market hours (9:15 AM - 3:30 PM IST)
- **Market closed:** WebSocket still connects but shows last traded price

