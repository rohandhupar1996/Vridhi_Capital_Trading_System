"""
Zerodha Automated Login Script
Handles login, token management, and connection monitoring
"""

from __future__ import annotations

import os
import sys
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
from src.trading_system.broker.oauth_callback_server import OAuthCallbackServer
from src.trading_system.config import AppConfig
from src.trading_system.logging import setup_logging, ComponentLogger


def main():
    """Main login flow"""
    print("=" * 70)
    print("ZERODHA AUTOMATED LOGIN SYSTEM")
    print("=" * 70)
    print()
    
    # Setup logging
    setup_logging(log_dir=PROJECT_ROOT / "logs")
    logger = ComponentLogger.get_logger("zerodha_login")
    
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
    
    # Check connection health
    print("\n🔍 Checking connection health...")
    health = authenticator.check_connection_health()
    print(f"  WiFi:           {'✅' if health.wifi else '❌'}")
    print(f"  Zerodha API:    {'✅' if health.zerodha_api else '❌'}")
    print(f"  Trading System: {'✅' if health.trading_system else '❌'}")
    
    if health.error_message:
        print(f"\n⚠️  {health.error_message}")
        return
    
    # Try to login
    print("\n🔐 Attempting login...")
    
    # Check if we have a valid token
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
    print("📱 Setting up automated token capture...")
    
    # Start OAuth callback server
    callback_server = OAuthCallbackServer(port=8080, timeout=120)
    if not callback_server.start():
        print("❌ Failed to start callback server. Falling back to manual entry.")
        callback_server = None
    else:
        callback_url = callback_server.get_callback_url()
        print(f"✅ Callback server started on {callback_url}")
        print("   (This will automatically capture your request_token)\n")
    
    # Generate login URL
    print("🌐 Generating login URL...")
    login_url = authenticator.get_login_url()
    print(f"\n📋 Login URL: {login_url}\n")
    
    # Open browser automatically
    import webbrowser
    webbrowser.open(login_url)
    print("✅ Browser opened automatically")
    
    if callback_server:
        print("\n⏳ Waiting for you to complete login in browser...")
        print("   (The script will automatically capture the token)")
        print("   You can close this window after login completes.\n")
        
        try:
            # Wait for callback
            request_token = callback_server.wait_for_callback()
            
            if request_token:
                print(f"✅ Request token captured automatically!")
                print(f"   Token: {request_token[:20]}...")
            else:
                print("⏱️  Timeout waiting for callback. Please enter token manually:")
                request_token = input("\n   Enter request_token: ").strip()
        except Exception as e:
            print(f"⚠️  Error capturing token automatically: {e}")
            print("   Please enter token manually:")
            request_token = input("\n   Enter request_token: ").strip()
        finally:
            callback_server.stop()
    else:
        # Manual entry fallback
        print("\n📝 After logging in, you'll be redirected to a URL with 'request_token'")
        print("   Copy the request_token from the URL and enter it below:")
        request_token = input("\n   Enter request_token: ").strip()
    
    if not request_token:
        print("❌ No request_token provided")
        return
    
    # Authenticate with request token
    print("\n🔄 Authenticating with request token...")
    if authenticator.authenticate_with_token(request_token):
        print("✅ Login successful!")
        
        # Save request token for future use
        print(f"\n💾 Saving request token to configs/.env...")
        print("   (You can add ZERODHA_REQUEST_TOKEN=your_token to configs/.env for auto-reconnect)")
        
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
    
    # Setup connection monitor
    print("\n📡 Setting up connection monitor...")
    monitor = ConnectionMonitor(
        authenticator=authenticator,
        check_interval=app_config.zerodha.connection_check_interval,
        logger=ComponentLogger.get_logger("connection_monitor")
    )
    
    # Test connection monitoring
    print("\n🔍 Testing connection monitoring...")
    status = monitor.get_status_report()
    print(f"  Connection Status: {status['connection_status']}")
    print(f"  Token Valid:       {'✅' if status['token_valid'] else '❌'}")
    print(f"  WiFi:              {'✅' if status['wifi'] else '❌'}")
    print(f"  Zerodha API:       {'✅' if status['zerodha_api'] else '❌'}")
    
    print("\n" + "=" * 70)
    print("✅ SETUP COMPLETE!")
    print("=" * 70)
    print("\n📌 Next steps:")
    print("   1. The connection monitor will automatically check connection health")
    print("   2. If connection drops, it will attempt to reconnect using saved token")
    print("   3. Check logs/ directory for detailed component-wise logs")
    print("   4. Authentication events are logged in logs/authentication.log")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Exiting...")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


