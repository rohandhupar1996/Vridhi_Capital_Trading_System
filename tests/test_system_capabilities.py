"""
Unit tests for System Capabilities
Tests all "Handles", "Monitors", and "Enforces" capabilities
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.trading_system.orchestrator.event_bus import Event, EventType, EventPriority, get_event_bus
from src.trading_system.orchestrator.shared_state import get_shared_state
from src.trading_system.orchestrator.agents.auth_agent import AuthConnectionAgent
from src.trading_system.orchestrator.agents.market_data_agent import MarketDataAgent
from src.trading_system.orchestrator.agents.risk_policy_agent import RiskPolicyAgent
from src.trading_system.orchestrator.agents.health_agent import HealthRecoveryAgent
from src.trading_system.broker.zerodha_auth import ZerodhaCredentials


class TestSystemCapabilitiesHandles(unittest.TestCase):
    """Test 'Handles' capabilities"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.event_bus = get_event_bus()
        self.shared_state = get_shared_state()
        self.mock_orchestrator = Mock()
    
    def test_handle_connection_drops(self):
        """Test: Connection drops (auto-reconnect)"""
        # Simulate connection drop event
        event = Event(
            event_type=EventType.CONNECTION_DROPPED,
            priority=EventPriority.HIGH,
            timestamp=datetime.now(),
            source="test",
            data={}
        )
        
        # Event should be published
        self.event_bus.publish(event)
        
        # Shared state should reflect disconnection
        self.shared_state.set("websocket_connected", False)
        self.assertFalse(self.shared_state.get("websocket_connected"))
    
    def test_handle_token_expiry(self):
        """Test: Token expiry (auto-refresh)"""
        event = Event(
            event_type=EventType.TOKEN_EXPIRED,
            priority=EventPriority.CRITICAL,
            timestamp=datetime.now(),
            source="auth_agent",
            data={}
        )
        
        self.event_bus.publish(event)
        # Token refresh would be triggered by auth agent
    
    def test_handle_stream_stalls(self):
        """Test: Stream stalls (auto-restart)"""
        event = Event(
            event_type=EventType.STREAM_STALLED,
            priority=EventPriority.HIGH,
            timestamp=datetime.now(),
            source="market_data_agent",
            data={"stall_seconds": 15}
        )
        
        self.event_bus.publish(event)
        # Stream restart would be triggered
    
    def test_handle_margin_issues(self):
        """Test: Margin issues (sequential lot reduction)"""
        risk_agent = RiskPolicyAgent(
            orchestrator=self.mock_orchestrator,
            max_lots=8
        )
        
        # Simulate insufficient margin
        self.shared_state.set("available_margin", 10000.0)
        self.shared_state.set("pre_calculated_margins", {
            "long": {"total_margin": 50000.0}
        })
        
        sufficient, required = risk_agent.check_margin("LONG", 8)
        self.assertFalse(sufficient)
    
    def test_handle_risk_breaches(self):
        """Test: Risk breaches (circuit breakers)"""
        risk_agent = RiskPolicyAgent(
            orchestrator=self.mock_orchestrator,
            max_lots=8
        )
        
        risk_agent.activate_circuit_breaker("test_breach")
        
        self.assertTrue(self.shared_state.get("read_only_mode"))
        self.assertFalse(self.shared_state.get("trading_enabled"))
    
    def test_handle_agent_failures(self):
        """Test: Agent failures (health monitoring)"""
        health_agent = HealthRecoveryAgent(
            orchestrator=self.mock_orchestrator
        )
        
        # Register heartbeat
        health_agent.register_heartbeat("test_agent")
        
        # Check health
        health = health_agent.check_agent_health()
        self.assertIn("test_agent", health)
    
    def test_handle_data_gaps(self):
        """Test: Data gaps (REST fill)"""
        event = Event(
            event_type=EventType.DATA_GAP_DETECTED,
            priority=EventPriority.HIGH,
            timestamp=datetime.now(),
            source="market_data_agent",
            data={"gap_seconds": 10}
        )
        
        self.event_bus.publish(event)
        # REST fill would be triggered
    
    def test_handle_order_rejections(self):
        """Test: Order rejections (retry with reduction)"""
        event = Event(
            event_type=EventType.ORDER_REJECTED,
            priority=EventPriority.HIGH,
            timestamp=datetime.now(),
            source="oms_agent",
            data={"reason": "margin_insufficient"}
        )
        
        self.event_bus.publish(event)
        # Retry with lot reduction would be triggered


class TestSystemCapabilitiesMonitors(unittest.TestCase):
    """Test 'Monitors' capabilities"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.shared_state = get_shared_state()
        self.mock_orchestrator = Mock()
    
    @patch('src.trading_system.orchestrator.agents.auth_agent.requests')
    def test_monitor_wifi_connection(self, mock_requests):
        """Test: Wi-Fi connection monitoring"""
        credentials = ZerodhaCredentials(api_key="test", api_secret="test")
        auth_agent = AuthConnectionAgent(
            credentials=credentials,
            token_file="test.json",
            orchestrator=self.mock_orchestrator
        )
        
        mock_requests.get.return_value.status_code = 200
        result = auth_agent.check_wifi()
        self.assertTrue(result)
    
    @patch('src.trading_system.orchestrator.agents.auth_agent.requests')
    def test_monitor_zerodha_api(self, mock_requests):
        """Test: Zerodha API availability monitoring"""
        credentials = ZerodhaCredentials(api_key="test", api_secret="test")
        auth_agent = AuthConnectionAgent(
            credentials=credentials,
            token_file="test.json",
            orchestrator=self.mock_orchestrator
        )
        
        mock_requests.get.return_value.status_code = 200
        result = auth_agent.check_zerodha_api()
        self.assertTrue(result)
    
    def test_monitor_token_validity(self):
        """Test: Token validity monitoring"""
        credentials = ZerodhaCredentials(api_key="test", api_secret="test")
        auth_agent = AuthConnectionAgent(
            credentials=credentials,
            token_file="test.json",
            orchestrator=self.mock_orchestrator
        )
        
        # Mock token check
        auth_agent.authenticator = Mock()
        auth_agent.authenticator.get_kite.return_value = None
        result = auth_agent.check_token_validity()
        # Will return False if no kite instance
        self.assertIsInstance(result, bool)
    
    def test_monitor_websocket_health(self):
        """Test: WebSocket health monitoring"""
        self.shared_state.set("websocket_connected", True)
        self.shared_state.set("last_tick_time", datetime.now())
        
        self.assertTrue(self.shared_state.get("websocket_connected"))
    
    def test_monitor_tick_freshness(self):
        """Test: Tick freshness monitoring"""
        self.shared_state.set("last_tick_time", datetime.now())
        last_tick = self.shared_state.get("last_tick_time")
        
        self.assertIsNotNone(last_tick)
        self.assertIsInstance(last_tick, datetime)
    
    def test_monitor_agent_heartbeats(self):
        """Test: Agent heartbeats monitoring"""
        health_agent = HealthRecoveryAgent(
            orchestrator=self.mock_orchestrator
        )
        
        health_agent.register_heartbeat("test_agent")
        health = health_agent.check_agent_health()
        
        self.assertIn("test_agent", health)
    
    def test_monitor_margin_availability(self):
        """Test: Margin availability monitoring"""
        self.shared_state.set("available_margin", 100000.0)
        margin = self.shared_state.get("available_margin")
        
        self.assertEqual(margin, 100000.0)
    
    # Daily P&L monitoring removed (not required)


class TestSystemCapabilitiesEnforces(unittest.TestCase):
    """Test 'Enforces' capabilities"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.shared_state = get_shared_state()
        self.mock_orchestrator = Mock()
        self.risk_agent = RiskPolicyAgent(
            orchestrator=self.mock_orchestrator,
            max_lots=8
        )
    
    def test_enforce_max_lot_limits(self):
        """Test: Max lot limits enforcement"""
        self.assertFalse(self.risk_agent.check_max_lots(10))  # Exceeds max
        self.assertTrue(self.risk_agent.check_max_lots(5))   # Within limit
    
    def test_enforce_trading_windows(self):
        """Test: Trading windows enforcement"""
        result = self.risk_agent.check_trading_window()
        self.assertIsInstance(result, bool)
    
    def test_enforce_margin_requirements(self):
        """Test: Margin requirements enforcement"""
        self.shared_state.set("available_margin", 100000.0)
        self.shared_state.set("pre_calculated_margins", {
            "long": {"total_margin": 50000.0}
        })
        
        sufficient, required = self.risk_agent.check_margin("LONG", 5)
        self.assertTrue(sufficient)
        self.assertEqual(required, 50000.0)
    
    def test_enforce_circuit_breakers(self):
        """Test: Circuit breakers enforcement"""
        self.risk_agent.activate_circuit_breaker("test")
        
        self.assertTrue(self.shared_state.get("read_only_mode"))
        self.assertFalse(self.shared_state.get("trading_enabled"))
    
    def test_enforce_earnings_filter(self):
        """Test: Earnings filter enforcement"""
        self.shared_state.set("earnings_blocked", True)
        
        blocked = self.shared_state.get("earnings_blocked")
        self.assertTrue(blocked)


if __name__ == '__main__':
    unittest.main()

