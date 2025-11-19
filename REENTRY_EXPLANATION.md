# Re-Entry Logic Explained

## 🎯 **What is Re-Entry?**

Re-entry logic prevents taking the **SAME side trade** too quickly after an exit. It enforces a **"pause"** before re-entering in the same direction to prevent overtrading.

---

## 📊 **Re-Entry Window (Currently: 3 to 50 bars)**

### **Example Scenario:**

Let's say we exit a **LONG** trade at bar 10:

```
Bar 10: LONG exited (last_long_exit_bar = 10)
Bar 11: ❌ Cannot enter LONG (too soon, < 3 bars)
Bar 12: ❌ Cannot enter LONG (too soon, < 3 bars)
Bar 13: ✅ CAN enter LONG IF prediction confirms (3 bars passed, within window)
Bar 14-60: ✅ CAN enter LONG IF prediction confirms (within window 3-50)
Bar 61+: ✅ Can enter LONG freely (outside window, > 50 bars)
```

---

## 🎯 **Re-Entry Rules (3 Zones)**

### **1. TOO SOON (< 3 bars since exit)**
- ❌ **Cannot re-enter at all** (forced pause)
- **Reason**: Prevent overtrading, let market settle
- **Example**: Exited at bar 10 → Cannot enter same side until bar 13

### **2. WITHIN WINDOW (3-50 bars since exit)**
- ✅ **Can re-enter ONLY if prediction confirms direction**
  - **LONG**: `prediction > 0` (ML thinks bullish)
  - **SHORT**: `prediction < 0` (ML thinks bearish)
- **Reason**: Ride the trend if ML confirms momentum is continuing
- **Example**: 
  - Bar 13: LONG signal + prediction > 0 → ✅ Re-enter
  - Bar 14: LONG signal BUT prediction < 0 → ❌ Skip (no confirmation)

### **3. OUTSIDE WINDOW (> 50 bars since exit)**
- ✅ **Can re-enter freely** (no restrictions)
- **Reason**: Enough time passed, treat as fresh signal
- **Example**: Exited at bar 10 → Can enter freely after bar 60

---

## 💡 **Why Re-Entry? (Example Without vs With)**

### **WITHOUT Re-Entry (Overtrading):**
```
Bar 10: LONG signal → Enter
Bar 11: LONG signal → Enter again ❌ (overtrading!)
Bar 12: LONG signal → Enter again ❌ (risky!)
Bar 13: Market reverses → All positions hit stop loss
Result: Losses accumulate quickly
```

### **WITH Re-Entry (Controlled):**
```
Bar 10: LONG exited
Bar 11-12: Wait (pause, < 3 bars) → No entries
Bar 13: LONG signal + prediction confirms → ✅ Re-enter
Bar 14: LONG signal BUT prediction unclear → Skip
Bar 15: LONG signal + prediction confirms → ✅ Re-enter
Result: Rides momentum only when ML confirms
```

---

## ✅ **Benefits of Re-Entry Logic**

1. **Prevents Overtrading**
   - Forced pause of 3 bars prevents entering same side too quickly
   - Reduces risk of accumulating losses in choppy markets

2. **Rides Momentum (Within Window)**
   - If ML confirms direction (prediction > 0 for LONG), allows re-entry
   - Catches strong trending moves while avoiding false signals

3. **Avoids Chop/Whipsaws**
   - Requires prediction confirmation (not just signal)
   - Prevents re-entering on weak signals that reverse quickly

4. **Allows Fresh Entries (Outside Window)**
   - After 50 bars, treat as completely fresh signal
   - No restrictions after enough time has passed

---

## 🚀 **Special Case: Volume Peak Exit on Same Candle as Entry**

### **Scenario (Fast Momentum):**
```
Running Candle (Bar 100):
  1. Signal generated → LONG entered at 57700
  2. Momentum is FAST → Price spikes to 57900
  3. Price crosses volume peak at 57850 → Exit immediately
  4. Same candle: Entry AND Exit both happen
  5. Mark this candle as exit bar (last_long_exit_bar = 100)
  6. Re-entry countdown starts: 
     - Bar 101-102: Cannot re-enter (< 3 bars)
     - Bar 103+: Can re-enter if prediction confirms (within 3-50 window)
```

### **Why This Matters:**
- **Fast momentum**: Price can move very quickly within a single 15min candle
- **Capture profits**: Volume peak exit catches profit targets immediately
- **Re-entry starts**: Countdown begins from the exit bar (same candle as entry if fast enough)

### **Implementation:**
1. Check volume exit **AFTER** processing entry (on same tick)
2. If volume exit triggers on same candle → Exit immediately
3. Update `last_long_exit_bar` or `last_short_exit_bar` to current candle index
4. Re-entry logic applies from next candle onwards

---

## 📋 **Code Logic**

```python
# Re-entry check before entry
if oms.position.position_type == PositionType.NONE:
    bars_since_long_exit = current_bar - last_long_exit_bar
    
    can_enter_long = (
        last_long_exit_bar < 0 or  # Never traded before
        bars_since_long_exit > 50 or  # Outside window (> 50 bars)
        (3 <= bars_since_long_exit <= 50 and prediction > 0)  # Within window + confirms
    )
    
    if signal == "LONG" and can_enter_long:
        enter_long()

# After entry, check volume exit on same candle
if oms.position.position_type == PositionType.LONG:
    volume_exit = check_volume_peak_exit(
        current_high=running_candle.high,
        current_low=running_candle.low,
        entry_price=entry_price
    )
    
    if volume_exit:
        exit_position()
        last_long_exit_bar = current_bar  # Same candle as entry!
        # Re-entry countdown: Bar+1, Bar+2 cannot enter, Bar+3+ can if confirms
```

---

## 🎯 **Summary**

**Re-entry = Smart Pause + Momentum Riding**

- **First 3 bars**: Forced pause (no re-entry)
- **Bars 3-50**: Can re-enter if ML confirms (rides momentum)
- **After 50 bars**: Free re-entry (fresh signal)

**Same Candle Exit**: If momentum is fast and volume peak is hit on same candle as entry, exit immediately and start re-entry countdown from that candle.

---

**Questions?** This logic prevents overtrading while allowing us to ride strong trending moves when ML confirms the momentum continues.

