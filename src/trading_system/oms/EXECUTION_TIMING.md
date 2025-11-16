# Order Execution Timing Analysis

## Simple Flow - Time Breakdown

### ENTRY Execution (LONG or SHORT)

#### Scenario 1: Fast Execution Mode (Pre-calculated Margins)
**Best Case - Signal at 9:15 AM with pre-calculated margins**

```
Signal Arrives                    → 0.00s
Calculate ATM Strike              → 0.01s (instant calculation)
Skip Margin Check (fast_execution=True) → 0.00s
─────────────────────────────────────────────
BUY Leg 1 (ATM CE/PE):
  - Place Order                   → 0.10-0.20s (API call)
  - Wait for execution            → 0.50s (safety delay)
  - Check Status                  → 0.10s (API call)
  Subtotal:                       → 0.70-0.80s

BUY Leg 2 (Hedge 20 legs away):
  - Place Order                   → 0.10-0.20s (API call)
  - Wait for execution            → 0.50s (safety delay)
  - Check Status                  → 0.10s (API call)
  Subtotal:                       → 0.70-0.80s

SELL Leg (ATM PE/CE):
  - Place Order                   → 0.10-0.20s (API call)
  - Wait for execution            → 0.50s (safety delay)
  - Check Status                  → 0.10s (API call)
  Subtotal:                       → 0.70-0.80s
─────────────────────────────────────────────
TOTAL TIME:                       → 2.1-2.4 seconds
```

**Note**: MARKET orders execute instantly on exchange (milliseconds), but we wait 0.5s between orders for safety and status confirmation.

---

#### Scenario 2: Normal Execution Mode (No Pre-calculation)
**Signal at any time without pre-calculated margins**

```
Signal Arrives                    → 0.00s
Calculate ATM Strike              → 0.01s
Margin Check:
  - Get Option Quotes (3 symbols) → 0.30-0.50s (API call)
  - Calculate Margin              → 0.10s (calculation)
  - Check Available Margin       → 0.10-0.20s (API call)
  Subtotal:                       → 0.50-0.80s
─────────────────────────────────────────────
BUY Leg 1 (ATM CE/PE):
  - Place Order                   → 0.10-0.20s
  - Wait for execution            → 0.50s
  - Check Status                  → 0.10s
  Subtotal:                       → 0.70-0.80s

BUY Leg 2 (Hedge):
  - Place Order                   → 0.10-0.20s
  - Wait for execution            → 0.50s
  - Check Status                  → 0.10s
  Subtotal:                       → 0.70-0.80s

SELL Leg (ATM PE/CE):
  - Place Order                   → 0.10-0.20s
  - Wait for execution            → 0.50s
  - Check Status                  → 0.10s
  Subtotal:                       → 0.70-0.80s
─────────────────────────────────────────────
TOTAL TIME:                       → 2.6-3.2 seconds
```

---

### EXIT Execution (All Legs Together)

```
Signal Arrives                    → 0.00s
Get Current Positions             → 0.10-0.20s (API call)
Create Exit Orders                → 0.01s
─────────────────────────────────────────────
Place All Exit Orders Simultaneously:
  - Order 1                       → 0.10-0.20s
  - Order 2                       → 0.10-0.20s
  - Order 3                       → 0.10-0.20s
  (All placed in parallel)
  
Wait for All Orders                → 1.00s (safety delay)
Check All Order Statuses           → 0.20-0.30s (API call)
─────────────────────────────────────────────
TOTAL TIME:                       → 1.4-1.9 seconds
```

---

### STOP LOSS Execution

Same as EXIT - all legs together:
```
TOTAL TIME:                       → 1.4-1.9 seconds
```

---

## Summary Table

| Operation | Fast Execution | Normal Execution | Notes |
|-----------|---------------|------------------|-------|
| **LONG Entry** | **2.1-2.4s** | **2.6-3.2s** | 3 orders sequential |
| **SHORT Entry** | **2.1-2.4s** | **2.6-3.2s** | 3 orders sequential |
| **EXIT** | **1.4-1.9s** | **1.4-1.9s** | All orders together |
| **STOP LOSS** | **1.4-1.9s** | **1.4-1.9s** | All orders together |

---

## Key Timing Factors

### 1. API Call Latency
- **Place Order**: 0.10-0.20s (network + broker processing)
- **Check Status**: 0.10s (query broker)
- **Get Quotes**: 0.30-0.50s (fetch 3 option prices)
- **Get Margins**: 0.10-0.20s (query broker)

### 2. Safety Delays
- **Between Orders**: 0.5s (prevents rate limiting, allows fill confirmation)
- **After All Orders**: 1.0s (for exit/SL when placing together)

### 3. Exchange Execution
- **MARKET Orders**: Execute in **milliseconds** on exchange
- Our delays are for **confirmation**, not execution

---

## Optimization Tips

### For Fastest Execution (9:15 AM Signals):

1. **Pre-calculate Margins** (before market opens):
   ```python
   # At 9:00 AM or when futures price available
   oms.futures_ltp = futures_price
   oms.pre_calculate_margins()  # Takes 1-2 seconds, done once
   ```

2. **Use Fast Execution Mode**:
   ```python
   oms.enter_long(fast_execution=True)   # Saves 0.5-0.8s
   ```

3. **Keep Futures Price Updated**:
   ```python
   # Update from tick data continuously
   oms.update_futures_price(tick)
   ```

### Expected Performance:

- **Best Case (9:15 AM with pre-calculation)**: **~2.1 seconds**
- **Normal Case (anytime)**: **~2.6-3.2 seconds**
- **Exit/SL (anytime)**: **~1.4-1.9 seconds**

---

## Real-World Considerations

### Network Latency
- Add 0.1-0.3s if network is slow
- Broker API may have additional delays during high volatility

### Market Conditions
- High volatility: Orders may fill faster (more liquidity)
- Low volatility: Orders may take slightly longer

### Sequential Lot Reduction
- If margin issues occur, add **+2-3 seconds** per retry attempt
- System automatically reduces lot size: 8 → 4 → 2 → 1

### Partial Fills
- If partial fills occur, system handles gracefully
- No additional time penalty (works with whatever is filled)

---

## Example: Complete Flow at 9:15 AM

```
9:15:00.000 - Signal arrives (LONG)
9:15:00.010 - ATM strike calculated
9:15:00.010 - Fast execution mode (skip margin check)
9:15:00.110 - BUY ATM CE order placed
9:15:00.610 - BUY ATM CE confirmed
9:15:00.710 - BUY Hedge PE order placed
9:15:01.210 - BUY Hedge PE confirmed
9:15:01.310 - SELL ATM PE order placed
9:15:01.810 - SELL ATM PE confirmed
9:15:01.810 - ✅ Position established
─────────────────────────────────────
Total: ~1.8 seconds (ideal case)
```

**Note**: In practice, with network latency and broker processing, expect **2.1-2.4 seconds** for fast execution mode.


