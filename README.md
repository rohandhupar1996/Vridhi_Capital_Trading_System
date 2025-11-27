# BankNifty Trading System

Modular trading system for BankNifty options with TradingView webhook integration and OpenAlgo execution.

## Structure

```
Vridhi_Capital_Trading_System/
├── app.py                      # Main application entry point
├── config.py                   # Configuration settings
├── requirements.txt
├── README.md
└── src/
    ├── openalgo_client.py      # OpenAlgo API wrapper
    ├── order_manager.py        # Order placement & verification
    ├── position_executor.py    # Position execution logic
    ├── telegram_notifier.py    # Telegram notifications
    └── webhook_handler.py      # Flask webhook endpoints
```

## Features

✅ **Parallel BUY Execution** - BUY orders execute simultaneously  
✅ **Sequential SELL Execution** - SELL only after BUY confirmation  
✅ **Order Verification** - Polls until order completion  
✅ **TradingView Integration** - Webhook endpoint for alerts  
✅ **OpenAlgo Integration** - Broker-agnostic execution  
✅ **Safety Checks** - Prevents naked SELL positions  
✅ **Telegram Alerts** - Real-time notifications for signals, executions, and P&L  

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Edit `config.py`:

```python
# OpenAlgo Configuration
OPENALGO_CONFIG = {
    "api_key": "your_api_key_here",  # ⚠️ CHANGE THIS
    "host": "http://127.0.0.1:5000"
}

# Telegram Configuration
TELEGRAM_CONFIG = {
    "enabled": True,  # Set to False to disable
    "username": "your_openalgo_username",  # ⚠️ CHANGE THIS
    "send_signal_alerts": True,
    "send_execution_alerts": True,
    "send_pnl_updates": True,
    "pnl_update_interval": 3600,  # 1 hour
    "market_hours_only": True,  # 9:15 AM - 3:30 PM
}

# Trading Configuration
CONFIG = {
    "underlying": "BANKNIFTY",
    "lot_size": 15,
    "product": "NRML",
    "strategy_name": "ML_BANKNIFTY",
}
```

## Usage

### Start Server

```bash
python app.py
```

Server runs on `http://0.0.0.0:5001`

### Endpoints

**TradingView Webhook:**
```
POST /webhook
Body: {"signal": "LONG" | "SHORT" | "EXIT" | "NONE"}
```

**Health Check:**
```
GET /health
```

**Get Positions:**
```
GET /positions
```

**Close All Positions:**
```
POST /close
```

**Get P&L (sends to Telegram):**
```
GET /pnl
```

**Test Execution:**
```
POST /test/long
POST /test/short
```

## TradingView Setup

1. Create alert in TradingView
2. Set webhook URL: `http://your-server:5001/webhook`
3. Set message:
```json
{"signal": "{{strategy.order.action}}"}
```

Replace `{{strategy.order.action}}` with:
- `LONG` - Enter long position
- `SHORT` - Enter short position
- `EXIT` - Close all positions

## Position Logic

### LONG Position
1. BUY ATM CE (parallel)
2. BUY OTM20 PE (parallel)
3. Wait for both BUYs to complete
4. SELL ATM PE (sequential)

### SHORT Position
1. BUY ATM PE (parallel)
2. BUY OTM20 CE (parallel)
3. Wait for both BUYs to complete
4. SELL ATM CE (sequential)

**Execution Time:** ~3-5 seconds

## Safety Features

- ✅ BUY orders execute first (parallel)
- ✅ SELL only after BUY confirmation
- ✅ Order status polling until completion
- ✅ Prevents naked SELL positions
- ✅ Comprehensive error logging

## Telegram Alerts

### Signal Alerts
```
🟢 LONG Signal Received!
📅 Expiry: 30-DEC-25
```

### Execution Success
```
🎯 LONG Position COMPLETE!
━━━━━━━━━━━━━━━━━━
⏱ Execution: 4.23s
📅 Expiry: 30-DEC-25

📥 BUY Orders:
  • BANKNIFTY30DEC2551000CE
  • BANKNIFTY30DEC2550000PE

📤 SELL Order:
  • BANKNIFTY30DEC2551000PE

💰 Check /pnl for P&L
```

### P&L Updates (Hourly during market hours)
```
📊 Current Positions P&L
━━━━━━━━━━━━━━━━━━
🟢 BANKNIFTY30DEC2551000CE: ₹+350.00
🔴 BANKNIFTY30DEC2550000PE: ₹-120.00
🟢 BANKNIFTY30DEC2551000PE: ₹+280.00
━━━━━━━━━━━━━━━━━━
💚 Total P&L: ₹+510.00
🕐 02:30 PM
```

## License

MIT
