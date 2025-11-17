"""
Live Trading Script
Runs the complete trading system with real-time WebSocket prices and live order execution

Features:
- WebSocket real-time price feed
- Live signal generation
- OMS order execution
- Running-candle signal handling (flicker, reversal)
- Dynamic timeframe (expiry day 5min switch)
- Earnings season filter
"""

from __future__ import annotations

import sys
import time
import signal
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
import os

from src.trading_system.config import AppConfig
from src.trading_system.logging import ComponentLogger, setup_logging
from src.trading_system.broker.zerodha_auth import ZerodhaAuthenticator, ZerodhaCredentials
from src.trading_system.oms.order_manager import OrderManager
from src.trading_system.oms.websocket_price_feed import WebSocketPriceFeed
from src.trading_system.oms.running_signal_executor import RunningSignalExecutor
from src.trading_system.oms.dynamic_timeframe import DynamicTimeframeController, DynamicTimeframeConfig
from src.trading_system.oms.earnings_filter import EarningsSeasonFilter, EarningsFilterConfig

# Global variables for graceful shutdown
running = True
price_feed = None
executor = None


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    global running, price_feed, executor
    print("\n\n⚠️  Shutdown signal received. Stopping trading system...")
    running = False
    
    if executor:
        executor.stop()
    
    if price_feed:
        price_feed.stop()
    
    print("✅ Trading system stopped gracefully")
    sys.exit(0)


def main():
    """Main live trading function"""
    global running, price_feed, executor
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Setup logging
    setup_logging("logs")
    main_logger = ComponentLogger.get_logger("live_trading")
    
    print("\n" + "="*70)
    print("LIVE TRADING SYSTEM")
    print("="*70 + "\n")
    
    # Load configuration
    app_config = AppConfig()
    
    # Load credentials
    env_path = PROJECT_ROOT / "configs" / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        main_logger.info(f"Loaded credentials from {env_path}")
    else:
        print(f"❌ Config file not found: {env_path}")
        return False
    
    api_key = os.getenv("ZERODHA_API_KEY")
    api_secret = os.getenv("ZERODHA_API_SECRET")
    
    if not api_key or not api_secret:
        print("❌ ZERODHA_API_KEY or ZERODHA_API_SECRET not found")
        return False
    
    # Authenticate
    print("📡 Authenticating with Zerodha...")
    credentials = ZerodhaCredentials(api_key=api_key, api_secret=api_secret)
    authenticator = ZerodhaAuthenticator(
        credentials=credentials,
        token_file="configs/zerodha_tokens.json",
        logger=ComponentLogger.get_logger("zerodha_auth")
    )
    
    if not authenticator.login(auto_open_browser=False):
        print("❌ Authentication failed. Please run: python scripts/zerodha_login.py")
        return False
    
    kite = authenticator.get_kite_instance()
    if not kite:
        print("❌ Failed to get Kite instance")
        return False
    
    profile = kite.profile()
    print(f"✅ Authenticated as: {profile.get('user_name', 'N/A')} ({profile.get('user_id', 'N/A')})")
    
    # Initialize OMS
    print("\n📦 Initializing Order Management System...")
    oms_config = app_config.oms if hasattr(app_config, 'oms') else {}
    lot_size = oms_config.get('lot_size', 8)
    
    oms_logger = ComponentLogger.get_logger("order_manager")
    oms = OrderManager(
        kite=kite,
        lot_size=lot_size,
        hedge_legs=oms_config.get('hedge_legs', 20),
        logger=oms_logger,
        dry_run=False  # REAL trading - set to True for testing
    )
    
    print(f"✅ OMS initialized | lot_size={lot_size}")
    
    # Get futures token
    futures_token = oms._get_futures_token()
    if not futures_token:
        print("❌ Failed to get futures token")
        return False
    
    print(f"✅ Futures token: {futures_token}")
    
    # Initialize WebSocket price feed
    print("\n📡 Starting WebSocket price feed...")
    price_feed = WebSocketPriceFeed(
        kite=kite,
        futures_token=futures_token,
        order_manager=oms,
        logger=ComponentLogger.get_logger("websocket_price_feed")
    )
    
    if not price_feed.start():
        print("❌ Failed to start WebSocket price feed")
        return False
    
    print("✅ WebSocket connected - waiting for price updates...")
    
    # Wait for initial price
    print("⏳ Waiting for initial price update...")
    for i in range(10):
        if oms.futures_ltp and oms.futures_ltp > 0:
            print(f"✅ Initial price received: {oms.futures_ltp}")
            break
        time.sleep(1)
    else:
        print("⚠️  No initial price received, but continuing...")
    
    # Initialize dynamic timeframe controller
    print("\n⏰ Initializing dynamic timeframe controller...")
    timeframe_config = DynamicTimeframeConfig(
        base_timeframe="15min",
        expiry_day_timeframe="5min",
        enable_expiry_switch=True
    )
    timeframe_controller = DynamicTimeframeController(timeframe_config)
    
    # Initialize earnings filter
    print("🏦 Initializing earnings season filter...")
    earnings_config = EarningsFilterConfig(
        use_filter=app_config.earnings_filter.get('use_filter', True) if hasattr(app_config, 'earnings_filter') else True,
        block_first_days_blue=app_config.earnings_filter.get('block_first_days_blue', 15) if hasattr(app_config, 'earnings_filter') else 15,
        block_after_yellow=app_config.earnings_filter.get('block_after_yellow', 15) if hasattr(app_config, 'earnings_filter') else 15
    )
    earnings_filter = EarningsSeasonFilter(earnings_config)
    
    # Initialize running signal executor
    print("\n🎯 Initializing signal executor...")
    executor = RunningSignalExecutor(
        oms=oms,
        earnings_filter=earnings_filter,
        logger=ComponentLogger.get_logger("running_signal_executor")
    )
    
    print("✅ Signal executor initialized")
    
    # Pre-calculate margins for the day (optional, for faster execution)
    print("\n💰 Pre-calculating margins...")
    if oms.futures_ltp and oms.futures_ltp > 0:
        oms.pre_calculate_margins()
        print("✅ Margins pre-calculated (margin check still enabled for safety)")
    else:
        print("⚠️  No futures price yet - margins will be calculated on first signal")
    
    # Main trading loop
    print("\n" + "="*70)
    print("🚀 LIVE TRADING STARTED")
    print("="*70)
    print("\n⚠️  Press Ctrl+C to stop trading system gracefully\n")
    
    try:
        # TODO: Add live signal generation from real-time data
        # For now, this is a framework that needs signal generation integration
        # You'll need to integrate your signal generation logic here
        
        print("📊 Waiting for signals...")
        print("   (Signal generation integration needed)")
        
        # Keep running until interrupted
        while running:
            # Check if WebSocket is still connected
            if hasattr(price_feed, 'is_connected') and not price_feed.is_connected:
                print("⚠️  WebSocket disconnected. Attempting to reconnect...")
                price_feed.start()
            
            # Monitor price updates
            if oms.futures_ltp and oms.futures_ltp > 0:
                # Price is updating via WebSocket
                pass
            
            # TODO: Add your signal generation logic here
            # Example:
            # - Get latest OHLCV data
            # - Generate signals using your ML model
            # - Call executor.handle_signal() when signal appears
            
            time.sleep(1)  # Small delay to avoid CPU spinning
            
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error in trading loop: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        print("\n🛑 Stopping trading system...")
        if executor:
            executor.stop()
        if price_feed:
            price_feed.stop()
        print("✅ Trading system stopped")
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

