"""
LIVE ZERODHA API TESTING SCRIPT
Tests all components with REAL Zerodha API in DRY-RUN mode using 1 LOT

Testing Phases:
1. Authentication & Connection
2. Futures & Option Chain
3. Margin Calculation (Real API)
4. LONG Entry (1 Lot, Dry Run)
5. SHORT Entry (1 Lot, Dry Run)
6. Exit Position (1 Lot, Dry Run)
7. WebSocket Price Feed
8. Integration Test - Complete Flow

Safety:
- Dry Run Mode: dry_run=True (no real orders)
- Lot Size: 1 lot only (for safety)
- Margin Check: Verify available margin before entry
- Error Handling: Graceful failure with detailed messages
- Logging: All operations logged for audit trail
"""

from __future__ import annotations

import sys
import time
import signal
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import os
from dotenv import load_dotenv

from src.trading_system.config import AppConfig
from src.trading_system.logging import setup_logging, ComponentLogger
from src.trading_system.broker import ZerodhaAuthenticator
from src.trading_system.broker.zerodha_auth import ZerodhaCredentials
from src.trading_system.broker.oauth_callback_server import OAuthCallbackServer
from src.trading_system.data.zerodha_futures_utils import (
    get_current_month_futures_symbol_and_token,
    get_monthly_expiry_from_option_chain
)
from src.trading_system.oms.option_chain_manager import OptionChainManager
from src.trading_system.oms.margin_calculator import MarginCalculator
from src.trading_system.oms.order_manager import OrderManager, PositionType
from src.trading_system.oms.websocket_price_feed import WebSocketPriceFeed
from src.trading_system.oms.running_signal_executor import RunningSignalExecutor
from src.trading_system.oms.earnings_filter import EarningsSeasonFilter, EarningsFilterConfig

# Global variables for graceful shutdown
running = True
price_feed: Optional[WebSocketPriceFeed] = None


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    global running, price_feed
    print("\n\n⚠️  Shutdown signal received. Stopping tests...")
    running = False
    
    if price_feed:
        price_feed.stop()
    
    print("✅ Tests stopped gracefully")
    sys.exit(0)


# Register signal handler
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def test_authentication(request_token: Optional[str] = None):
    """Phase 1: Authentication & Connection"""
    print("=" * 70)
    print("PHASE 1: AUTHENTICATION & CONNECTION")
    print("=" * 70)
    print()
    
    try:
        # Load credentials
        env_path = PROJECT_ROOT / "configs" / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        
        api_key = os.getenv("ZERODHA_API_KEY")
        api_secret = os.getenv("ZERODHA_API_SECRET")
        
        if not api_key or not api_secret:
            print("❌ Error: ZERODHA_API_KEY and ZERODHA_API_SECRET must be set")
            print("   Add them to configs/.env file")
            return None, None
        
        # Create credentials
        credentials = ZerodhaCredentials(api_key=api_key, api_secret=api_secret)
        
        # Create authenticator
        app_config = AppConfig()
        token_file = app_config.resolve_path(app_config.zerodha.token_file)
        authenticator = ZerodhaAuthenticator(
            credentials=credentials,
            token_file=token_file,
            logger=ComponentLogger.get_logger("zerodha_auth")
        )
        
        # Check connection health
        print("🔍 Checking connection health...")
        health = authenticator.check_connection_health()
        print(f"  WiFi:           {'✅' if health.wifi else '❌'}")
        print(f"  Zerodha API:    {'✅' if health.zerodha_api else '❌'}")
        print(f"  Trading System: {'✅' if health.trading_system else '❌'}")
        
        if health.error_message:
            print(f"\n⚠️  {health.error_message}")
        
        # Check if we have a valid token
        if authenticator.is_token_valid():
            print("✅ Already authenticated with valid token")
        else:
            print("\n🔐 Attempting login...")
            
            # Use provided token if available
            if request_token:
                print(f"✅ Using provided request token: {request_token[:20]}...")
                print("\n🔄 Authenticating with request token...")
                if not authenticator.authenticate_with_token(request_token):
                    print("❌ Authentication failed")
                    return None, None
            else:
                # Start OAuth callback server
                callback_server = OAuthCallbackServer(port=8080, timeout=120)
                if callback_server.start():
                    print("✅ Callback server started on http://localhost:8080")
                    
                    # Generate login URL
                    login_url = authenticator.get_login_url()
                    print(f"\n📋 Login URL: {login_url}")
                    
                    # Open browser
                    import webbrowser
                    webbrowser.open(login_url)
                    print("✅ Browser opened automatically")
                    
                    print("\n⏳ Waiting for you to complete login in browser...")
                    request_token = callback_server.wait_for_callback()
                    callback_server.stop()
                    
                    if not request_token:
                        print("⏱️  Timeout. Please enter token manually:")
                        request_token = input("   Enter request_token: ").strip()
                    
                    if request_token:
                        print("\n🔄 Authenticating with request token...")
                        if not authenticator.authenticate_with_token(request_token):
                            print("❌ Authentication failed")
                            return None, None
                else:
                    print("❌ Failed to start callback server")
                    request_token = input("   Enter request_token: ").strip()
                    if request_token:
                        if not authenticator.authenticate_with_token(request_token):
                            print("❌ Authentication failed")
                            return None, None
        
        # Get Kite instance
        kite = authenticator.get_kite_instance()
        if not kite:
            print("❌ Failed to get Kite instance")
            return None, None
        
        # Get profile
        profile = kite.profile()
        print(f"\n✅ Authentication successful!")
        print(f"   Logged in as: {profile.get('user_name', 'N/A')}")
        print(f"   User ID: {profile.get('user_id', 'N/A')}")
        print(f"   Connection Status: {authenticator.connection_status.value}")
        
        return authenticator, kite
        
    except Exception as e:
        print(f"❌ Error in authentication: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def test_futures_and_option_chain(kite, logger):
    """Phase 2: Futures & Option Chain"""
    print("\n" + "=" * 70)
    print("PHASE 2: FUTURES & OPTION CHAIN")
    print("=" * 70)
    print()
    
    try:
        # Get current month futures symbol and token
        print("🔍 Getting current month BankNifty futures...")
        symbol, token = get_current_month_futures_symbol_and_token(kite)
        
        if not symbol or not token:
            print("❌ Failed to get futures symbol/token")
            return None, None, None
        
        print(f"✅ Futures symbol: {symbol}")
        print(f"✅ Futures token: {token}")
        
        # Initialize option chain manager
        print("\n🔍 Fetching option chain...")
        option_chain_manager = OptionChainManager(kite=kite, logger=logger)
        option_chain_manager.refresh_option_chain()
        
        # Get expiry
        expiry_date = get_monthly_expiry_from_option_chain(kite)
        if expiry_date:
            print(f"✅ Option chain expiry: {expiry_date} (last Tuesday)")
        
        # Get summary
        summary = option_chain_manager.get_contracts_summary()
        print(f"✅ Option chain fetched: {summary['total_contracts']} contracts")
        if 'current_expiry' in summary:
            print(f"   Current expiry: {summary['current_expiry']}")
        elif 'expiry' in summary:
            print(f"   Expiry: {summary['expiry']}")
        strikes = summary.get('strikes', [])
        if isinstance(strikes, list):
            print(f"   Available strikes: {len(strikes)} strikes")
        else:
            print(f"   Available strikes: {strikes} strikes")
        
        # Test ATM strike calculation (using simple round method)
        futures_ltp = 57300.0  # Example LTP
        atm_strike = int(round(futures_ltp / 100) * 100)
        print(f"✅ ATM strike (LTP {futures_ltp}): {atm_strike}")
        
        return symbol, token, option_chain_manager
        
    except Exception as e:
        print(f"❌ Error in futures/option chain: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None


def test_margin_calculation(kite, option_chain_manager, futures_ltp, logger):
    """Phase 3: Margin Calculation (Real API)"""
    print("\n" + "=" * 70)
    print("PHASE 3: MARGIN CALCULATION (REAL API)")
    print("=" * 70)
    print()
    
    try:
        # Initialize margin calculator
        margin_calculator = MarginCalculator(
            kite=kite,
            option_chain_manager=option_chain_manager,
            logger=logger
        )
        
        # Calculate ATM and hedge strikes
        atm_strike = int(round(futures_ltp / 100) * 100)
        hedge_strike_long = atm_strike - (20 * 100)  # 20 legs down for LONG
        hedge_strike_short = atm_strike + (20 * 100)  # 20 legs up for SHORT
        
        # Test LONG margin (1 lot)
        print("🔍 Calculating LONG margin (1 lot)...")
        print(f"   ATM strike: {atm_strike}, Hedge strike: {hedge_strike_long}")
        long_margin = margin_calculator.calculate_long_margin(
            atm_strike=atm_strike,
            hedge_strike=hedge_strike_long,
            lot_size=1,
            futures_price=futures_ltp
        )
        
        if long_margin and isinstance(long_margin, dict):
            total_margin = long_margin.get('total_margin', 0)
            if total_margin > 0:
                print(f"✅ LONG margin (1 lot): ₹{total_margin:,.2f}")
                print(f"   Per lot: ₹{total_margin / 1:,.2f}")
                print(f"   Spread benefit: ₹{long_margin.get('spread_benefit', 0):,.2f}")
                print(f"   Initial margin: ₹{long_margin.get('initial_margin', 0):,.2f}")
                print(f"   Final margin: ₹{long_margin.get('final_margin', 0):,.2f}")
            else:
                print("❌ Failed to calculate LONG margin (total_margin is 0)")
                return None, None
        else:
            print("❌ Failed to calculate LONG margin (invalid response)")
            return None, None
        
        # Test SHORT margin (1 lot)
        print("\n🔍 Calculating SHORT margin (1 lot)...")
        print(f"   ATM strike: {atm_strike}, Hedge strike: {hedge_strike_short}")
        short_margin = margin_calculator.calculate_short_margin(
            atm_strike=atm_strike,
            hedge_strike=hedge_strike_short,
            lot_size=1,
            futures_price=futures_ltp
        )
        
        if short_margin and isinstance(short_margin, dict):
            total_margin = short_margin.get('total_margin', 0)
            if total_margin > 0:
                print(f"✅ SHORT margin (1 lot): ₹{total_margin:,.2f}")
                print(f"   Per lot: ₹{total_margin / 1:,.2f}")
                print(f"   Spread benefit: ₹{short_margin.get('spread_benefit', 0):,.2f}")
                print(f"   Initial margin: ₹{short_margin.get('initial_margin', 0):,.2f}")
                print(f"   Final margin: ₹{short_margin.get('final_margin', 0):,.2f}")
            else:
                print("❌ Failed to calculate SHORT margin (total_margin is 0)")
                return None, None
        else:
            print("❌ Failed to calculate SHORT margin (invalid response)")
            return None, None
        
        # Check available margin
        available_margin = margin_calculator.check_available_margin()
        long_total = long_margin.get('total_margin', 0) if isinstance(long_margin, dict) else 0
        short_total = short_margin.get('total_margin', 0) if isinstance(short_margin, dict) else 0
        
        if available_margin:
            print(f"\n✅ Available margin: ₹{available_margin:,.2f}")
            print(f"   LONG margin required: ₹{long_total:,.2f}")
            print(f"   SHORT margin required: ₹{short_total:,.2f}")
            
            if available_margin >= long_total:
                print(f"   ✅ Sufficient margin for LONG (1 lot)")
            else:
                print(f"   ⚠️  Insufficient margin for LONG (1 lot)")
            
            if available_margin >= short_total:
                print(f"   ✅ Sufficient margin for SHORT (1 lot)")
            else:
                print(f"   ⚠️  Insufficient margin for SHORT (1 lot)")
        
        return margin_calculator, (long_margin, short_margin)
        
    except Exception as e:
        print(f"❌ Error in margin calculation: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def test_long_entry(kite, option_chain_manager, margin_calculator, futures_token, futures_symbol, futures_ltp, logger):
    """Phase 4: LONG Entry (1 Lot, Dry Run)"""
    print("\n" + "=" * 70)
    print("PHASE 4: LONG ENTRY (1 LOT, DRY RUN)")
    print("=" * 70)
    print()
    
    try:
        # Initialize OMS (dry run mode)
        oms = OrderManager(
            kite=kite,
            lot_size=1,  # 1 lot for testing
            hedge_legs=20,
            logger=logger,
            dry_run=True  # DRY RUN MODE
        )
        
        # Update futures price first (needed for pre-calculation)
        try:
            quote = kite.quote(f"NSE_FUT:{futures_symbol}")
            if quote and f"NSE_FUT:{futures_symbol}" in quote:
                oms.update_futures_price(quote[f"NSE_FUT:{futures_symbol}"]["last_price"])
                print(f"✅ Updated futures LTP: ₹{oms.futures_ltp:.2f}")
        except Exception as e:
            print(f"⚠️  Failed to get futures LTP: {e}")
            oms.update_futures_price(futures_ltp)  # Use provided LTP
        
        # Pre-calculate margins
        print("🔍 Pre-calculating LONG margin...")
        oms.pre_calculate_margins()
        
        # Check margin availability
        available = oms.check_margin_availability("LONG", lot_size=1)
        if not available:
            print("⚠️  Insufficient margin for LONG entry (1 lot)")
            return None
        
        print("✅ Margin check passed")
        
        # Enter LONG position
        print("\n🔵 Entering LONG position (1 lot, DRY RUN)...")
        print("   Strategy: SELL ATM PE, BUY ATM CE, BUY Hedge PE (20 legs down)")
        
        success = oms.enter_long(fast_execution=False)
        
        if success:
            pos_status = oms.get_position_status()
            print(f"\n✅ LONG entry executed (DRY RUN)")
            print(f"   Position type: {pos_status['position_type']}")
            print(f"   ATM strike: {pos_status.get('atm_strike')}")
            print(f"   Hedge strike: {pos_status.get('hedge_strike')}")
            print(f"   Lot size: {pos_status.get('lot_size')}")
            print(f"   Entry time: {pos_status.get('entry_time')}")
            
            return oms
        else:
            print("❌ LONG entry failed")
            return None
        
    except Exception as e:
        print(f"❌ Error in LONG entry: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_short_entry(kite, option_chain_manager, margin_calculator, oms, futures_token, futures_symbol, futures_ltp, logger):
    """Phase 5: SHORT Entry (1 Lot, Dry Run)"""
    print("\n" + "=" * 70)
    print("PHASE 5: SHORT ENTRY (1 LOT, DRY RUN)")
    print("=" * 70)
    print()
    
    try:
        # Exit LONG position first (if exists)
        if oms and oms.position.position_type != PositionType.NONE:
            print("⏹️  Exiting existing position...")
            oms.exit_position()
            print("✅ Existing position exited")
            time.sleep(2)  # Wait for exit to complete
        
        # Update futures price first (needed for pre-calculation)
        try:
            quote = kite.quote(f"NSE_FUT:{futures_symbol}")
            if quote and f"NSE_FUT:{futures_symbol}" in quote:
                oms.update_futures_price(quote[f"NSE_FUT:{futures_symbol}"]["last_price"])
                print(f"✅ Updated futures LTP: ₹{oms.futures_ltp:.2f}")
        except Exception as e:
            print(f"⚠️  Failed to get futures LTP: {e}")
            oms.update_futures_price(futures_ltp)  # Use provided LTP
        
        # Pre-calculate margins
        print("\n🔍 Pre-calculating SHORT margin...")
        oms.pre_calculate_margins()
        
        # Check margin availability
        available = oms.check_margin_availability("SHORT", lot_size=1)
        if not available:
            print("⚠️  Insufficient margin for SHORT entry (1 lot)")
            return None
        
        print("✅ Margin check passed")
        
        # Enter SHORT position
        print("\n🔴 Entering SHORT position (1 lot, DRY RUN)...")
        print("   Strategy: SELL ATM CE, BUY ATM PE, BUY Hedge CE (20 legs up)")
        
        success = oms.enter_short(fast_execution=False)
        
        if success:
            pos_status = oms.get_position_status()
            print(f"\n✅ SHORT entry executed (DRY RUN)")
            print(f"   Position type: {pos_status['position_type']}")
            print(f"   ATM strike: {pos_status.get('atm_strike')}")
            print(f"   Hedge strike: {pos_status.get('hedge_strike')}")
            print(f"   Lot size: {pos_status.get('lot_size')}")
            print(f"   Entry time: {pos_status.get('entry_time')}")
            
            return oms
        else:
            print("❌ SHORT entry failed")
            return None
        
    except Exception as e:
        print(f"❌ Error in SHORT entry: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_exit_position(oms, logger):
    """Phase 6: Exit Position (1 Lot, Dry Run)"""
    print("\n" + "=" * 70)
    print("PHASE 6: EXIT POSITION (1 LOT, DRY RUN)")
    print("=" * 70)
    print()
    
    try:
        if not oms or oms.position.position_type == PositionType.NONE:
            print("⚠️  No position to exit")
            return False
        
        pos_status_before = oms.get_position_status()
        print(f"⏹️  Exiting {pos_status_before['position_type']} position (1 lot, DRY RUN)...")
        
        oms.exit_position()
        
        time.sleep(2)  # Wait for exit to complete
        
        pos_status_after = oms.get_position_status()
        
        if pos_status_after['position_type'] == 'NONE':
            print(f"\n✅ Position exited successfully (DRY RUN)")
            print(f"   Before: {pos_status_before['position_type']}")
            print(f"   After: {pos_status_after['position_type']}")
            return True
        else:
            print(f"❌ Position not cleared: {pos_status_after['position_type']}")
            return False
        
    except Exception as e:
        print(f"❌ Error in exit position: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_websocket_price_feed(kite, oms, futures_token, futures_symbol, logger):
    """Phase 7: WebSocket Price Feed"""
    print("\n" + "=" * 70)
    print("PHASE 7: WEBSOCKET PRICE FEED")
    print("=" * 70)
    print()
    
    global running, price_feed
    
    try:
        # Create OMS if not provided
        if oms is None:
            print("⚠️  No OMS provided, creating new OMS for WebSocket test...")
            from src.trading_system.oms.option_chain_manager import OptionChainManager
            option_chain_manager = OptionChainManager(kite=kite, logger=logger)
            option_chain_manager.refresh_option_chain()
            
            oms = OrderManager(
                kite=kite,
                lot_size=1,
                hedge_legs=20,
                logger=logger,
                dry_run=True
            )
        
        # Initialize WebSocket price feed
        print(f"📡 Starting WebSocket price feed for token {futures_token}...")
        price_feed = WebSocketPriceFeed(
            kite=kite,
            futures_token=futures_token,
            order_manager=oms,
            logger=logger
        )
        
        if not price_feed.start():
            print("❌ Failed to start WebSocket price feed")
            return False
        
        print("✅ WebSocket connected")
        
        # Wait for initial price
        print("\n⏳ Waiting for initial price update...")
        initial_price = None
        for i in range(10):
            if oms.futures_ltp and oms.futures_ltp > 0:
                initial_price = oms.futures_ltp
                break
            time.sleep(1)
        
        if initial_price:
            print(f"✅ Initial price received: ₹{initial_price:.2f}")
        else:
            print("⚠️  No initial price received")
        
        # Monitor price updates for 30 seconds
        print("\n📊 Monitoring price updates for 30 seconds...")
        print("   (Press Ctrl+C to stop early)")
        
        start_time = time.time()
        last_price = initial_price
        tick_count = 0
        
        while running and (time.time() - start_time) < 30:
            current_price = oms.futures_ltp
            
            if current_price and current_price != last_price:
                tick_count += 1
                price_change = current_price - (last_price or current_price)
                print(f"   Tick #{tick_count}: ₹{current_price:.2f} ({price_change:+.2f})")
                last_price = current_price
            
            time.sleep(0.5)
        
        print(f"\n✅ WebSocket price feed test complete")
        print(f"   Total ticks received: {tick_count}")
        print(f"   Final price: ₹{oms.futures_ltp:.2f}" if oms.futures_ltp else "   Final price: N/A")
        
        price_feed.stop()
        print("✅ WebSocket stopped")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in WebSocket price feed: {e}")
        import traceback
        traceback.print_exc()
        if price_feed:
            price_feed.stop()
        return False


def test_complete_flow(kite, option_chain_manager, margin_calculator, futures_token, futures_symbol, futures_ltp, logger):
    """Phase 8: Integration Test - Complete Flow"""
    print("\n" + "=" * 70)
    print("PHASE 8: INTEGRATION TEST - COMPLETE FLOW")
    print("=" * 70)
    print()
    
    try:
        # Initialize OMS (dry run mode)
        oms = OrderManager(
            kite=kite,
            lot_size=1,  # 1 lot for testing
            hedge_legs=20,
            logger=logger,
            dry_run=True  # DRY RUN MODE
        )
        
        # Initialize signal executor
        earnings_config = EarningsFilterConfig(use_filter=False)  # Disable for testing
        earnings_filter = EarningsSeasonFilter(earnings_config)
        executor = RunningSignalExecutor(oms=oms, earnings_filter=earnings_filter, logger=logger)
        
        # Step 1: Check position (none exists)
        print("🔍 Step 1: Checking position...")
        pos_status = oms.get_position_status()
        if pos_status['position_type'] == 'NONE':
            print("✅ No position exists → Proceeding with entry")
        else:
            print(f"⚠️  Position exists: {pos_status['position_type']} → Exiting first")
            oms.exit_position()
            time.sleep(2)
        
        # Step 2: Simulate LONG signal from ML algorithm
        print("\n🔍 Step 2: Simulating LONG signal from ML algorithm...")
        candle_id = datetime.now().strftime("%Y-%m-%d_%H:%M") + "_15min"
        executor.start_new_candle(candle_id=candle_id, opened_at=datetime.now())
        
        # Get current futures price
        if not futures_ltp:
            print("❌ No futures price available")
            return False
        
        executor.on_running_signal("LONG", candle_id=candle_id, futures_price=futures_ltp)
        
        # Step 3: Verify position established
        print("\n🔍 Step 3: Verifying position established...")
        time.sleep(3)  # Wait for orders to execute
        pos_status = oms.get_position_status()
        
        if pos_status['position_type'] == 'LONG':
            print(f"✅ Position established: {pos_status['position_type']}")
            print(f"   ATM strike: {pos_status.get('atm_strike')}")
            print(f"   Hedge strike: {pos_status.get('hedge_strike')}")
        else:
            print(f"❌ Position not established: {pos_status['position_type']}")
            return False
        
        # Step 4: Simulate 4-bar exit signal
        print("\n🔍 Step 4: Simulating 4-bar exit signal...")
        executor.on_running_signal("EXIT_LONG", candle_id=candle_id, futures_price=futures_ltp + 100)
        time.sleep(3)  # Wait for exit to execute
        
        # Step 5: Verify position cleared
        print("\n🔍 Step 5: Verifying position cleared...")
        pos_status = oms.get_position_status()
        
        if pos_status['position_type'] == 'NONE':
            print(f"✅ Position cleared: {pos_status['position_type']}")
            print("\n✅ Complete flow test passed!")
            return True
        else:
            print(f"❌ Position not cleared: {pos_status['position_type']}")
            return False
        
    except Exception as e:
        print(f"❌ Error in complete flow test: {e}")
        import traceback
        traceback.print_exc()
        return False


def main(request_token: Optional[str] = None):
    """Main testing function"""
    print("\n" + "=" * 70)
    print("LIVE ZERODHA API TESTING - DRY RUN MODE (1 LOT)")
    print("=" * 70)
    print()
    print("⚠️  SAFETY: All orders are in DRY-RUN mode (no real orders)")
    print("⚠️  LOT SIZE: 1 lot only (for safety)")
    print("⚠️  Press Ctrl+C at any time to stop testing")
    print()
    
    # Setup logging
    setup_logging(log_dir=PROJECT_ROOT / "logs")
    logger = ComponentLogger.get_logger("live_api_testing")
    
    results = {
        'Phase 1: Authentication': False,
        'Phase 2: Futures & Option Chain': False,
        'Phase 3: Margin Calculation': False,
        'Phase 4: LONG Entry': False,
        'Phase 5: SHORT Entry': False,
        'Phase 6: Exit Position': False,
        'Phase 7: WebSocket Price Feed': False,
        'Phase 8: Complete Flow': False
    }
    
    authenticator = None
    kite = None
    futures_symbol = None
    futures_token = None
    option_chain_manager = None
    margin_calculator = None
    oms = None
    
    try:
        # Phase 1: Authentication
        authenticator, kite = test_authentication(request_token=request_token)
        if not kite:
            print("\n❌ Phase 1 failed - Cannot proceed without authentication")
            return
        results['Phase 1: Authentication'] = True
        
        # Get futures LTP (example)
        futures_ltp = 57300.0  # Will be updated from WebSocket if needed
        
        # Phase 2: Futures & Option Chain
        futures_symbol, futures_token, option_chain_manager = test_futures_and_option_chain(kite, logger)
        if not futures_symbol or not futures_token or not option_chain_manager:
            print("\n❌ Phase 2 failed - Cannot proceed without futures/option chain")
            return
        results['Phase 2: Futures & Option Chain'] = True
        
        # Phase 3: Margin Calculation
        margin_calculator, margins = test_margin_calculation(kite, option_chain_manager, futures_ltp, logger)
        if not margin_calculator:
            print("\n❌ Phase 3 failed - Cannot proceed without margin calculation")
            return
        results['Phase 3: Margin Calculation'] = True
        
        # Phase 4: LONG Entry
        oms = test_long_entry(kite, option_chain_manager, margin_calculator, futures_token, futures_symbol, futures_ltp, logger)
        if oms:
            results['Phase 4: LONG Entry'] = True
        
        # Phase 5: SHORT Entry
        oms = test_short_entry(kite, option_chain_manager, margin_calculator, oms, futures_token, futures_symbol, futures_ltp, logger)
        if oms:
            results['Phase 5: SHORT Entry'] = True
        
        # Phase 6: Exit Position
        if test_exit_position(oms, logger):
            results['Phase 6: Exit Position'] = True
        
        # Phase 7: WebSocket Price Feed (optional, may timeout)
        try:
            if test_websocket_price_feed(kite, oms, futures_token, futures_symbol, logger):
                results['Phase 7: WebSocket Price Feed'] = True
        except Exception as e:
            print(f"\n⚠️  Phase 7 skipped due to error: {e}")
            import traceback
            traceback.print_exc()
        
        # Phase 8: Complete Flow
        if test_complete_flow(kite, option_chain_manager, margin_calculator, futures_token, futures_symbol, futures_ltp, logger):
            results['Phase 8: Complete Flow'] = True
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Testing interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        global price_feed
        if price_feed:
            price_feed.stop()
        
        # Print summary
        print("\n" + "=" * 70)
        print("TESTING SUMMARY")
        print("=" * 70)
        
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        
        for phase, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status}: {phase}")
        
        print("\n" + "=" * 70)
        print(f"RESULTS: {passed}/{total} phases passed")
        print("=" * 70)
        
        if passed == total:
            print("\n🎉 ALL TESTS PASSED!")
            print("✅ System is ready for live trading (after switching to dry_run=False)")
        elif passed >= 4:
            print("\n⚠️  MOST TESTS PASSED")
            print("   Review failed phases and fix issues before live trading")
        else:
            print("\n❌ MULTIPLE TESTS FAILED")
            print("   Please review and fix issues before proceeding")


if __name__ == "__main__":
    import sys
    # Check for request token as command line argument
    request_token = sys.argv[1] if len(sys.argv) > 1 else None
    main(request_token=request_token)

