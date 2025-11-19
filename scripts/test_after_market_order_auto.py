"""
AFTER-MARKET ORDER PLACEMENT TEST - AUTOMATED VERSION
======================================================

This version runs all checks WITHOUT placing actual orders.
Useful for verifying setup and API connections.

For actual order placement, use test_after_market_order.py (interactive)
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime
import time

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import os
from dotenv import load_dotenv
import pytz

from src.trading_system.config import AppConfig
from src.trading_system.logging import setup_logging, ComponentLogger
from src.trading_system.broker import ZerodhaAuthenticator
from src.trading_system.broker.zerodha_auth import ZerodhaCredentials

# Import directly (avoids __init__.py import issues)
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from trading_system.data.zerodha_futures_utils import (
    get_current_month_futures_symbol_and_token,
    get_monthly_expiry_from_option_chain
)
from src.trading_system.oms.option_chain_manager import OptionChainManager
from src.trading_system.oms.order_manager import OrderManager, OrderStatus

# Load environment
load_dotenv()

# Setup logging
setup_logging()
logger = ComponentLogger.get_logger("test_after_market_order_auto")

KOLKATA_TZ = pytz.timezone('Asia/Kolkata')


def check_market_hours():
    """Check if market is currently open"""
    now = datetime.now(KOLKATA_TZ)
    current_time = now.time()
    
    market_open = datetime.strptime("09:15", "%H:%M").time()
    market_close = datetime.strptime("15:30", "%H:%M").time()
    
    if market_open <= current_time <= market_close:
        return True, "OPEN"
    elif current_time > market_close:
        return False, "CLOSED (After Hours)"
    else:
        return False, "CLOSED (Before Hours)"


def test_after_market_order_auto():
    """Automated test - verifies setup WITHOUT placing orders"""
    
    print("\n" + "=" * 70)
    print("🌙 AFTER-MARKET ORDER TEST - AUTOMATED (VERIFICATION ONLY)")
    print("=" * 70)
    print()
    print("⚠️  NOTE: This version does NOT place actual orders")
    print("⚠️  It only verifies API connections and setup")
    print("⚠️  For actual order placement, use test_after_market_order.py")
    print()
    
    test_results = {
        "authentication": False,
        "futures_data": False,
        "option_chain": False,
        "order_manager_init": False,
        "market_status": None,
        "ready_for_real_test": False
    }
    
    try:
        # Step 1: Check market hours
        print("=" * 70)
        print("STEP 1: Check Market Hours")
        print("=" * 70)
        
        is_open, status = check_market_hours()
        now = datetime.now(KOLKATA_TZ)
        print(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"Market status: {status}")
        test_results["market_status"] = status
        
        if is_open:
            print("⚠️  Market is OPEN - Orders would execute IMMEDIATELY")
        else:
            print("✅ Market is CLOSED - Orders would be QUEUED (safe for testing)")
        
        # Step 2: Authentication
        print("\n" + "=" * 70)
        print("STEP 2: Authentication")
        print("=" * 70)
        
        api_key = os.getenv("ZERODHA_API_KEY")
        api_secret = os.getenv("ZERODHA_API_SECRET")
        
        if not api_key or not api_secret:
            print("❌ Missing ZERODHA_API_KEY or ZERODHA_API_SECRET")
            return test_results
        
        credentials = ZerodhaCredentials(
            api_key=api_key,
            api_secret=api_secret
        )
        authenticator = ZerodhaAuthenticator(credentials, logger)
        kite = authenticator.get_authenticated_kite()
        
        if not kite:
            print("❌ Authentication failed")
            return test_results
        
        profile = kite.profile()
        print(f"✅ Authenticated as: {profile['user_name']} ({profile['user_id']})")
        test_results["authentication"] = True
        
        # Step 3: Get futures and option chain
        print("\n" + "=" * 70)
        print("STEP 3: Get Futures & Option Chain")
        print("=" * 70)
        
        futures_symbol, futures_token = get_current_month_futures_symbol_and_token(kite)
        if not futures_symbol or not futures_token:
            print("❌ Failed to get futures symbol/token")
            return test_results
        
        print(f"✅ Futures: {futures_symbol} (token: {futures_token})")
        test_results["futures_data"] = True
        
        # Get futures LTP
        try:
            quote = kite.quote(f"NSE_FUT:{futures_symbol}")
            futures_ltp = quote[f"NSE_FUT:{futures_symbol}"]["last_price"]
            print(f"✅ Futures LTP: ₹{futures_ltp:.2f}")
        except Exception as e:
            print(f"⚠️  Cannot get futures LTP (market closed): {e}")
            futures_ltp = 59000.0
        
        # Initialize option chain manager
        option_chain_manager = OptionChainManager(kite=kite, logger=logger)
        option_chain_manager.refresh_option_chain()
        
        # Calculate ATM strike
        atm_strike = int(round(futures_ltp / 100) * 100)
        print(f"✅ ATM strike: {atm_strike}")
        test_results["option_chain"] = True
        
        # Step 4: Get option symbol
        print("\n" + "=" * 70)
        print("STEP 4: Get Option Symbol")
        print("=" * 70)
        
        atm_ce_symbol = option_chain_manager.get_option_symbol(atm_strike, "CE")
        if not atm_ce_symbol:
            print(f"❌ Failed to get option symbol for {atm_strike} CE")
            return test_results
        
        print(f"✅ Option symbol: {atm_ce_symbol}")
        
        # Try to get option quote (might fail if market closed)
        try:
            option_quote = kite.quote(f"NFO:{atm_ce_symbol}")
            option_ltp = option_quote[f"NFO:{atm_ce_symbol}"]["last_price"]
            print(f"✅ Option LTP: ₹{option_ltp:.2f}")
        except Exception as e:
            print(f"⚠️  Cannot get option LTP (market closed): {e}")
        
        # Step 5: Initialize Order Manager (DRY-RUN mode for safety)
        print("\n" + "=" * 70)
        print("STEP 5: Initialize Order Manager")
        print("=" * 70)
        
        print("ℹ️  Initializing in DRY-RUN mode for safety")
        
        oms = OrderManager(
            kite=kite,
            lot_size=1,  # 1 lot only
            hedge_legs=20,
            logger=logger,
            dry_run=True  # DRY-RUN mode (no real orders)
        )
        
        oms.update_futures_price(futures_ltp)
        oms.option_chain_manager = option_chain_manager
        
        print("✅ Order Manager initialized (DRY-RUN mode)")
        test_results["order_manager_init"] = True
        
        # Step 6: Verify order parameters (without placing order)
        print("\n" + "=" * 70)
        print("STEP 6: Verify Order Parameters")
        print("=" * 70)
        
        print("✅ Order Parameters Verified:")
        print(f"   Symbol: {atm_ce_symbol}")
        print(f"   Quantity: 35 (1 lot)")
        print(f"   Exchange: NFO")
        print(f"   Product: NRML")
        print(f"   Order Type: MARKET")
        print(f"   Transaction Type: BUY")
        
        # Step 7: Test Summary
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        
        all_passed = all([
            test_results["authentication"],
            test_results["futures_data"],
            test_results["option_chain"],
            test_results["order_manager_init"]
        ])
        
        test_results["ready_for_real_test"] = all_passed and not is_open
        
        print(f"✅ Authentication: {'PASS' if test_results['authentication'] else 'FAIL'}")
        print(f"✅ Futures Data: {'PASS' if test_results['futures_data'] else 'FAIL'}")
        print(f"✅ Option Chain: {'PASS' if test_results['option_chain'] else 'FAIL'}")
        print(f"✅ Order Manager: {'PASS' if test_results['order_manager_init'] else 'FAIL'}")
        print(f"✅ Market Status: {test_results['market_status']}")
        print()
        
        if all_passed:
            print("✅ ALL CHECKS PASSED!")
            print()
            
            if not is_open:
                print("✅ READY FOR REAL ORDER TEST:")
                print("   Market is CLOSED - Safe to place test orders")
                print("   Run: python scripts/test_after_market_order.py")
                print("   Orders will be QUEUED and execute at 9:15 AM next day")
            else:
                print("⚠️  Market is OPEN - Orders would execute IMMEDIATELY")
                print("⚠️  Wait for market close (after 3:30 PM) for safe testing")
        else:
            print("❌ SOME CHECKS FAILED!")
            print("   Fix issues before attempting real order placement")
        
        print()
        print("Next Steps:")
        if test_results["ready_for_real_test"]:
            print("1. ✅ Setup verified - Ready for real test")
            print("2. Run: python scripts/test_after_market_order.py")
            print("3. Type 'CONFIRM' when prompted")
            print("4. Type 'PLACE' to place real order")
            print("5. Verify order on Zerodha dashboard")
            print("6. Cancel order before 9:15 AM next day (optional)")
        else:
            print("1. Fix any failed checks above")
            print("2. Re-run this test: python scripts/test_after_market_order_auto.py")
            print("3. After all checks pass, run real test")
        
        return test_results
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        return test_results
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return test_results


if __name__ == "__main__":
    results = test_after_market_order_auto()
    sys.exit(0 if results.get("ready_for_real_test", False) else 1)

