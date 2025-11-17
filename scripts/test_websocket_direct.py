"""
Direct WebSocket Test with Provided Token
Tests WebSocket connection without re-authentication
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

from kiteconnect import KiteConnect, KiteTicker

print("\n" + "="*70)
print("DIRECT WEBSOCKET TEST WITH PROVIDED TOKEN")
print("="*70 + "\n")

# Load credentials
env_path = PROJECT_ROOT / "configs" / ".env"
if env_path.exists():
    load_dotenv(env_path)
    api_key = os.getenv("ZERODHA_API_KEY")
    api_secret = os.getenv("ZERODHA_API_SECRET")
    
    if not api_key or not api_secret:
        print("❌ ZERODHA_API_KEY or ZERODHA_API_SECRET not found")
        sys.exit(1)
    
    print(f"✅ API Key: {api_key[:10]}...")
else:
    print(f"❌ Config file not found: {env_path}")
    sys.exit(1)

# Load token from file
token_file = PROJECT_ROOT / "configs" / "zerodha_tokens.json"
if not token_file.exists():
    print(f"❌ Token file not found: {token_file}")
    sys.exit(1)

import json
with open(token_file, 'r') as f:
    token_data = json.load(f)
    access_token = token_data.get('access_token')

if not access_token:
    print("❌ Access token not found in token file")
    sys.exit(1)

print(f"✅ Access Token: {access_token[:20]}...")

# Test 1: Verify token works with KiteConnect
print("\n" + "-"*70)
print("TEST 1: Token Validation")
print("-"*70)

try:
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    
    # Try to get profile (this validates the token)
    profile = kite.profile()
    print("✅ Token is valid!")
    print(f"   User ID: {profile.get('user_id', 'N/A')}")
    print(f"   User Name: {profile.get('user_name', 'N/A')}")
    print(f"   Email: {profile.get('email', 'N/A')}")
except Exception as e:
    print(f"❌ Token validation failed: {e}")
    print("   Token might be invalid or expired")
    sys.exit(1)

# Test 2: Get BankNifty futures instrument
print("\n" + "-"*70)
print("TEST 2: Getting BankNifty Futures Instrument")
print("-"*70)

try:
    instruments = kite.instruments("NFO")
    futures_instruments = [
        inst for inst in instruments 
        if 'BANKNIFTY' in inst['tradingsymbol'] and inst['tradingsymbol'].endswith('FUT')
    ]
    
    if not futures_instruments:
        print("⚠️  No BankNifty futures found")
        print("   Market might be closed or no active contracts")
        print("   Trying any NFO instrument...")
        test_instruments = [inst for inst in instruments if inst['exchange'] == 'NFO'][:5]
        if test_instruments:
            test_instrument = test_instruments[0]
            test_token = test_instrument['instrument_token']
            test_symbol = test_instrument['tradingsymbol']
            print(f"✅ Using test instrument: {test_symbol} (token: {test_token})")
        else:
            print("❌ No instruments found")
            sys.exit(1)
    else:
        # Get current month futures (usually first one)
        test_instrument = futures_instruments[0]
        test_token = test_instrument['instrument_token']
        test_symbol = test_instrument['tradingsymbol']
        print(f"✅ Found BankNifty futures: {test_symbol}")
        print(f"   Instrument Token: {test_token}")
except Exception as e:
    print(f"❌ Failed to get instruments: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Initialize KiteTicker
print("\n" + "-"*70)
print("TEST 3: KiteTicker Initialization")
print("-"*70)

try:
    kws = KiteTicker(api_key=api_key, access_token=access_token)
    print("✅ KiteTicker initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize KiteTicker: {e}")
    sys.exit(1)

# Test 4: WebSocket Connection Test
print("\n" + "-"*70)
print("TEST 4: WebSocket Connection Test")
print("-"*70)
print("⚠️  Attempting to connect to Zerodha WebSocket...")
print("    This will reveal if your Connect subscription includes WebSocket access")
print()

connection_result = {"connected": False, "ticks_received": False, "error": None}

def on_connect(ws, response):
    print("✅ WebSocket CONNECTED!")
    print(f"   Response: {response}")
    connection_result["connected"] = True

def on_close(ws, code, reason):
    print(f"⚠️  WebSocket closed: code={code}, reason={reason if reason else 'N/A'}")

def on_error(ws, code, reason):
    error_msg = f"WebSocket error: code={code}, reason={reason if reason else 'N/A'}"
    print(f"❌ {error_msg}")
    connection_result["error"] = error_msg
    
    # Check for subscription-related errors
    if reason and ('subscription' in str(reason).lower() or 'connect' in str(reason).lower()):
        print("\n⚠️  This error suggests:")
        print("   - You may need Zerodha Connect subscription (₹500/month)")
        print("   - Check: https://kite.trade/app/console/")

def on_ticks(ws, ticks):
    print(f"\n✅✅✅ RECEIVED TICK DATA! ✅✅✅")
    print(f"   WebSocket is WORKING! Your subscription includes WebSocket access!")
    print(f"   Ticks received: {len(ticks)}")
    if ticks:
        first_tick = ticks[0]
        print(f"   Sample tick data:")
        for key, value in first_tick.items():
            print(f"      {key}: {value}")
    connection_result["ticks_received"] = True

try:
    kws.on_connect = on_connect
    kws.on_close = on_close
    kws.on_error = on_error
    kws.on_ticks = on_ticks
    
    print("📡 Connecting to WebSocket first...")
    kws.connect(threaded=True)
    
    # Wait a moment for connection
    time.sleep(2)
    
    print("📡 Subscribing to instrument...")
    kws.subscribe([test_token])
    kws.set_mode(kws.MODE_LTP, [test_token])
    
    # Wait for connection and ticks
    print("⏳ Waiting for connection and tick data (15 seconds)...")
    for i in range(15):
        time.sleep(1)
        if connection_result["ticks_received"]:
            break
        if connection_result["error"] and "subscription" in str(connection_result["error"]).lower():
            break
        print(".", end="", flush=True)
    
    print()  # New line after dots
    
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

# Final Result
print("\n" + "="*70)
print("FINAL RESULT")
print("="*70)

if connection_result["ticks_received"]:
    print("✅✅✅ SUCCESS! ✅✅✅")
    print("   Your Zerodha Connect subscription INCLUDES WebSocket access!")
    print("   WebSocket is working perfectly!")
    print("   You can use WebSocketPriceFeed for live trading!")
elif connection_result["connected"]:
    print("⚠️  WebSocket connected but no ticks received")
    print("   Possible reasons:")
    print("   - Market is closed (WebSocket only sends data during market hours)")
    print("   - Instrument not trading")
    print("   - Try again during market hours (9:15 AM - 3:30 PM IST)")
elif connection_result["error"]:
    print("❌ WebSocket connection failed")
    print(f"   Error: {connection_result['error']}")
    if "subscription" in str(connection_result["error"]).lower():
        print("\n   ⚠️  This likely means:")
        print("   - You need Zerodha Connect subscription (₹500/month)")
        print("   - Check your subscription: https://kite.trade/app/console/")
else:
    print("⚠️  Connection timeout")
    print("   Possible reasons:")
    print("   - Market is closed")
    print("   - Network issue")
    print("   - Subscription issue")

print("="*70 + "\n")

