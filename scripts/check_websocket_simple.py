"""
Simple WebSocket Access Check
Tests if KiteTicker can be initialized (doesn't require active connection)
"""

from __future__ import annotations

import sys
import json
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
import os

print("\n" + "="*70)
print("SIMPLE WEBSOCKET ACCESS CHECK")
print("="*70 + "\n")

# Test 1: Check if KiteTicker exists
print("TEST 1: KiteTicker Class Availability")
print("-"*70)
try:
    from kiteconnect import KiteTicker
    print("✅ KiteTicker class is available")
    print(f"   Class: {KiteTicker}")
    print(f"   Module: {KiteTicker.__module__}")
except ImportError as e:
    print(f"❌ KiteTicker not available: {e}")
    sys.exit(1)

# Test 2: Check credentials
print("\nTEST 2: Credentials Check")
print("-"*70)
env_path = PROJECT_ROOT / "configs" / ".env"
if env_path.exists():
    load_dotenv(env_path)
    api_key = os.getenv("ZERODHA_API_KEY")
    if api_key:
        print(f"✅ API Key found: {api_key[:10]}...")
    else:
        print("❌ API Key not found")
        sys.exit(1)
else:
    print(f"❌ Config file not found: {env_path}")
    sys.exit(1)

# Test 3: Check token file
print("\nTEST 3: Access Token Check")
print("-"*70)
token_file = PROJECT_ROOT / "configs" / "zerodha_tokens.json"
if token_file.exists():
    try:
        with open(token_file, 'r') as f:
            token_data = json.load(f)
            access_token = token_data.get('access_token')
            if access_token:
                print(f"✅ Access token found: {access_token[:20]}...")
                expiry = token_data.get('token_expiry')
                if expiry:
                    print(f"   Token expiry: {expiry}")
            else:
                print("⚠️  Access token not in file")
                print("   Run: python scripts/zerodha_login.py")
                sys.exit(1)
    except Exception as e:
        print(f"❌ Error reading token file: {e}")
        sys.exit(1)
else:
    print("⚠️  Token file not found")
    print("   Run: python scripts/zerodha_login.py")
    sys.exit(1)

# Test 4: Try to initialize KiteTicker
print("\nTEST 4: KiteTicker Initialization")
print("-"*70)
try:
    kws = KiteTicker(api_key=api_key, access_token=access_token)
    print("✅ KiteTicker initialized successfully!")
    print("   This means:")
    print("   - KiteTicker class is available")
    print("   - Your credentials are valid format")
    print("   - WebSocket client can be created")
    print("\n   ⚠️  Note: This doesn't verify subscription status")
    print("   To fully test WebSocket, you need:")
    print("   1. Active Connect subscription (₹500/month)")
    print("   2. Market hours (9:15 AM - 3:30 PM IST)")
    print("   3. Run full test: python scripts/test_websocket_access.py")
except Exception as e:
    print(f"❌ Failed to initialize KiteTicker: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Check available methods
print("\nTEST 5: KiteTicker Methods")
print("-"*70)
methods = [m for m in dir(kws) if not m.startswith('_') and callable(getattr(kws, m, None))]
important_methods = ['connect', 'subscribe', 'set_mode', 'close', 'unsubscribe']
for method in important_methods:
    if hasattr(kws, method):
        print(f"✅ {method}() method available")
    else:
        print(f"❌ {method}() method NOT found")

# Final summary
print("\n" + "="*70)
print("SUMMARY")
print("="*70)
print("✅ KiteTicker is available and can be initialized")
print("✅ Your setup supports WebSocket (if you have Connect subscription)")
print("\n📋 Next Steps:")
print("   1. Verify Connect subscription: https://kite.trade/app/console/")
print("   2. During market hours, run: python scripts/test_websocket_access.py")
print("   3. This will test actual WebSocket connection and tick data")
print("\n💡 Note: WebSocket only works:")
print("   - With Connect subscription (₹500/month)")
print("   - During market hours (9:15 AM - 3:30 PM IST)")
print("   - With valid access token")
print("="*70 + "\n")

