# Dynamic Timeframe Switching (Expiry Day)

On the monthly expiry day (last Thursday), the system switches the signal timeframe to **5min** for that day only, then reverts to the default (e.g., **15min**) from the next day.

## API

```python
from datetime import datetime
from src.trading_system.oms.dynamic_timeframe import (
    DynamicTimeframeController,
    DynamicTimeframeConfig,
)

cfg = DynamicTimeframeConfig(
    base_timeframe="15min",
    expiry_day_timeframe="5min",
    enable_expiry_switch=True,
)
controller = DynamicTimeframeController(config=cfg)

now = datetime.now()
effective_tf = controller.get_effective_timeframe(now)
print(effective_tf)  # "5min" on expiry day, otherwise "15min"
```

## How expiry is determined
- Uses the **last Thursday** of the month
- Ignores holiday shifts (can be extended with an exchange calendar if needed)

## Integration
- Use `get_effective_timeframe()` wherever you load/select the timeframe for your signal engine / data feed.
- This does not change any other system logic; it only changes the timeframe for the signal that day.


