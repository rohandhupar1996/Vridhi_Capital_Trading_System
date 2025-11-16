# Earnings Season Filter

Blocks new entries during specific periods around earnings seasons to avoid excitement/fear phases.

## Logic
- Earnings months (YELLOW): Jan, Apr, Jul, Oct
- 60D before (BLUE): Feb, May, Aug, Nov
- 45D before (GREEN): Mar, Jun, Sep, Dec

Blocked:
- First N days of BLUE months (default N=15)
- N days after YELLOW ends → also first N days of the following BLUE month

This matches the provided Pine logic.

## Configuration (`configs/config.yaml`)
```yaml
earnings_filter:
  use_filter: true
  block_first_days_blue: 15
  block_after_yellow: 15
```

## API
```python
from src.trading_system.oms.earnings_filter import EarningsSeasonFilter, EarningsFilterConfig

flt = EarningsSeasonFilter(EarningsFilterConfig(
    use_filter=True,
    block_first_days_blue=15,
    block_after_yellow=15,
))

if flt.is_blocked():
    # Skip new entries
    pass
```

## Integration
- Already wired into `RunningSignalExecutor`: blocks `enter_long/enter_short` when filter is active.
- You can inject a custom filter or disable via config.


