"""
Zerodha Authentication and Connection Management
Handles automated login, token refresh, and connection monitoring
"""

from __future__ import annotations

import json
import time
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional

import requests
from kiteconnect import KiteConnect

from ..logging import ComponentLogger


class ConnectionStatus(Enum):
    """Connection status enumeration"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class ZerodhaCredentials:
    """Zerodha API credentials"""
    api_key: str
    api_secret: str
    request_token: Optional[str] = None
    access_token: Optional[str] = None
    token_expiry: Optional[datetime] = None


@dataclass
class ConnectionHealth:
    """Connection health status"""
    wifi: bool = False
    zerodha_api: bool = False
    trading_system: bool = False
    last_check: Optional[datetime] = None
    error_message: Optional[str] = None


class ZerodhaAuthenticator:
    """
    Automated Zerodha authentication with token management and reconnection
    """
    
    def __init__(
        self,
        credentials: ZerodhaCredentials,
        token_file: Path | str = "configs/zerodha_tokens.json",
        logger: Optional[ComponentLogger] = None
    ):
        self.credentials = credentials
        self.token_file = Path(token_file)
        self.logger = logger or ComponentLogger("zerodha_auth")
        
        self.kite: Optional[KiteConnect] = None
        self.connection_status = ConnectionStatus.DISCONNECTED
        self.health = ConnectionHealth()
        
        # Load saved tokens if available
        self._load_tokens()
    
    def _load_tokens(self) -> None:
        """Load saved access token from file"""
        if not self.token_file.exists():
            return
        
        try:
            with open(self.token_file, 'r') as f:
                data = json.load(f)
                self.credentials.access_token = data.get('access_token')
                expiry_str = data.get('token_expiry')
                if expiry_str:
                    self.credentials.token_expiry = datetime.fromisoformat(expiry_str)
            
            self.logger.info("Loaded saved access token from file")

            # If we have an access token and API key, initialize KiteConnect instance
            if self.credentials.access_token and self.credentials.api_key:
                try:
                    self.kite = KiteConnect(api_key=self.credentials.api_key)
                    self.kite.set_access_token(self.credentials.access_token)
                    self.logger.info("Initialized KiteConnect with saved access token")
                except Exception as e:
                    self.logger.error(f"Failed to initialize KiteConnect with saved token: {e}")
        except Exception as e:
            self.logger.error(f"Failed to load tokens: {e}")
    
    def _save_tokens(self) -> None:
        """Save access token to file"""
        try:
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                'access_token': self.credentials.access_token,
                'token_expiry': self.credentials.token_expiry.isoformat() if self.credentials.token_expiry else None
            }
            with open(self.token_file, 'w') as f:
                json.dump(data, f, indent=2)
            self.logger.info("Saved access token to file")
        except Exception as e:
            self.logger.error(f"Failed to save tokens: {e}")
    
    def _check_wifi_connection(self) -> bool:
        """Check if WiFi/internet connection is available"""
        try:
            response = requests.get("https://www.google.com", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def _check_zerodha_api(self) -> bool:
        """Check if Zerodha API is reachable"""
        try:
            response = requests.get("https://kite.zerodha.com", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def _check_trading_system(self) -> bool:
        """Check if trading system is running"""
        # This can be extended to check internal system health
        return True
    
    def check_connection_health(self) -> ConnectionHealth:
        """Check health of all connections"""
        self.health.wifi = self._check_wifi_connection()
        self.health.zerodha_api = self._check_zerodha_api()
        self.health.trading_system = self._check_trading_system()
        self.health.last_check = datetime.now()
        
        if not self.health.wifi:
            self.health.error_message = "WiFi/Internet connection unavailable"
        elif not self.health.zerodha_api:
            self.health.error_message = "Zerodha API unreachable"
        elif not self.health.trading_system:
            self.health.error_message = "Trading system not running"
        else:
            self.health.error_message = None
        
        return self.health
    
    def get_login_url(self, redirect_url: Optional[str] = None) -> str:
        """
        Generate login URL for Zerodha
        
        Args:
            redirect_url: Optional custom redirect URL (defaults to KiteConnect default)
            
        Returns:
            Login URL
        """
        if not self.kite:
            self.kite = KiteConnect(api_key=self.credentials.api_key)
        
        if redirect_url:
            # Note: KiteConnect doesn't directly support custom redirect_url in login_url()
            # But we can use it if needed for callback server
            login_url = self.kite.login_url()
            # Append redirect_url if provided (Zerodha may support this)
            if redirect_url and 'redirect_url' not in login_url:
                separator = '&' if '?' in login_url else '?'
                login_url = f"{login_url}{separator}redirect_url={redirect_url}"
        else:
            login_url = self.kite.login_url()
        
        self.logger.info(f"Generated login URL: {login_url}")
        return login_url
    
    def authenticate_with_token(self, request_token: str) -> bool:
        """
        Authenticate using request token
        
        Args:
            request_token: Request token from Zerodha login
            
        Returns:
            True if authentication successful
        """
        try:
            if not self.kite:
                self.kite = KiteConnect(api_key=self.credentials.api_key)
            
            data = self.kite.generate_session(
                request_token=request_token,
                api_secret=self.credentials.api_secret
            )
            
            self.credentials.access_token = data['access_token']
            self.credentials.token_expiry = datetime.now() + timedelta(days=1)  # Tokens typically valid for 1 day
            
            self.kite.set_access_token(self.credentials.access_token)
            self._save_tokens()
            
            self.connection_status = ConnectionStatus.CONNECTED
            self.logger.info("Successfully authenticated with Zerodha")
            return True
            
        except Exception as e:
            self.connection_status = ConnectionStatus.ERROR
            self.logger.error(f"Authentication failed: {e}")
            return False
    
    def is_token_valid(self) -> bool:
        """Check if current access token is still valid"""
        if not self.credentials.access_token or not self.kite:
            return False
        
        if self.credentials.token_expiry and datetime.now() >= self.credentials.token_expiry:
            return False
        
        try:
            # Try a simple API call to verify token
            self.kite.profile()
            return True
        except Exception:
            return False
    
    def reconnect(self) -> bool:
        """Attempt to reconnect using saved token or request new authentication"""
        self.connection_status = ConnectionStatus.RECONNECTING
        self.logger.info("Attempting to reconnect...")
        
        # Check connection health first
        health = self.check_connection_health()
        if not health.wifi:
            self.logger.error("Cannot reconnect: WiFi/Internet unavailable")
            return False
        
        if not health.zerodha_api:
            self.logger.error("Cannot reconnect: Zerodha API unreachable")
            return False
        
        # Try using existing token first
        if self.credentials.access_token and self.is_token_valid():
            self.connection_status = ConnectionStatus.CONNECTED
            self.logger.info("Reconnected using existing token")
            return True
        
        # If token invalid, need new request token
        if self.credentials.request_token:
            if self.authenticate_with_token(self.credentials.request_token):
                return True
        
        self.logger.warning("Reconnection failed: Need new request token")
        return False
    
    def login(self, auto_open_browser: bool = True) -> bool:
        """
        Perform complete login flow
        
        Args:
            auto_open_browser: Automatically open browser for login
            
        Returns:
            True if login successful
        """
        # Check connection health
        health = self.check_connection_health()
        if not health.wifi:
            self.logger.error("Login failed: WiFi/Internet unavailable")
            return False
        
        if not health.zerodha_api:
            self.logger.error("Login failed: Zerodha API unreachable")
            return False
        
        # Try using existing token first
        if self.is_token_valid():
            self.connection_status = ConnectionStatus.CONNECTED
            self.logger.info("Already authenticated with valid token")
            return True
        
        # Generate login URL
        login_url = self.get_login_url()
        
        if auto_open_browser:
            self.logger.info("Opening browser for Zerodha login...")
            webbrowser.open(login_url)
            self.logger.info("Please complete login in browser and provide request token")
        
        return False
    
    def get_kite_instance(self) -> Optional[KiteConnect]:
        """Get authenticated KiteConnect instance"""
        if self.connection_status == ConnectionStatus.CONNECTED and self.kite:
            return self.kite
        return None


class ConnectionMonitor:
    """
    Monitors connection health and automatically reconnects
    """
    
    def __init__(
        self,
        authenticator: ZerodhaAuthenticator,
        check_interval: int = 30,  # seconds
        logger: Optional[ComponentLogger] = None
    ):
        self.authenticator = authenticator
        self.check_interval = check_interval
        self.logger = logger or ComponentLogger("connection_monitor")
        self.monitoring = False
        self._last_health_check = None
    
    def start_monitoring(self) -> None:
        """Start background connection monitoring"""
        self.monitoring = True
        self.logger.info(f"Started connection monitoring (interval: {self.check_interval}s)")
        
        # In a real implementation, this would run in a background thread
        # For now, we'll provide a manual check method
    
    def stop_monitoring(self) -> None:
        """Stop background connection monitoring"""
        self.monitoring = False
        self.logger.info("Stopped connection monitoring")
    
    def check_and_reconnect(self) -> bool:
        """
        Check connection health and attempt reconnection if needed
        
        Returns:
            True if connection is healthy
        """
        health = self.authenticator.check_connection_health()
        self._last_health_check = health.last_check
        
        if health.error_message:
            self.logger.warning(f"Connection issue detected: {health.error_message}")
            
            # Attempt reconnection
            if self.authenticator.connection_status != ConnectionStatus.CONNECTED:
                return self.authenticator.reconnect()
        
        return self.authenticator.connection_status == ConnectionStatus.CONNECTED
    
    def get_status_report(self) -> dict:
        """Get detailed status report"""
        health = self.authenticator.check_connection_health()
        
        return {
            'connection_status': self.authenticator.connection_status.value,
            'wifi': health.wifi,
            'zerodha_api': health.zerodha_api,
            'trading_system': health.trading_system,
            'token_valid': self.authenticator.is_token_valid(),
            'last_check': health.last_check.isoformat() if health.last_check else None,
            'error_message': health.error_message
        }

