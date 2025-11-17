"""
Simple Live Trading Script
Clean version without agents - just Zerodha login and trading system

Features:
- Zerodha authentication
- WebSocket real-time price feed
- ML model signal generation
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
from src.trading_system.data.historical_loader import HistoricalDataLoader
from src.strategy.core.trading_system import LorentzianTradingSystem
from src.strategy.backtest.config import TradingSettings

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
    
    # Setup minimal logging
    setup_logging("logs")
    main_logger = ComponentLogger.get_logger("simple_trading")
    
    print("\n" + "="*70)
    print("SIMPLE LIVE TRADING SYSTEM")
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
    
    # Load historical data for ML model
    print("\n📊 Loading historical data for ML model...")
    db_path = app_config.resolve_path(app_config.data.db_path) if hasattr(app_config, 'data') else PROJECT_ROOT / "data" / "banknifty_data.db"
    data_loader = HistoricalDataLoader(
        db_path=db_path,
        symbol="BANKNIFTY1!",
        timeframe="15min",
        lookback_bars=2000,
        logger=ComponentLogger.get_logger("data_loader")
    )
    
    historical_data = None
    if data_loader.load():
        historical_data = data_loader.get_data()
        print(f"✅ Historical data loaded: {len(historical_data)} bars")
    else:
        print("⚠️  Failed to load historical data - ML model will not work")
    
    # Initialize ML model
    print("\n🤖 Initializing ML model...")
    ml_settings = TradingSettings(
        neighbors_count=8,
        max_bars_back=2000,
        feature_count=5,
        use_kernel_filter=True,
        kernel_lookback=8,
        kernel_relative_weight=8.0,
        use_volatility_filter=True,
        use_regime_filter=True,
        regime_threshold=-0.1,
        enable_reentry=True,
        reentry_window_start=1,
        reentry_window_end=8
    )
    ml_model = LorentzianTradingSystem(ml_settings)
    print("✅ ML model initialized")
    
    # Initialize dynamic timeframe controller
    print("\n⏰ Initializing dynamic timeframe controller...")
    timeframe_config = DynamicTimeframeConfig(
        base_timeframe="15min",
        expiry_day_timeframe="5min",
        enable_expiry_switch=True
    )
    timeframe_controller = DynamicTimeframeController(
        config=timeframe_config,
        kite=kite
    )
    
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
    
    last_signal_time = None
    last_candle_id = None
    
    try:
        while running:
            # Check if WebSocket is still connected
            if hasattr(price_feed, 'is_connected') and not price_feed.is_connected:
                print("⚠️  WebSocket disconnected. Attempting to reconnect...")
                price_feed.start()
            
            # Get current price
            current_price = oms.futures_ltp
            if not current_price or current_price <= 0:
                time.sleep(1)
                continue
            
            # Get effective timeframe
            effective_tf = timeframe_controller.get_effective_timeframe(datetime.now())
            current_time = datetime.now()
            
            # Generate candle_id (simplified - using 15min/5min buckets)
            if effective_tf == "5min":
                minute_bucket = (current_time.minute // 5) * 5
            else:
                minute_bucket = (current_time.minute // 15) * 15
            
            candle_id = f"{current_time.strftime('%Y%m%d_%H%M')}{minute_bucket:02d}_{effective_tf}"
            
            # Check if this is a new candle
            is_new_candle = candle_id != last_candle_id
            if is_new_candle and last_candle_id:
                # Candle closed - reconcile
                executor.on_candle_close("NONE", last_candle_id, current_price)
            
            if is_new_candle:
                executor.start_new_candle(candle_id, current_time)
                last_candle_id = candle_id
            
            # Generate signal using ML model (every second, but only process if we have historical data)
            if historical_data is not None:
                try:
                    # Prepare data: append current price to historical data
                    import pandas as pd
                    import pytz
                    
                    current_time_ts = pd.Timestamp(current_time.replace(tzinfo=pytz.timezone('Asia/Kolkata')))
                    new_row = pd.DataFrame({
                        'timestamp': [current_time_ts],
                        'open': [current_price],
                        'high': [current_price],
                        'low': [current_price],
                        'close': [current_price],
                        'volume': [0]
                    })
                    
                    # Combine historical + current
                    combined_data = pd.concat([historical_data, new_row], ignore_index=True)
                    
                    # Keep only last 2000 bars (sliding window)
                    if len(combined_data) > 2000:
                        combined_data = combined_data.tail(2000).reset_index(drop=True)
                    
                    # Generate signals
                    high = combined_data['high'].values
                    low = combined_data['low'].values
                    close = combined_data['close'].values
                    
                    results = ml_model.generate_signals(high, low, close, start_bar=100)
                    
                    # Get last bar signal
                    last_idx = len(results['start_long']) - 1
                    
                    # Check for exit signals first
                    ml_signal = "NONE"
                    if results['end_long'][last_idx]:
                        ml_signal = "EXIT_LONG"
                    elif results['end_short'][last_idx]:
                        ml_signal = "EXIT_SHORT"
                    elif results['start_long'][last_idx]:
                        ml_signal = "LONG"
                    elif results['start_short'][last_idx]:
                        ml_signal = "SHORT"
                    
                    # Process signal
                    if ml_signal != "NONE":
                        executor.on_running_signal(ml_signal, candle_id, current_price)
                        main_logger.info(
                            f"Signal: {ml_signal} | Price: {current_price:.2f} | Candle: {candle_id}"
                        )
                    
                    # Update historical data (sliding window)
                    historical_data = combined_data
                    
                except Exception as e:
                    main_logger.warning(f"Error generating signal: {e}")
            
            time.sleep(1)  # Check every second
            
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

