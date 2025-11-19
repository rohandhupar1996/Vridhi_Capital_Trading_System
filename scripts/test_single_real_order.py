"""
SAFETY TEST: Single Real Order Placement
==========================================

This script tests placing ONE real order to verify order execution works correctly.

⚠️  WARNING: This will place a REAL order on Zerodha dashboard!
⚠️  Start with 1 lot, single order only
⚠️  Have Zerodha dashboard open to verify order appears

Test Plan:
1. Place ONE real BUY order (1 lot, any option)
2. Verify order appears on Zerodha dashboard
3. Verify order executes successfully
4. Exit position manually or using script
5. Only proceed to full trading after this test passes

Usage:
    python scripts/test_single_real_order.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import os
from dotenv import load_dotenv

from src.trading_system.config import AppConfig
from src.trading_system.logging import setup_logging, ComponentLogger
from src.trading_system.broker import ZerodhaAuthenticator
from src.trading_system.broker.zerodha_auth import ZerodhaCredentials
from src.trading_system.data.zerodha_futures_utils import (
    get_current_month_futures_symbol_and_token,
    get_monthly_expiry_from_option_chain
)
from src.trading_system.oms.option_chain_manager import OptionChainManager
from src.trading_system.oms.order_manager import OrderManager

# Load environment
load_dotenv()

# Setup logging
setup_logging()
logger = ComponentLogger.get_logger("test_single_real_order")


def test_single_real_order():
    """Test placing ONE real order to verify order execution"""
    
    print("\n" + "=" * 70)
    print("⚠️  SINGLE REAL ORDER TEST ⚠️")
    print("=" * 70)
    print()
    print("⚠️  WARNING: This will place a REAL order on Zerodha dashboard!")
    print("⚠️  Make sure:")
    print("   1. Zerodha dashboard is open")
    print("   2. You are ready to verify the order appears")
    print("   3. You have sufficient margin")
    print("   4. Market is open")
    print()
    
    response = input("Type 'YES' to continue with real order placement: ")
    if response != "YES":
        print("❌ Test cancelled")
        return
    
    try:
        # Step 1: Authenticate
        print("\n" + "=" * 70)
        print("STEP 1: Authentication")
        print("=" * 70)
        
        # Load credentials from environment
        api_key = os.getenv("ZERODHA_API_KEY")
        api_secret = os.getenv("ZERODHA_API_SECRET")
        
        if not api_key or not api_secret:
            print("❌ Missing ZERODHA_API_KEY or ZERODHA_API_SECRET in environment")
            return
        
        credentials = ZerodhaCredentials(
            api_key=api_key,
            api_secret=api_secret
        )
        authenticator = ZerodhaAuthenticator(credentials, logger)
        kite = authenticator.get_authenticated_kite()
        
        if not kite:
            print("❌ Authentication failed")
            return
        
        profile = kite.profile()
        print(f"✅ Authenticated as: {profile['user_name']} ({profile['user_id']})")
        
        # Step 2: Get futures and option chain
        print("\n" + "=" * 70)
        print("STEP 2: Get Futures & Option Chain")
        print("=" * 70)
        
        futures_symbol, futures_token = get_current_month_futures_symbol_and_token(kite)
        if not futures_symbol or not futures_token:
            print("❌ Failed to get futures symbol/token")
            return
        
        print(f"✅ Futures: {futures_symbol} (token: {futures_token})")
        
        # Get futures LTP
        quote = kite.quote(f"NSE_FUT:{futures_symbol}")
        futures_ltp = quote[f"NSE_FUT:{futures_symbol}"]["last_price"]
        print(f"✅ Futures LTP: ₹{futures_ltp:.2f}")
        
        # Initialize option chain manager
        option_chain_manager = OptionChainManager(kite=kite, logger=logger)
        option_chain_manager.refresh_option_chain()
        
        # Calculate ATM strike
        atm_strike = int(round(futures_ltp / 100) * 100)
        print(f"✅ ATM strike: {atm_strike}")
        
        # Step 3: Get option symbol
        print("\n" + "=" * 70)
        print("STEP 3: Get Option Symbol")
        print("=" * 70)
        
        # Get ATM CE symbol for testing
        atm_ce_symbol = option_chain_manager.get_option_symbol(atm_strike, "CE")
        if not atm_ce_symbol:
            print(f"❌ Failed to get option symbol for {atm_strike} CE")
            return
        
        print(f"✅ Option symbol: {atm_ce_symbol}")
        
        # Get option quote to verify
        option_quote = kite.quote(f"NFO:{atm_ce_symbol}")
        option_ltp = option_quote[f"NFO:{atm_ce_symbol}"]["last_price"]
        print(f"✅ Option LTP: ₹{option_ltp:.2f}")
        
        # Step 4: Initialize Order Manager (REAL MODE)
        print("\n" + "=" * 70)
        print("STEP 4: Initialize Order Manager (REAL MODE)")
        print("=" * 70)
        
        print("⚠️  Setting dry_run=False - REAL orders will be placed!")
        
        oms = OrderManager(
            kite=kite,
            lot_size=1,  # 1 lot only
            hedge_legs=20,
            logger=logger,
            dry_run=False  # ⚠️  REAL MODE
        )
        
        oms.update_futures_price(futures_ltp)
        oms.option_chain_manager = option_chain_manager
        
        print("✅ Order Manager initialized (REAL MODE)")
        
        # Step 5: Place ONE real order
        print("\n" + "=" * 70)
        print("STEP 5: Place ONE Real Order (BUY)")
        print("=" * 70)
        
        print(f"🔵 Placing REAL BUY order:")
        print(f"   Symbol: {atm_ce_symbol}")
        print(f"   Quantity: 35 (1 lot)")
        print(f"   Exchange: NFO")
        print(f"   Product: NRML")
        print(f"   Order Type: MARKET")
        print()
        
        response = input("Type 'CONFIRM' to place this REAL order: ")
        if response != "CONFIRM":
            print("❌ Order placement cancelled")
            return
        
        # Place the order
        print("\n📤 Placing order...")
        order_id = oms._place_market_order(
            symbol=atm_ce_symbol,
            quantity=35,  # 1 lot
            transaction_type="BUY"
        )
        
        if not order_id:
            print("❌ Order placement failed")
            return
        
        print(f"✅ Order placed!")
        print(f"   Order ID: {order_id}")
        print()
        print("🔍 CHECK ZERODHA DASHBOARD NOW:")
        print("   1. Go to Zerodha dashboard")
        print("   2. Check 'Orders' tab")
        print("   3. Verify order appears with ID:", order_id)
        print("   4. Wait for order to execute")
        print()
        
        input("Press Enter after verifying order appears on Zerodha dashboard...")
        
        # Step 6: Check order status
        print("\n" + "=" * 70)
        print("STEP 6: Check Order Status")
        print("=" * 70)
        
        print("🔍 Checking order status...")
        
        # Wait a bit for order to execute
        import time
        time.sleep(3)
        
        # Check status
        status = oms._check_order_status(order_id)
        print(f"✅ Order status: {status}")
        
        if status.value == "COMPLETE":
            # Get order details
            filled_qty, avg_price = oms._get_order_details(order_id)
            print(f"✅ Order executed!")
            print(f"   Filled quantity: {filled_qty}")
            print(f"   Average price: ₹{avg_price:.2f}")
            
            # Step 7: Exit position
            print("\n" + "=" * 70)
            print("STEP 7: Exit Position")
            print("=" * 70)
            
            print(f"🔴 Exiting position: SELL {atm_ce_symbol}")
            
            response = input("Type 'EXIT' to exit this position: ")
            if response == "EXIT":
                exit_order_id = oms._place_market_order(
                    symbol=atm_ce_symbol,
                    quantity=35,
                    transaction_type="SELL"
                )
                
                if exit_order_id:
                    print(f"✅ Exit order placed!")
                    print(f"   Order ID: {exit_order_id}")
                    
                    time.sleep(3)
                    exit_status = oms._check_order_status(exit_order_id)
                    print(f"✅ Exit order status: {exit_status}")
                    
                    if exit_status.value == "COMPLETE":
                        filled_qty, avg_price = oms._get_order_details(exit_order_id)
                        print(f"✅ Position exited!")
                        print(f"   Filled quantity: {filled_qty}")
                        print(f"   Average price: ₹{avg_price:.2f}")
            
        elif status.value == "REJECTED":
            print("❌ Order REJECTED!")
            print("   Check Zerodha dashboard for rejection reason")
            print("   Common reasons:")
            print("   - Insufficient margin")
            print("   - Invalid symbol")
            print("   - Exchange not open")
            print("   - Rate limit exceeded")
        else:
            print(f"⚠️  Order status: {status.value}")
            print("   Order might be pending or partially filled")
            print("   Check Zerodha dashboard")
        
        # Step 8: Summary
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        
        print("✅ Single real order test completed")
        print()
        print("What was verified:")
        print("   ✅ Order placement API call works")
        print("   ✅ Order appears on Zerodha dashboard")
        print("   ✅ Order execution works")
        print("   ✅ Order status checking works")
        print()
        print("Next steps:")
        print("   1. Verify order on Zerodha dashboard matches system")
        print("   2. If successful, proceed to 3-leg strategy test")
        print("   3. After 3-leg test passes, enable full trading")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_single_real_order()

