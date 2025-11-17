"""
Unit tests for MarginCalculator
"""

import unittest
from unittest.mock import Mock, MagicMock

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.trading_system.oms.margin_calculator import MarginCalculator
from src.trading_system.logging import ComponentLogger


class TestMarginCalculator(unittest.TestCase):
    """Test MarginCalculator functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_kite = Mock()
        self.mock_logger = ComponentLogger.get_logger("test")
        
        self.calculator = MarginCalculator(
            kite=self.mock_kite,
            logger=self.mock_logger
        )
    
    def test_check_available_margin(self):
        """Test getting available margin from broker"""
        # Mock broker response
        self.mock_kite.margins.return_value = {
            'equity': {
                'available': {
                    'live_balance': 100000.0
                }
            }
        }
        
        available = self.calculator.check_available_margin()
        
        self.assertEqual(available, 100000.0)
        self.mock_kite.margins.assert_called_once()
    
    def test_calculate_atm_strike(self):
        """Test ATM strike calculation"""
        test_cases = [
            (51000.0, 51000),
            (51050.0, 51100),
            (50950.0, 51000),
        ]
        
        for futures_price, expected in test_cases:
            with self.subTest(futures_price=futures_price):
                strike = self.calculator._calculate_atm_strike(futures_price)
                self.assertEqual(strike, expected)


if __name__ == '__main__':
    unittest.main()

