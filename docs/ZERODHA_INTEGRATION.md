# Zerodha Integration Guide

## Overview

The trading system now includes automated Zerodha authentication, connection monitoring, and comprehensive logging.

## Features

1. **Automated Login**: Handles Zerodha login flow with request token management
2. **Connection Monitoring**: Checks WiFi, Zerodha API, and trading system health
3. **Auto-Reconnect**: Automatically reconnects when connection drops
4. **Component Logging**: Tracks ML, filters, kernel, and trading system operations
5. **Daily Log Rotation**: Maintains 30-90 days of logs with automatic rotation

## Setup

### 1. Install Dependencies

```bash
pip install kiteconnect requests python-dotenv
```

### 2. Configure Credentials

Add your Zerodha API credentials to `configs/.env`:

```env
ZERODHA_API_KEY=your_api_key
ZERODHA_API_SECRET=your_api_secret
ZERODHA_REQUEST_TOKEN=your_request_token  # Optional, for auto-reconnect
```

### 3. Run Login Script

```bash
python scripts/zerodha_login.py
```

The script will:
- Check connection health (WiFi, Zerodha API)
- Open browser for login (if needed)
- Save access token for future use
- Setup connection monitoring

## Usage

### Basic Authentication

```python
from src.trading_system.broker import ZerodhaAuthenticator, ZerodhaCredentials
from src.trading_system.logging import ComponentLogger

credentials = ZerodhaCredentials(
    api_key="your_api_key",
    api_secret="your_api_secret"
)

authenticator = ZerodhaAuthenticator(
    credentials=credentials,
    token_file="configs/zerodha_tokens.json",
    logger=ComponentLogger.get_logger("zerodha_auth")
)

# Login
if authenticator.login():
    kite = authenticator.get_kite_instance()
    # Use kite for trading operations
```

### Connection Monitoring

```python
from src.trading_system.broker import ConnectionMonitor

monitor = ConnectionMonitor(
    authenticator=authenticator,
    check_interval=30  # seconds
)

# Check connection health
if monitor.check_and_reconnect():
    print("Connection healthy")
else:
    print("Connection issue detected")
```

### Component Logging

```python
from src.trading_system.logging import ComponentLogger

# Get component-specific logger
ml_logger = ComponentLogger.get_logger("ml_extension")
kernel_logger = ComponentLogger.get_logger("kernel_function")
trading_logger = ComponentLogger.get_logger("trading_system")

# Log operations
ml_logger.log_ml_operation("feature_generation", duration_ms=500.0)
kernel_logger.log_kernel_operation("rational_quadratic", duration_ms=200.0)
trading_logger.log_trade_signal("LONG", bar=100, price=50000.0)
```

## Log Files

All logs are stored in the `logs/` directory:

- `ml_extension.log` - ML operations and timing
- `kernel_function.log` - Kernel calculations
- `lorentzian_classifier.log` - Classification operations
- `trading_system.log` - Trading system events
- `backtest_engine.log` - Backtest operations
- `zerodha_auth.log` - Authentication events
- `connection_monitor.log` - Connection health checks
- `errors.log` - All error messages (all components)
- `authentication.log` - Login/authentication events

Logs rotate daily at midnight and are kept for:
- Component logs: 30 days
- Authentication logs: 90 days

## Connection Health Checks

The system monitors:

1. **WiFi/Internet**: Checks connectivity to Google
2. **Zerodha API**: Verifies Zerodha API is reachable
3. **Trading System**: Checks if trading system is running
4. **Token Validity**: Verifies access token is still valid

## Auto-Reconnect Flow

1. Connection monitor detects disconnection
2. Checks connection health (WiFi, API)
3. Attempts to use existing access token
4. If token invalid, uses request token (if available)
5. If no valid token, prompts for new login

## Error Handling

All errors are logged with:
- Timestamp
- Component name
- Error message
- Stack trace (for exceptions)

Check `logs/errors.log` for all system errors.

## Next Steps

The authentication system is ready. You can now:
1. Integrate it into your trading system
2. Add more components to the logging system
3. Customize connection check intervals
4. Add additional health checks


