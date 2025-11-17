"""
Integration test for live_trading.py
Tests that all components work together correctly
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestLiveTradingIntegration(unittest.TestCase):
    """Integration tests for live_trading.py"""
    
    @patch('src.trading_system.broker.zerodha_auth.ZerodhaAuthenticator')
    @patch('src.trading_system.oms.order_manager.OrderManager')
    @patch('src.trading_system.oms.websocket_price_feed.WebSocketPriceFeed')
    def test_live_trading_initialization(self, mock_ws, mock_oms, mock_auth):
        """Test that live_trading.py initializes all components correctly"""
        # Mock authentication
        mock_auth_instance = Mock()
        mock_auth_instance.login.return_value = True
        mock_auth_instance.get_kite.return_value = Mock()
        mock_auth.return_value = mock_auth_instance
        
        # Mock OMS
        mock_oms_instance = Mock()
        mock_oms_instance._get_futures_token.return_value = 12345
        mock_oms_instance.futures_ltp = 51000.0
        mock_oms.return_value = mock_oms_instance
        
        # Mock WebSocket
        mock_ws_instance = Mock()
        mock_ws_instance.start.return_value = True
        mock_ws_instance.is_connected = True
        mock_ws.return_value = mock_ws_instance
        
        # Import and test initialization
        from scripts.live_trading import main
        
        # This will test the initialization flow
        # (We'll mock the main loop to avoid infinite loop)
        with patch('scripts.live_trading.running', False):
            try:
                result = main()
                # If we get here, initialization worked
                self.assertTrue(True)
            except Exception as e:
                self.fail(f"Initialization failed: {e}")
    
    def test_component_integration(self):
        """Test that components integrate correctly"""
        # Test that OMS uses futures price correctly
        # Test that WebSocket updates OMS price
        # Test that executor uses OMS correctly
        pass  # Placeholder for more detailed integration tests


if __name__ == '__main__':
    unittest.main()

