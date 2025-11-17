"""
Convert Request Token to Access Token
If you have a request_token from the login URL, this will convert it to access_token
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
from kiteconnect import KiteConnect

print("\n" + "="*70)
print("CONVERT REQUEST TOKEN TO ACCESS TOKEN")
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

# Get token from user
print("\nEnter the token you received:")
print("(This could be a request_token from login URL, or an access_token)")
token = input("Token: ").strip()

if not token:
    print("❌ No token provided")
    sys.exit(1)

# Try to use it as access_token first
print("\n" + "-"*70)
print("TESTING AS ACCESS TOKEN")
print("-"*70)

try:
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(token)
    profile = kite.profile()
    print("✅ Token is a VALID ACCESS TOKEN!")
    print(f"   User ID: {profile.get('user_id', 'N/A')}")
    print(f"   User Name: {profile.get('user_name', 'N/A')}")
    
    # Save it
    token_file = PROJECT_ROOT / "configs" / "zerodha_tokens.json"
    token_data = {
        "access_token": token,
        "token_expiry": "2025-11-18T00:00:00"
    }
    with open(token_file, 'w') as f:
        json.dump(token_data, f, indent=2)
    print(f"\n✅ Access token saved to {token_file}")
    print("\nNow you can test WebSocket:")
    print("   python scripts/test_websocket_direct.py")
    sys.exit(0)
    
except Exception as e:
    print(f"❌ Not a valid access token: {e}")
    print("\nTrying as request_token...")

# Try to convert it as request_token
print("\n" + "-"*70)
print("TESTING AS REQUEST TOKEN")
print("-"*70)

try:
    kite = KiteConnect(api_key=api_key)
    data = kite.generate_session(token, api_secret=api_secret)
    access_token = data['access_token']
    
    print("✅ Successfully converted request_token to access_token!")
    print(f"   Access Token: {access_token[:20]}...")
    
    # Verify it works
    kite.set_access_token(access_token)
    profile = kite.profile()
    print(f"   User ID: {profile.get('user_id', 'N/A')}")
    print(f"   User Name: {profile.get('user_name', 'N/A')}")
    
    # Save it
    token_file = PROJECT_ROOT / "configs" / "zerodha_tokens.json"
    token_data = {
        "access_token": access_token,
        "token_expiry": "2025-11-18T00:00:00"
    }
    with open(token_file, 'w') as f:
        json.dump(token_data, f, indent=2)
    print(f"\n✅ Access token saved to {token_file}")
    print("\nNow you can test WebSocket:")
    print("   python scripts/test_websocket_direct.py")
    sys.exit(0)
    
except Exception as e:
    print(f"❌ Failed to convert request_token: {e}")
    print("\n⚠️  The token you provided might be:")
    print("   - Invalid or expired")
    print("   - Not a request_token or access_token")
    print("   - From a different API key")
    print("\nTo get a valid token:")
    print("   1. Run: python scripts/zerodha_login.py")
    print("   2. Complete login in browser")
    print("   3. Copy the request_token from the redirect URL")
    sys.exit(1)

