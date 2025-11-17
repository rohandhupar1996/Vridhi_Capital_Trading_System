"""
Fully Automated Zerodha Login
Attempts to automatically capture request_token from redirect URL
Works by monitoring clipboard or using callback server (if configured)
"""

from __future__ import annotations

import os
import sys
import time
import webbrowser
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_PATH):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from dotenv import load_dotenv
from src.trading_system.broker import ZerodhaAuthenticator, ConnectionMonitor
from src.trading_system.broker.zerodha_auth import ZerodhaCredentials
from src.trading_system.config import AppConfig
from src.trading_system.logging import setup_logging, ComponentLogger


def monitor_clipboard_for_token(timeout: int = 120) -> str | None:
    """
    Monitor clipboard for request_token
    Looks for URLs containing 'request_token='
    """
    try:
        import pyperclip
    except ImportError:
        print("⚠️  pyperclip not installed. Install with: pip install pyperclip")
        print("   Falling back to manual entry...")
        return None
    
    print("📋 Monitoring clipboard for request_token...")
    print("   (After login, copy the redirect URL from browser address bar)")
    print("   The script will automatically detect it.\n")
    
    start_time = time.time()
    last_clipboard = ""
    
    while time.time() - start_time < timeout:
        try:
            current_clipboard = pyperclip.paste()
            
            # Check if clipboard changed and contains request_token
            if current_clipboard != last_clipboard and 'request_token=' in current_clipboard:
                # Extract token from URL
                from urllib.parse import urlparse, parse_qs
                try:
                    # Try parsing as URL
                    parsed = urlparse(current_clipboard)
                    params = parse_qs(parsed.query)
                    token = params.get('request_token', [None])[0]
                    
                    if token:
                        print(f"✅ Token detected in clipboard!")
                        return token
                except:
                    # Try extracting directly
                    import re
                    match = re.search(r'request_token=([^&\s]+)', current_clipboard)
                    if match:
                        token = match.group(1)
                        print(f"✅ Token detected in clipboard!")
                        return token
            
            last_clipboard = current_clipboard
            time.sleep(0.5)  # Check every 0.5 seconds
            
        except Exception as e:
            print(f"⚠️  Clipboard monitoring error: {e}")
            return None
    
    return None


def main():
    """Main automated login flow"""
    print("=" * 70)
    print("ZERODHA AUTOMATED LOGIN (WITH AUTO-TOKEN CAPTURE)")
    print("=" * 70)
    print()
    
    # Setup logging
    setup_logging(log_dir=PROJECT_ROOT / "logs")
    logger = ComponentLogger.get_logger("zerodha_login_auto")
    
    # Load configuration
    app_config = AppConfig()
    
    # Load credentials from .env
    env_path = PROJECT_ROOT / "configs" / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"Loaded credentials from {env_path}")
    
    api_key = os.getenv("ZERODHA_API_KEY") or app_config.zerodha.api_key
    api_secret = os.getenv("ZERODHA_API_SECRET") or app_config.zerodha.api_secret
    
    if not api_key or not api_secret:
        print("❌ Error: ZERODHA_API_KEY and ZERODHA_API_SECRET must be set")
        print("   Add them to configs/.env file:")
        print("   ZERODHA_API_KEY=your_api_key")
        print("   ZERODHA_API_SECRET=your_api_secret")
        return
    
    # Create credentials
    credentials = ZerodhaCredentials(
        api_key=api_key,
        api_secret=api_secret,
        request_token=os.getenv("ZERODHA_REQUEST_TOKEN")
    )
    
    # Create authenticator
    token_file = app_config.resolve_path(app_config.zerodha.token_file)
    authenticator = ZerodhaAuthenticator(
        credentials=credentials,
        token_file=token_file,
        logger=ComponentLogger.get_logger("zerodha_auth")
    )
    
    # Check if already logged in
    if authenticator.is_token_valid():
        print("✅ Already authenticated with valid token")
        kite = authenticator.get_kite_instance()
        if kite:
            try:
                profile = kite.profile()
                print(f"   Logged in as: {profile.get('user_name', 'N/A')}")
            except Exception as e:
                logger.error(f"Failed to get profile: {e}")
        return
    
    # Need new login
    print("\n📱 Generating login URL...")
    login_url = authenticator.get_login_url()
    
    print(f"\n🌐 Login URL:")
    print(f"   {login_url}\n")
    
    # Open browser
    print("🚀 Opening browser...")
    webbrowser.open(login_url)
    print("✅ Browser opened")
    
    # Try clipboard monitoring
    print("\n" + "="*70)
    print("AUTOMATED TOKEN CAPTURE")
    print("="*70)
    print("\n📋 Method 1: Clipboard Monitoring (Recommended)")
    print("   1. Complete login in browser")
    print("   2. After redirect, copy the ENTIRE URL from browser address bar")
    print("   3. The script will automatically detect the token")
    print("\n   (Waiting for clipboard to contain request_token...)\n")
    
    request_token = monitor_clipboard_for_token(timeout=120)
    
    if not request_token:
        print("\n⏱️  Clipboard monitoring timeout or not available")
        print("="*70)
        print("MANUAL ENTRY")
        print("="*70)
        print("\n📝 Please enter the request_token manually:")
        print("   1. After login, you'll be redirected to a URL")
        print("   2. The URL will contain: request_token=XXXXX")
        print("   3. Copy just the token value (the XXXXX part)\n")
        
        request_token = input("   Enter request_token: ").strip()
    
    if not request_token:
        print("❌ No request_token provided")
        return
    
    # Authenticate
    print(f"\n🔄 Authenticating with token: {request_token[:20]}...")
    if authenticator.authenticate_with_token(request_token):
        print("✅ Login successful!")
        
        kite = authenticator.get_kite_instance()
        if kite:
            try:
                profile = kite.profile()
                print(f"\n👤 Logged in as: {profile.get('user_name', 'N/A')}")
                print(f"   User ID: {profile.get('user_id', 'N/A')}")
            except Exception as e:
                logger.error(f"Failed to get profile: {e}")
    else:
        print("❌ Login failed. Please check your credentials and try again.")
        return
    
    print("\n" + "=" * 70)
    print("✅ SETUP COMPLETE!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Exiting...")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

