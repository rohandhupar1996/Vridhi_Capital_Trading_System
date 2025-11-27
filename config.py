"""
Trading System Configuration
"""

# Trading Configuration
CONFIG = {
    "underlying": "BANKNIFTY",
    "exchange": "NSE_INDEX",
    "lot_size": 30,              # BankNifty lot size
    "product": "NRML",           # NRML for overnight, MIS for intraday
    "strategy_name": "ML_BANKNIFTY",
    "max_order_wait": 10,        # seconds to wait for order completion
    "order_poll_interval": 0.3,  # seconds between status checks
}

# OpenAlgo Configuration
OPENALGO_CONFIG = {
    "api_key": "509ef6284b57bc2a35670dbc904be5324cea3af2d131ba3be53e435270b993b5",  # ⚠️ CHANGE THIS
    "host": "http://127.0.0.1:5000"
}

# Telegram Configuration
TELEGRAM_CONFIG = {
    "enabled": True,  # Set to False to disable Telegram alerts
    "username": "rohandhupar18@gmail.com",  # ⚠️ CHANGE THIS to your OpenAlgo login username
    "send_signal_alerts": True,  # Alert when LONG/SHORT signal received
    "send_execution_alerts": True,  # Alert when position executed
    "send_pnl_updates": True,  # Send periodic P&L updates
    "pnl_update_interval": 3600,  # Seconds between P&L updates (3600 = 1 hour)
    "market_hours_only": True,  # Only send P&L during market hours (9:15 AM - 3:30 PM)
}

# Server Configuration
SERVER_CONFIG = {
    "host": "0.0.0.0",
    "port": 5001,
    "debug": False
}

