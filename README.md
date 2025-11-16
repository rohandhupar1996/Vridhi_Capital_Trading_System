# Vridhi Capital Trading System

Comprehensive trading system for BankNifty options with ML-based signal generation and automated order management.

## Components

### 1. Order Management System (OMS)
**Location**: `src/trading_system/oms/`

Complete order management system for BankNifty options trading with:
- **NRML Market Orders**: All orders use NRML product type with MARKET execution
- **BUY-First Sequence**: BUY orders execute first, then SELL orders to prevent margin issues
- **Margin Management**: Pre-calculation and real-time margin checking
- **Sequential Lot Reduction**: Automatically reduces lot size if margin issues occur
- **Fast Execution**: Pre-calculated margins enable instant execution at 9:15 AM
- **All-Leg Execution**: Exit and SL execute all legs together simultaneously

**Strategy**:
- **LONG**: SELL ATM PUT (PE) + BUY ATM CALL (CE) + BUY 20 legs away PUT (PE) for margin
- **SHORT**: SELL ATM CALL (CE) + BUY ATM PUT (PE) + BUY 20 legs away CALL (CE) for margin

**Key Features**:
- 8 lots of BankNifty (configurable)
- 20 legs away hedge for margin requirements
- Handles partial fills gracefully
- Complete position tracking and state management

See `src/trading_system/oms/README.md` for detailed documentation.

### 2. Trading Strategy
**Location**: `src/strategy/core/`

ML-based trading system using Lorentzian Classification with:
- Dual timeframe analysis
- Kernel filtering
- Volume node detection
- Re-entry logic

### 3. Broker Integration
**Location**: `src/trading_system/broker/`

Zerodha KiteConnect integration with:
- Automated authentication
- Connection monitoring
- Token management
- Health checks

## Quick Start

### Setup
1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure credentials in `configs/.env`:
```
ZERODHA_API_KEY=your_api_key
ZERODHA_API_SECRET=your_api_secret
```

3. Update `configs/config.yaml` with your trading parameters

### Using OMS

```python
from src.trading_system.oms import OrderManager
from src.trading_system.broker import ZerodhaAuthenticator, ZerodhaCredentials

# Authenticate
credentials = ZerodhaCredentials(api_key="...", api_secret="...")
authenticator = ZerodhaAuthenticator(credentials=credentials)
authenticator.login()

# Initialize OMS
oms = OrderManager(
    kite=authenticator.get_kite_instance(),
    lot_size=8,
    hedge_legs=20
)

# Pre-calculate margins (before market opens)
oms.futures_ltp = get_futures_price()
oms.pre_calculate_margins()

# Handle signals
if signal == 'LONG':
    oms.enter_long(fast_execution=True)
elif signal == 'SHORT':
    oms.enter_short(fast_execution=True)
elif signal == 'EXIT':
    oms.exit_position()
elif signal == 'SL':
    oms.execute_stop_loss()
```

See `src/trading_system/oms/example_usage.py` for complete integration example.

## Configuration

Edit `configs/config.yaml` to customize:
- Lot size (default: 8)
- Hedge legs (default: 20)
- Order execution settings
- Margin management options

## Documentation

- **OMS Documentation**: `src/trading_system/oms/README.md`
- **Zerodha Integration**: `docs/ZERODHA_INTEGRATION.md`
- **Example Usage**: `src/trading_system/oms/example_usage.py`

## Features

✅ NRML Market Orders  
✅ BUY-first execution sequence  
✅ Margin calculation and management  
✅ Sequential lot reduction on margin issues  
✅ Fast execution for early morning signals  
✅ All-leg exit and SL execution  
✅ Complete position tracking  
✅ Comprehensive logging  
✅ Error handling and recovery  

## Production Notes

- Pre-calculate margins before market opens for fastest execution
- Monitor margin availability throughout the day
- All orders use NRML product type (required for options)
- Partial fills are handled gracefully
- Complete audit trail via logging
