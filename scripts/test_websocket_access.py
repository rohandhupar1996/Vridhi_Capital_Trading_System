"""
Test Script to Verify Zerodha WebSocket Access
Checks if your paid Connect subscription includes WebSocket/KiteTicker access
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
import os

from src.trading_system.broker.zerodha_auth import ZerodhaAuthenticator, ZerodhaCredentials
from src.trading_system.logging import ComponentLogger, setup_logging
from kiteconnect import KiteTicker

setup_logging("logs")
logger = ComponentLogger.get_logger("websocket_test")


def test_websocket_access():
    """Test if WebSocket/KiteTicker is accessible with current subscription."""
    
    print("\n" + "="*70)
    print("ZERODHA WEBSOCKET ACCESS TEST")
    print("="*70 + "\n")
    
    # Load credentials
    env_path = PROJECT_ROOT / "configs" / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Loaded credentials from {env_path}")
    else:
        print(f"❌ Config file not found: {env_path}")
        return False
    
    api_key = os.getenv("ZERODHA_API_KEY")
    api_secret = os.getenv("ZERODHA_API_SECRET")
    
    if not api_key or not api_secret:
        print("❌ ZERODHA_API_KEY or ZERODHA_API_SECRET not found in .env")
        return False
    
    print(f"✅ API Key found: {api_key[:10]}...")
    
    # Authenticate
    print("\n📡 Authenticating with Zerodha...")
    credentials = ZerodhaCredentials(api_key=api_key, api_secret=api_secret)
    authenticator = ZerodhaAuthenticator(
        credentials=credentials,
        token_file="configs/zerodha_tokens.json",
        logger=logger
    )
    
    # Try to login/reconnect
    print("   Attempting to login/reconnect...")
    login_success = authenticator.login(auto_open_browser=False)
    
    if not login_success:
        print("\n⚠️  Auto-login failed. Trying manual login...")
        print("   Opening browser for manual login...")
        login_success = authenticator.login(auto_open_browser=True)
        
        if not login_success:
            print("❌ Authentication failed. Please run: python scripts/zerodha_login.py")
            return False
    
    kite = authenticator.get_kite()
    if not kite:
        print("❌ Failed to get Kite instance")
        return False
    
    print("✅ Authentication successful")
    print(f"   User ID: {kite.profile().get('user_id', 'N/A')}")
    print(f"   User Name: {kite.profile().get('user_name', 'N/A')}")
    
    # Test 1: Check if KiteTicker can be imported and initialized
    print("\n" + "-"*70)
    print("TEST 1: KiteTicker Class Availability")
    print("-"*70)
    
    try:
        from kiteconnect import KiteTicker
        print("✅ KiteTicker class imported successfully")
        print(f"   Class: {KiteTicker}")
    except ImportError as e:
        print(f"❌ Failed to import KiteTicker: {e}")
        return False
    
    # Test 2: Try to initialize KiteTicker
    print("\n" + "-"*70)
    print("TEST 2: KiteTicker Initialization")
    print("-"*70)
    
    try:
        access_token = kite.access_token
        print(f"✅ Access token available: {access_token[:20]}...")
        
        kws = KiteTicker(api_key=api_key, access_token=access_token)
        print("✅ KiteTicker initialized successfully")
        print(f"   API Key: {api_key[:10]}...")
        print(f"   Access Token: {access_token[:20]}...")
    except Exception as e:
        print(f"❌ Failed to initialize KiteTicker: {e}")
        print("   This might indicate subscription issue")
        return False
    
    # Test 3: Get a test instrument token (BankNifty futures)
    print("\n" + "-"*70)
    print("TEST 3: Getting Test Instrument Token")
    print("-"*70)
    
    try:
        # Try to get BankNifty futures instrument
        instruments = kite.instruments("NFO")
        futures_instruments = [
            inst for inst in instruments 
            if 'BANKNIFTY' in inst['tradingsymbol'] and inst['tradingsymbol'].endswith('FUT')
        ]
        
        if not futures_instruments:
            print("⚠️  No BankNifty futures found (market might be closed)")
            print("   Trying to get any NFO instrument for test...")
            test_instruments = [inst for inst in instruments if inst['exchange'] == 'NFO'][:5]
            if test_instruments:
                test_token = test_instruments[0]['instrument_token']
                test_symbol = test_instruments[0]['tradingsymbol']
                print(f"✅ Using test instrument: {test_symbol} (token: {test_token})")
            else:
                print("❌ No instruments found")
                return False
        else:
            # Get current month futures
            test_instrument = futures_instruments[0]
            test_token = test_instrument['instrument_token']
            test_symbol = test_instrument['tradingsymbol']
            print(f"✅ Found BankNifty futures: {test_symbol}")
            print(f"   Instrument Token: {test_token}")
    except Exception as e:
        print(f"❌ Failed to get instruments: {e}")
        return False
    
    # Test 4: Try to connect and subscribe (this will reveal subscription status)
    print("\n" + "-"*70)
    print("TEST 4: WebSocket Connection Test")
    print("-"*70)
    print("⚠️  This will attempt to connect to Zerodha WebSocket...")
    print("    If you see subscription errors, you may need Connect plan")
    print()
    
    connection_result = {"success": False, "error": None}
    
    def on_connect(ws, response):
        print("✅ WebSocket connected successfully!")
        print(f"   Response: {response}")
        connection_result["success"] = True
    
    def on_close(ws, code, reason):
        print(f"⚠️  WebSocket closed: code={code}, reason={reason}")
    
    def on_error(ws, code, reason):
        error_msg = f"WebSocket error: code={code}, reason={reason}"
        print(f"❌ {error_msg}")
        connection_result["error"] = error_msg
        connection_result["success"] = False
    
    def on_ticks(ws, ticks):
        print(f"✅ Received tick data! WebSocket is working!")
        print(f"   Ticks received: {len(ticks)}")
        if ticks:
            first_tick = ticks[0]
            print(f"   Sample tick: {first_tick}")
        connection_result["success"] = True
    
    try:
        kws.on_connect = on_connect
        kws.on_close = on_close
        kws.on_error = on_error
        kws.on_ticks = on_ticks
        
        print("📡 Attempting to connect...")
        kws.subscribe([test_token])
        kws.set_mode(kws.MODE_LTP, [test_token])
        kws.connect(threaded=True)
        
        # Wait for connection (max 10 seconds)
        print("⏳ Waiting for connection (max 10 seconds)...")
        for i in range(10):
            time.sleep(1)
            if connection_result["success"]:
                print(f"\n✅ Connection successful after {i+1} seconds!")
                break
            if connection_result["error"]:
                print(f"\n❌ Connection failed: {connection_result['error']}")
                break
            print(".", end="", flush=True)
        else:
            print("\n⚠️  Connection timeout - no response after 10 seconds")
            print("   This might indicate:")
            print("   1. Market is closed")
            print("   2. Subscription issue (need Connect plan)")
            print("   3. Network/connection issue")
        
        # Wait a bit more to see if we get any ticks
        if connection_result["success"]:
            print("\n⏳ Waiting for tick data (5 seconds)...")
            time.sleep(5)
        
        # Clean up
        try:
            kws.unsubscribe([test_token])
            kws.close()
        except:
            pass
        
    except Exception as e:
        print(f"❌ Exception during WebSocket test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Final Result
    print("\n" + "="*70)
    print("FINAL RESULT")
    print("="*70)
    
    if connection_result["success"]:
        print("✅ SUCCESS: WebSocket is working!")
        print("   Your Connect subscription includes WebSocket access")
        print("   You can use WebSocketPriceFeed for live trading")
        return True
    else:
        print("⚠️  WebSocket connection test inconclusive")
        if connection_result["error"]:
            print(f"   Error: {connection_result['error']}")
        print("\n   Possible reasons:")
        print("   1. Market is closed (WebSocket only works during market hours)")
        print("   2. Need Zerodha Connect subscription (₹500/month)")
        print("   3. Network/firewall blocking WebSocket connection")
        print("\n   To verify subscription:")
        print("   - Check Zerodha Console: https://kite.trade/app/console/")
        print("   - Look for 'Connect' subscription status")
        print("   - Try during market hours (9:15 AM - 3:30 PM IST)")
        return False


if __name__ == "__main__":
    try:
        result = test_websocket_access()
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

