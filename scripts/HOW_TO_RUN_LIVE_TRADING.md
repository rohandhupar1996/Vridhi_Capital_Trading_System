# How to Run Live Trading - Simple Steps

## 🚀 Step-by-Step Guide

### Step 1: Check/Refresh Token (Before Market Opens)
```bash
PYTHONPATH=. python scripts/zerodha_login.py
```
**What it does:**
- Opens browser for Zerodha login
- Gets new access token
- Saves token to file

**When:** Before market opens (9:00 AM) or if token expired

---

### Step 2: Start Live Trading Script
```bash
PYTHONPATH=. python scripts/live_trading.py
```

**What happens automatically:**

1. **Authenticate** → Logs into Zerodha
2. **Initialize OMS** → Sets up order management (8 lots)
3. **Get Futures Token** → Finds BankNifty futures contract
4. **Start WebSocket** → Connects for real-time prices
5. **Wait for Price** → Gets initial futures price
6. **Pre-calculate Margins** → Calculates margin requirements
7. **Initialize Signal Executor** → Sets up signal handling
8. **Start Trading Loop** → Waits for signals

---

### Step 3: System Runs Automatically

**Once started, the system:**
- ✅ Receives real-time prices via WebSocket
- ✅ Generates signals (you need to add signal generation logic)
- ✅ Checks margin before each trade
- ✅ Places orders: BUY legs first, then SELL leg
- ✅ Handles flicker, reversals, exits automatically
- ✅ Monitors positions continuously

---

### Step 4: Stop Trading (When Done)
**Press:** `Ctrl+C`

**What happens:**
- Stops WebSocket connection
- Closes all connections gracefully
- Logs final status

---

## 📋 Quick Checklist

**Before Market Opens:**
- [ ] Run `zerodha_login.py` to refresh token
- [ ] Check WebSocket: `python scripts/test_websocket_direct.py`
- [ ] Verify config: Check `configs/config.yaml` (lot_size=8)

**At Market Open (9:15 AM):**
- [ ] Run `python scripts/live_trading.py`
- [ ] System starts automatically
- [ ] Monitor logs for signals and trades

**During Trading:**
- [ ] System runs automatically
- [ ] Watch logs for entries/exits
- [ ] Press Ctrl+C to stop when done

---

## ⚠️ Important Notes

1. **Signal Generation Needed:**
   - Script framework is ready
   - You need to add your signal generation logic
   - Currently has placeholder: "Signal generation integration needed"

2. **Real Trades:**
   - Set `dry_run=False` in script (line ~128)
   - This executes REAL trades with real money
   - Test thoroughly first!

3. **Market Hours:**
   - Best during: 9:15 AM - 3:30 PM IST
   - WebSocket works anytime but best during market hours

---

## 🎯 Simple Answer

**To start live trading:**

1. **Refresh token:** `PYTHONPATH=. python scripts/zerodha_login.py`
2. **Start trading:** `PYTHONPATH=. python scripts/live_trading.py`
3. **System runs automatically** - receives prices, checks margin, places orders
4. **Stop:** Press `Ctrl+C`

**That's it!** The script handles everything else automatically.

