"""
Unit tests for Orchestrator
"""

import unittest
from datetime import datetime
from unittest.mock import Mock

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.trading_system.orchestrator.orchestrator import Orchestrator
from src.trading_system.orchestrator.event_bus import Event, EventType, EventPriority
from src.trading_system.orchestrator.shared_state import get_shared_state


class TestOrchestrator(unittest.TestCase):
    """Test Orchestrator functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.orchestrator = Orchestrator()
        self.shared_state = get_shared_state()
    
    def test_register_agent(self):
        """Test agent registration"""
        mock_agent = Mock()
        self.orchestrator.register_agent("test_agent", mock_agent)
        
        self.assertIn("test_agent", self.orchestrator.agents)
        self.assertEqual(self.orchestrator.agents["test_agent"], mock_agent)
    
    def test_approve_action_with_policy(self):
        """Test action approval with policy enforcement"""
        # Set read_only_mode to block actions
        self.shared_state.set("read_only_mode", True)
        
        approved = self.orchestrator.approve_action(
            "enter_long",
            "test_agent",
            {}
        )
        
        self.assertFalse(approved)  # Should be blocked by circuit breaker policy
    
    def test_approve_action_allowed(self):
        """Test action approval when allowed"""
        self.shared_state.set("read_only_mode", False)
        self.shared_state.set("earnings_blocked", False)
        
        approved = self.orchestrator.approve_action(
            "enter_long",
            "test_agent",
            {}
        )
        
        self.assertTrue(approved)


if __name__ == '__main__':
    unittest.main()

