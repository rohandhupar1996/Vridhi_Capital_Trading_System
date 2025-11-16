# Running-Candle Signal Executor (Flicker + Reversal)

Implements immediate execution on running-candle signals, strict flicker cleanup at candle close, and same-candle reversal handling.

## Rules
- Enter immediately on running-candle signals (before candle close)
- If the signal that triggered the entry does NOT exist at candle close → EXIT immediately (flicker cleanup)
- If the signal reverses within the same candle → EXIT and ENTER the reversed side instantly
- After candle close, the system continues normally

## Usage

```python
from datetime import datetime
from src.trading_system.oms import OrderManager
from src.trading_system.oms.running_signal_executor import RunningSignalExecutor

# Assume you already have a kite instance and an OrderManager
oms = OrderManager(kite=kite, lot_size=8, hedge_legs=20)
executor = RunningSignalExecutor(oms)

# When a new candle starts (optional if you pass candle_id directly)
candle_id = "2025-11-16 09:15:00_5min"
executor.start_new_candle(candle_id, opened_at=datetime.now())

# Running-candle signal arrives (use current futures price)
futures_price = 50000.0
executor.on_running_signal("LONG", candle_id, futures_price)

# Same-candle reversal to SHORT (exit and reverse immediately)
executor.on_running_signal("SHORT", candle_id, futures_price)

# Candle closes, final signal known (e.g., NONE → flicker cleanup)
executor.on_candle_close(final_signal="NONE", candle_id=candle_id, futures_price=futures_price)
```

## Candle ID
Provide a stable `candle_id` per bar (e.g., `"YYYY-MM-DD HH:MM:SS_5min"`). The executor uses this to:
- Detect same-candle reversals
- Exit if the entry signal flickers away by candle close

## Integration Notes
- The executor delegates all trading to `OrderManager`:
  - `enter_long(fast_execution=True)`
  - `enter_short(fast_execution=True)`
  - `exit_position()`
- Ensure `oms.futures_ltp` is kept fresh via ticks or pass `futures_price` to the executor calls (the executor forwards it to the OMS).

## Behavior Matrix
- Running LONG → at close signal NONE → EXIT (flicker cleanup)
- Running LONG → flips to SHORT same candle → EXIT long, ENTER short
- At close signal exists and differs from position → switch to final signal
- At close signal matches position → keep as-is


