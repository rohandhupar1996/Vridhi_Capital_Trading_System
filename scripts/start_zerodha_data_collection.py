#!/usr/bin/env python3
"""
Start Zerodha Data Collection Script
Initializes ohlcv_zerodha table and starts collecting BankNifty futures data
from Zerodha WebSocket into 5min, 15min, 1hr candles.

This script:
1. Creates/initializes ohlcv_zerodha table in the same DB as TradingView data
2. Fetches current month BankNifty futures symbol from Zerodha dynamically
3. Connects to Zerodha WebSocket for tick data
4. Aggregates ticks into candles and stores in ohlcv_zerodha table
5. Maintains continuous data stream across contract changes
"""

import sys
import signal
import time
from pathlib import Path
from datetime import datetime

import pytz

# Ensure project root and src/ directory are on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_PATH):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import os
from dotenv import load_dotenv

from src.trading_system.config import AppConfig
from src.trading_system.logging import setup_logging, ComponentLogger
from src.trading_system.broker.zerodha_auth import ZerodhaAuthenticator, ZerodhaCredentials, ConnectionStatus
from src.trading_system.data.zerodha_candle_aggregator import ZerodhaCandleAggregator
from src.trading_system.data.zerodha_futures_utils import get_current_month_futures_symbol_and_token
from src.trading_system.oms.websocket_price_feed import WebSocketPriceFeed

KOLKATA_TZ = pytz.timezone("Asia/Kolkata")

# Global variables for cleanup
aggregator = None
websocket_feed = None
zerodha_auth = None
shutdown_event = False


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_event
    print("\n\n🛑 Shutdown signal received. Closing connections...")
    shutdown_event = True


def on_tick_received(tick_data: dict, tick_logger: ComponentLogger):
    """Callback for receiving tick data from WebSocket"""
    global aggregator
    
    try:
        # Extract tick information
        instrument_token = tick_data.get('instrument_token')
        ltp = tick_data.get('last_price')  # Last Traded Price
        volume = tick_data.get('volume', 0) if 'volume' in tick_data else 0
        
        if ltp is None:
            return
        
        # Current timestamp
        tick_time = datetime.now(KOLKATA_TZ)
        
        # Feed tick to aggregator
        completed_candles = aggregator.on_tick(
            price=ltp,
            volume=volume,
            timestamp=tick_time
        )
        
        # Log when candles complete
        for timeframe, candle in completed_candles.items():
            if candle is not None:
                tick_logger.info(
                    f"Completed {timeframe} candle",
                    timestamp=candle.timestamp.isoformat(),
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume
                )
                
    except Exception as e:
        tick_logger.error(f"Error processing tick: {e}", exc_info=True)


def main():
    """Main entry point"""
    global aggregator, websocket_feed, zerodha_auth, shutdown_event
    
    print("=" * 70)
    print("🚀 ZERODHA BANKNIFTY FUTURES DATA COLLECTION")
    print("=" * 70)
    print()
    
    # Setup logging
    setup_logging(log_dir=PROJECT_ROOT / "logs")
    logger = ComponentLogger.get_logger("zerodha_data_collection")
    
    # Load configuration
    app_config = AppConfig()
    data_config = app_config.data
    
    print(f"📁 Database: {app_config.resolve_path(data_config.db_path)}")
    print()
    
    # Load Zerodha credentials from .env
    env_path = PROJECT_ROOT / "configs" / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"Loaded credentials from {env_path}")
    else:
        print(f"❌ Config file not found: {env_path}")
        return 1
    
    api_key = os.getenv("ZERODHA_API_KEY")
    api_secret = os.getenv("ZERODHA_API_SECRET")
    
    if not api_key or not api_secret:
        print("❌ ZERODHA_API_KEY or ZERODHA_API_SECRET not found in configs/.env")
        return 1
    
    # Authenticate with Zerodha
    print("🔐 Authenticating with Zerodha...")
    credentials = ZerodhaCredentials(api_key=api_key, api_secret=api_secret)
    token_file_path = PROJECT_ROOT / "configs" / "zerodha_tokens.json"
    zerodha_auth = ZerodhaAuthenticator(
        credentials=credentials,
        token_file=str(token_file_path),
        logger=logger
    )
    
    # Try to login (will use saved token if valid, otherwise prompt)
    if not zerodha_auth.login(auto_open_browser=False):
        print("❌ Authentication failed. Please authenticate first.")
        print("   Run: python scripts/zerodha_login.py")
        return 1
    
    if zerodha_auth.connection_status != ConnectionStatus.CONNECTED:
        print("❌ Not authenticated. Please authenticate first.")
        print("   Run: python scripts/zerodha_login.py")
        return 1
    
    kite = zerodha_auth.get_kite_instance()
    if not kite:
        print("❌ Failed to get KiteConnect instance")
        return 1
    
    profile = kite.profile()
    print(f"✅ Authenticated as: {profile.get('user_name', 'N/A')} ({profile.get('user_id', 'N/A')})")
    print()
    
    # Fetch current month futures symbol and token
    print("📊 Fetching current month BankNifty futures contract...")
    try:
        futures_symbol, futures_token = get_current_month_futures_symbol_and_token(kite)
        
        if not futures_symbol or not futures_token:
            print("❌ Failed to fetch current month futures contract from Zerodha")
            logger.error("No futures contract found - check if market is open or contracts are available")
            return 1
    except Exception as e:
        print(f"❌ Error fetching futures contract: {e}")
        logger.error(f"Error fetching futures contract: {e}", exc_info=True)
        return 1
    
    print(f"✅ Found: {futures_symbol} (Token: {futures_token})")
    print()
    
    # Initialize candle aggregator (fetches symbol dynamically or uses fetched one)
    print("📈 Initializing candle aggregator...")
    try:
        aggregator = ZerodhaCandleAggregator(
            config=data_config,
            kite=kite,  # Will use this to fetch symbol dynamically
            symbol=futures_symbol,  # Use the fetched symbol
            logger=logger
        )
        
        # Initialize all managers (loads historical data if available)
        if not aggregator.initialize():
            print("❌ Failed to initialize candle aggregator")
            return 1
        
        print("✅ Candle aggregator initialized")
        print(f"   Symbol: {aggregator.symbol}")
        print(f"   Table: ohlcv_zerodha")
        print(f"   Timeframes: 5min, 15min, 1hour")
        print()
        
    except Exception as e:
        print(f"❌ Error initializing aggregator: {e}")
        logger.error(f"Error initializing aggregator: {e}", exc_info=True)
        return 1
    
    # Create a minimal order manager mock for WebSocket
    class MockOrderManager:
        """Mock order manager for WebSocket price feed"""
        def __init__(self, tick_callback, tick_logger):
            self.tick_callback = tick_callback
            self.tick_logger = tick_logger
            self.futures_ltp = None
            self.futures_token = futures_token
        
        def update_futures_price(self, tick_data: dict):
            """Update futures price from tick data"""
            if tick_data.get('instrument_token') == self.futures_token:
                self.futures_ltp = tick_data.get('last_price')
                # Call the tick callback
                self.tick_callback(tick_data, self.tick_logger)
    
    mock_oms = MockOrderManager(on_tick_received, logger)
    
    # Initialize WebSocket price feed
    print("🔌 Starting WebSocket connection...")
    try:
        websocket_feed = WebSocketPriceFeed(
            kite=kite,
            futures_token=futures_token,
            order_manager=mock_oms,
            logger=logger
        )
        
        if not websocket_feed.start():
            print("❌ Failed to start WebSocket connection")
            return 1
        
        print("✅ WebSocket connected")
        print()
        
    except Exception as e:
        print(f"❌ Error starting WebSocket: {e}")
        logger.error(f"Error starting WebSocket: {e}", exc_info=True)
        return 1
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("=" * 70)
    print("✅ DATA COLLECTION STARTED")
    print("=" * 70)
    print(f"📊 Collecting data for: {futures_symbol}")
    print(f"💾 Storing in: ohlcv_zerodha table")
    print(f"⏱️  Timeframes: 5min, 15min, 1hour")
    print()
    print("Press Ctrl+C to stop...")
    print()
    
    # Main loop - wait for ticks
    try:
        while not shutdown_event:
            time.sleep(1)
            
            # Check if WebSocket is still connected
            if websocket_feed and not websocket_feed.is_connected:
                logger.warning("WebSocket disconnected. Attempting to reconnect...")
                # Could implement reconnection logic here
                break
            
    except KeyboardInterrupt:
        shutdown_event = True
    except Exception as e:
        logger.error(f"Error in main loop: {e}", exc_info=True)
    
    # Cleanup
    print("\n🛑 Shutting down...")
    
    if websocket_feed:
        websocket_feed.stop()
        print("✅ WebSocket closed")
    
    if aggregator:
        aggregator.close()
        print("✅ Candle aggregator closed")
    
    print()
    print("=" * 70)
    print("✨ SHUTDOWN COMPLETE")
    print("=" * 70)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

