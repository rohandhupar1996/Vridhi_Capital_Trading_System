# Futures Price Verification

## ✅ CONFIRMED: System Uses BankNifty FUTURES Price Only (Not Spot/Cash)

This document verifies that the OMS uses **BankNifty FUTURES contract price** exclusively for all calculations and trading decisions.

---

## Key Verification Points

### 1. Futures Symbol Format
```python
# Symbol format: BANKNIFTY{YY}{MONTH}FUT
# Example: BANKNIFTY24JANFUT, BANKNIFTY24FEBFUT
# ✅ Ends with 'FUT' - explicitly futures contract
```

**Location**: `order_manager.py::_get_current_futures_symbol()`
- Symbol: `BANKNIFTY{year_suffix}{month}FUT`
- **Only** futures contracts (ends with 'FUT')
- **Never** uses spot/cash symbols

---

### 2. Futures Token Validation
```python
def _get_futures_token(self):
    # Ensures symbol ends with 'FUT' (futures only)
    if (inst['tradingsymbol'] == self.futures_symbol and 
        inst['tradingsymbol'].endswith('FUT')):
        return token
```

**Location**: `order_manager.py::_get_futures_token()`
- ✅ Explicitly checks for 'FUT' suffix
- ✅ Rejects any non-futures contracts
- ✅ Only matches futures instruments

---

### 3. Price Update from Ticks
```python
def update_futures_price(self, tick: Dict):
    # ONLY accepts ticks from futures_token
    if self.futures_token and tick.get('instrument_token') == self.futures_token:
        self.futures_ltp = tick.get('last_price')
```

**Location**: `order_manager.py::update_futures_price()`
- ✅ Only accepts ticks from futures contract token
- ✅ Rejects spot/cash ticks automatically
- ✅ Validates price > 0 before accepting

---

### 4. Direct Futures Price Fetch
```python
def get_futures_price_from_broker(self):
    # Gets quote for futures contract only
    quote = self.kite.quote(f"NFO:{self.futures_symbol}")
    # self.futures_symbol = "BANKNIFTY24JANFUT" (futures only)
```

**Location**: `order_manager.py::get_futures_price_from_broker()`
- ✅ Fetches price from futures symbol only
- ✅ Uses `self.futures_symbol` which is always futures contract
- ✅ Never queries spot/cash prices

---

### 5. ATM Strike Calculation
```python
def _calculate_atm_strike(self, futures_price: float) -> int:
    # Uses futures_price parameter (from futures contract)
    atm_strike = int(round(futures_price / 100) * 100)
```

**Location**: `order_manager.py::_calculate_atm_strike()`
- ✅ Uses `self.futures_ltp` which is always futures price
- ✅ Validates futures_price > 0
- ✅ Never uses spot price

---

### 6. Entry Methods (LONG/SHORT)
```python
def enter_long(self):
    # Validates futures price exists
    if not self.futures_ltp:
        self.get_futures_price_from_broker()  # Fetches futures price
    
    # Uses futures price for ATM calculation
    atm_strike = self._calculate_atm_strike(self.futures_ltp)
```

**Location**: `order_manager.py::enter_long()` and `enter_short()`
- ✅ Always uses `self.futures_ltp` (futures price)
- ✅ Fetches from broker if missing (futures contract only)
- ✅ Validates futures price before use
- ✅ Never references spot/cash price

---

### 7. Margin Calculations
```python
def calculate_long_margin(..., futures_price: float):
    # futures_price parameter is from futures contract
    # Used for SPAN margin calculation
```

**Location**: `margin_calculator.py::calculate_long_margin()` and `calculate_short_margin()`
- ✅ Accepts `futures_price` parameter (from futures contract)
- ✅ Documentation explicitly states "NOT spot/cash"
- ✅ Uses futures price for margin calculations

---

## Flow Verification

### Complete Flow (LONG Entry Example):

```
1. Initialize OMS
   → Gets futures symbol: "BANKNIFTY24JANFUT" ✅
   → Gets futures token: 12345678 ✅

2. Update Price from Tick
   → Checks: tick['instrument_token'] == futures_token ✅
   → Only accepts if matches futures token ✅
   → Updates: self.futures_ltp = futures_price ✅

3. Calculate ATM Strike
   → Input: self.futures_ltp (futures price) ✅
   → Output: ATM strike based on futures ✅

4. Place Orders
   → BUY BANKNIFTY{atm_strike}CE ✅
   → BUY BANKNIFTY{hedge_strike}PE ✅
   → SELL BANKNIFTY{atm_strike}PE ✅
   → All strikes calculated from futures price ✅
```

---

## What is NOT Used

❌ **Spot Price** (BANKNIFTY index from NSE)
❌ **Cash Price** (BANKNIFTY cash segment)
❌ **Any non-FUTURES contract**

---

## Verification Test

To verify the system is using futures price:

```python
# Check futures symbol
print(oms.futures_symbol)  
# Output: "BANKNIFTY24JANFUT" ✅ (ends with FUT)

# Check futures price source
print(oms.futures_ltp)
# This price is from futures contract only ✅

# Check ATM strike calculation
atm = oms._calculate_atm_strike(oms.futures_ltp)
# ATM strike is based on futures price ✅
```

---

## Summary

✅ **All price calculations use BankNifty FUTURES contract price**
✅ **Symbol format explicitly uses 'FUT' suffix**
✅ **Token validation ensures futures contract only**
✅ **No spot/cash price references anywhere**
✅ **All documentation explicitly states "futures price (NOT spot/cash)"**

**The system is 100% futures-based for all trading decisions.**


