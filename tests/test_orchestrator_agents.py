"""
Unit tests for all Orchestrator Agents
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.trading_system.orchestrator.agents.auth_agent import AuthConnectionAgent
from src.trading_system.orchestrator.agents.risk_policy_agent import RiskPolicyAgent
from src.trading_system.orchestrator.agents.health_agent import HealthRecoveryAgent
from src.trading_system.orchestrator.agents.oms_execution_agent import OMSExecutionAgent
from src.trading_system.orchestrator.event_bus import EventType
from src.trading_system.orchestrator.shared_state import get_shared_state
from src.trading_system.broker.zerodha_auth import ZerodhaCredentials


class TestAuthAgent(unittest.TestCase):
    """Test Auth/Connection Agent"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_orchestrator = Mock()
        self.credentials = ZerodhaCredentials(
            api_key="test_key",
            api_secret="test_secret"
        )
        self.agent = AuthConnectionAgent(
            credentials=self.credentials,
            token_file="test_tokens.json",
            orchestrator=self.mock_orchestrator
        )
    
    @patch('src.trading_system.orchestrator.agents.auth_agent.requests')
    def test_check_wifi(self, mock_requests):
        """Test Wi-Fi connection check"""
        mock_requests.get.return_value.status_code = 200
        result = self.agent.check_wifi()
        self.assertTrue(result)
    
    @patch('src.trading_system.orchestrator.agents.auth_agent.requests')
    def test_check_zerodha_api(self, mock_requests):
        """Test Zerodha API check"""
        mock_requests.get.return_value.status_code = 200
        result = self.agent.check_zerodha_api()
        self.assertTrue(result)


class TestRiskAgent(unittest.TestCase):
    """Test Risk/Policy Agent"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_orchestrator = Mock()
        self.agent = RiskPolicyAgent(
            orchestrator=self.mock_orchestrator,
            max_lots=8
        )
        self.shared_state = get_shared_state()
    
    def test_check_max_lots(self):
        """Test max lots check"""
        self.assertTrue(self.agent.check_max_lots(5))
        self.assertFalse(self.agent.check_max_lots(10))
    
    def test_activate_circuit_breaker(self):
        """Test circuit breaker activation"""
        self.agent.activate_circuit_breaker("test_reason")
        
        self.assertTrue(self.shared_state.get("read_only_mode"))
        self.assertFalse(self.shared_state.get("trading_enabled"))
    
    def test_approve_trade(self):
        """Test trade approval"""
        self.shared_state.set("read_only_mode", False)
        self.shared_state.set("available_margin", 100000.0)
        self.shared_state.set("pre_calculated_margins", {
            "long": {"total_margin": 50000.0}
        })
        
        approved = self.agent.approve_trade("LONG", 5)
        self.assertTrue(approved)


class TestHealthAgent(unittest.TestCase):
    """Test Health/Recovery Agent"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_orchestrator = Mock()
        self.agent = HealthRecoveryAgent(
            orchestrator=self.mock_orchestrator
        )
    
    def test_register_heartbeat(self):
        """Test heartbeat registration"""
        self.agent.register_heartbeat("test_agent")
        
        self.assertIn("test_agent", self.agent._agent_heartbeats)
    
    def test_check_agent_health(self):
        """Test agent health check"""
        self.agent.register_heartbeat("test_agent")
        
        health = self.agent.check_agent_health()
        self.assertIn("test_agent", health)
        self.assertTrue(health["test_agent"])
    
    def test_detect_wedges(self):
        """Test wedge detection"""
        shared_state = get_shared_state()
        shared_state.set("last_tick_time", datetime.now() - timedelta(seconds=40))
        
        wedges = self.agent.detect_wedges()
        self.assertIn("no_ticks", wedges)


class TestOMSExecutionAgent(unittest.TestCase):
    """Test OMS/Execution Agent"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_orchestrator = Mock()
        self.mock_oms = Mock()
        self.agent = OMSExecutionAgent(
            order_manager=self.mock_oms,
            orchestrator=self.mock_orchestrator
        )
    
    def test_enter_long_with_approval(self):
        """Test enter long with orchestrator approval"""
        self.mock_orchestrator.approve_action.return_value = True
        self.mock_oms.enter_long.return_value = True
        
        result = self.agent.enter_long()
        
        self.assertTrue(result)
        self.mock_orchestrator.approve_action.assert_called_once()
        self.mock_oms.enter_long.assert_called_once()


if __name__ == '__main__':
    unittest.main()

