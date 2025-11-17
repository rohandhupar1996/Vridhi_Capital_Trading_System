"""
Auth/Connection Agent
Monitors Wi-Fi, Zerodha API, token validity
Auto refreshes tokens, retries with backoff, switches to read-only when degraded
"""

from typing import Optional
from datetime import datetime, timedelta
import time
import requests

from ..event_bus import EventBus, Event, EventType, EventPriority, get_event_bus
from ..shared_state import SharedState, get_shared_state
from ...logging import ComponentLogger
from ...broker.zerodha_auth import ZerodhaAuthenticator, ZerodhaCredentials


class AuthConnectionAgent:
    """
    Monitors and manages authentication and connections
    Auto-refreshes tokens, handles failures gracefully
    """
    
    def __init__(
        self,
        credentials: ZerodhaCredentials,
        token_file: str,
        orchestrator,
        logger: Optional[ComponentLogger] = None
    ):
        self.credentials = credentials
        self.token_file = token_file
        self.orchestrator = orchestrator
        self.logger = logger or ComponentLogger.get_logger("auth_agent")
        
        self.event_bus = get_event_bus()
        self.shared_state = get_shared_state()
        
        self.authenticator = ZerodhaAuthenticator(
            credentials=credentials,
            token_file=token_file,
            logger=self.logger
        )
        
        self._retry_count = 0
        self._max_retries = 3
        self._backoff_base = 2  # Exponential backoff
    
    def check_wifi(self) -> bool:
        """Check Wi-Fi/internet connection"""
        try:
            response = requests.get("https://www.google.com", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def check_zerodha_api(self) -> bool:
        """Check if Zerodha API is reachable"""
        try:
            response = requests.get("https://kite.zerodha.com", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def check_token_validity(self) -> bool:
        """Check if current token is valid"""
        try:
            kite = self.authenticator.get_kite()
            if not kite:
                return False
            
            # Try to get profile (validates token)
            profile = kite.profile()
            return profile is not None
        except:
            return False
    
    def refresh_token(self) -> bool:
        """Refresh access token with exponential backoff"""
        if self._retry_count >= self._max_retries:
            self.logger.error("Max retries reached for token refresh")
            self.event_bus.publish(Event(
                event_type=EventType.AUTH_FAILED,
                priority=EventPriority.CRITICAL,
                timestamp=datetime.now(),
                source="auth_agent",
                data={"retry_count": self._retry_count}
            ))
            return False
        
        try:
            # Exponential backoff
            wait_time = self._backoff_base ** self._retry_count
            time.sleep(wait_time)
            
            success = self.authenticator.login(auto_open_browser=False)
            
            if success:
                self._retry_count = 0
                self.shared_state.set("auth_status", "connected")
                self.event_bus.publish(Event(
                    event_type=EventType.AUTH_SUCCESS,
                    priority=EventPriority.HIGH,
                    timestamp=datetime.now(),
                    source="auth_agent",
                    data={}
                ))
                return True
            else:
                self._retry_count += 1
                return False
                
        except Exception as e:
            self.logger.error(f"Token refresh error: {e}")
            self._retry_count += 1
            return False
    
    def monitor(self):
        """Monitor connections and token validity"""
        # Check Wi-Fi
        wifi_ok = self.check_wifi()
        if not wifi_ok:
            self.logger.warning("Wi-Fi connection lost")
            self.shared_state.set("read_only_mode", True)
            return
        
        # Check Zerodha API
        api_ok = self.check_zerodha_api()
        if not api_ok:
            self.logger.warning("Zerodha API unreachable")
            self.shared_state.set("read_only_mode", True)
            return
        
        # Check token
        token_ok = self.check_token_validity()
        if not token_ok:
            self.logger.warning("Token invalid or expired - refreshing")
            if self.refresh_token():
                self.shared_state.set("read_only_mode", False)
            else:
                self.shared_state.set("read_only_mode", True)
        else:
            self.shared_state.set("auth_status", "connected")
            self.shared_state.set("read_only_mode", False)
    
    def start(self):
        """Start monitoring"""
        self.logger.info("Auth/Connection Agent started")
        # Initial check
        self.monitor()
    
    def stop(self):
        """Stop monitoring"""
        self.logger.info("Auth/Connection Agent stopped")

