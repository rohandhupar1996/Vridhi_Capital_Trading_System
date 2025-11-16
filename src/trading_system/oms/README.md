# Order Management System (OMS)

Comprehensive Order Management System for BankNifty Options Trading with margin management, sequential lot reduction, and fast execution capabilities.

## Features

### Core Functionality
- **NRML Orders**: All orders use NRML product type (required for options)
- **MARKET Orders**: All orders are MARKET type for fast execution
- **BUY-First Sequence**: BUY orders execute first, then SELL orders to avoid margin issues
- **All-Leg Execution**: Exit and SL execute all legs together simultaneously
- **Position Tracking**: Complete position state management

### Margin Management
- **Pre-calculation**: Calculate margins before market opens for fast execution
- **Real-time Margin Check**: Verify margin availability before placing orders
- **Sequential Lot Reduction**: Automatically reduce lot size if margin issues occur
- **Partial Fill Handling**: Work with whatever is filled if full order can't be executed

### Fast Execution
- **Early Morning Ready**: Pre-calculate margins to enable instant execution at 9:15 AM
- **Fast Execution Mode**: Skip margin checks if margins were pre-calculated
- **Optimized Order Flow**: Minimal delays between order placement

## Strategy Details

### LONG Signal
1. **BUY** ATM CALL (CE) - Main leg
2. **BUY** 20 legs away PUT (PE) - Margin hedge
3. **SELL** ATM PUT (PE) - Short leg

### SHORT Signal
1. **BUY** ATM PUT (PE) - Main leg
2. **BUY** 20 legs away CALL (CE) - Margin hedge
3. **SELL** ATM CALL (CE) - Short leg

### Execution Sequence
1. All BUY orders placed first (main + hedge)
2. Wait for BUY orders to complete
3. Then place SELL orders
4. If any order fails, exit partial positions and retry with reduced lot size

## Configuration

Update `configs/config.yaml`:

```yaml
oms:
  lot_size: 8  # Number of BankNifty lots
  hedge_legs: 20  # 20 legs = 2000 points away
  order_type: "MARKET"
  product_type: "NRML"
  execution_sequence: "BUY_FIRST"
  allow_partial_sell: true
  fast_execution: true
  margin_check_before_trade: true
  sequential_lot_reduction: true
  exit_all_legs_together: true
```

## Usage

### Basic Initialization

```python
from src.trading_system.oms import OrderManager
from src.trading_system.broker import ZerodhaAuthenticator, ZerodhaCredentials

# Authenticate with Zerodha
credentials = ZerodhaCredentials(api_key="...", api_secret="...")
authenticator = ZerodhaAuthenticator(credentials=credentials)
authenticator.login()

kite = authenticator.get_kite_instance()

# Initialize OMS
oms = OrderManager(
    kite=kite,
    lot_size=8,
    hedge_legs=20
)
```

### Early Morning Setup (9:15 AM)

```python
# Get current futures price
futures_price = get_futures_price()  # Your data source

# Pre-calculate margins (takes 1-2 seconds)
oms.futures_ltp = futures_price
oms.pre_calculate_margins()

# Now ready for fast execution when signal arrives
```

### Handling Trading Signals

```python
# Update futures price
oms.futures_ltp = current_futures_price

# LONG signal
if signal == 'LONG':
    success = oms.enter_long(fast_execution=True)

# SHORT signal
elif signal == 'SHORT':
    success = oms.enter_short(fast_execution=True)

# EXIT signal
elif signal == 'EXIT':
    success = oms.exit_position()

# STOP LOSS signal
elif signal == 'SL':
    success = oms.execute_stop_loss()
```

### Handling Tick Data

```python
# Update futures price from tick data
def on_tick(tick):
    oms.update_futures_price(tick)
```

## Margin Management

### Pre-calculation
Pre-calculating margins before market opens enables instant execution when signals arrive:

```python
# Calculate margins for both LONG and SHORT
oms.pre_calculate_margins()

# Access pre-calculated margins
long_margin = oms._pre_calculated_margins['long']['total_margin']
short_margin = oms._pre_calculated_margins['short']['total_margin']
```

### Real-time Margin Check
Check margin availability before placing orders:

```python
margin_ok, required = oms.check_margin_availability('LONG', lot_size=8)
if margin_ok:
    # Proceed with order
    pass
```

### Sequential Lot Reduction
If margin issues occur, OMS automatically:
1. Tries with full lot size (8 lots)
2. If fails, reduces to half (4 lots)
3. Continues reducing until order succeeds or reaches 0
4. Works with whatever is filled (especially for SELL legs)

## Position Management

### Get Position Status
```python
status = oms.get_position_status()
# Returns:
# {
#     'position_type': 'LONG' | 'SHORT' | 'NONE',
#     'entry_time': '2024-01-01T09:15:00',
#     'lot_size': 8,
#     'atm_strike': 50000,
#     'hedge_strike': 48000,
#     'num_legs': 3
# }
```

### Exit All Positions
```python
# Exit all legs together (MARKET orders, NRML)
success = oms.exit_position()
```

### Stop Loss Execution
```python
# Execute stop loss (same as exit, all legs together)
success = oms.execute_stop_loss()
```

## Error Handling

### Margin Issues
- OMS automatically reduces lot size if margin issues occur
- Partial fills are handled gracefully
- Failed orders trigger position cleanup

### Order Failures
- If BUY orders fail: Exit any partial positions, retry with reduced lot size
- If SELL orders fail: Try with reduced lot size, or exit if can't fill
- All errors are logged with full context

## Logging

OMS uses component logging:

```python
from src.trading_system.logging import ComponentLogger

logger = ComponentLogger.get_logger("order_manager")
# All OMS operations are logged automatically
```

Logs include:
- Order placement and status
- Margin calculations
- Position entries and exits
- Error details with stack traces

## Production Considerations

### Fast Execution at 9:15 AM
1. **Pre-calculate margins** before market opens (can be done at 9:00 AM)
2. **Update futures price** as soon as market opens
3. **Use fast_execution=True** when entering positions
4. **Monitor margin availability** throughout the day

### Margin Management
- Margin requirements change with market volatility
- Pre-calculated margins are estimates (actual may vary)
- Always check available margin before large positions
- Monitor margin utilization throughout the day

### Order Execution
- MARKET orders execute immediately but price may vary
- Small delays (0.5-1 second) between orders prevent rate limiting
- All orders use NRML product type (required for options)
- Order status is checked after placement to confirm fills

### Risk Management
- Sequential lot reduction ensures partial fills are handled
- Failed orders trigger automatic cleanup
- Position state is tracked to prevent duplicate entries
- All operations are logged for audit trail

## API Reference

### OrderManager

#### Methods
- `enter_long(fast_execution=False) -> bool`: Enter LONG position
- `enter_short(fast_execution=False) -> bool`: Enter SHORT position
- `exit_position() -> bool`: Exit all positions
- `execute_stop_loss() -> bool`: Execute stop loss
- `pre_calculate_margins() -> bool`: Pre-calculate margins for fast execution
- `check_margin_availability(position_type, lot_size) -> Tuple[bool, float]`: Check margin
- `update_futures_price(tick) -> None`: Update futures price from tick
- `get_position_status() -> Dict`: Get current position status

### MarginCalculator

#### Methods
- `calculate_long_margin(atm_strike, hedge_strike, lot_size, futures_price) -> Dict`
- `calculate_short_margin(atm_strike, hedge_strike, lot_size, futures_price) -> Dict`
- `check_available_margin() -> float`: Get available margin from broker
- `pre_calculate_daily_margins(futures_price, lot_size) -> Dict`: Pre-calculate for the day

## Example Integration

See `example_usage.py` for complete integration example with:
- Zerodha authentication
- Early morning setup
- Signal handling
- Tick data processing

