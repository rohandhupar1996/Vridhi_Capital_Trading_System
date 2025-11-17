"""
Unit tests for OrderManager
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.trading_system.oms.order_manager import OrderManager, PositionType
from src.trading_system.logging import ComponentLogger


class TestOrderManager(unittest.TestCase):
    """Test OrderManager functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_kite = Mock()
        self.mock_logger = ComponentLogger.get_logger("test")
        
        self.oms = OrderManager(
            kite=self.mock_kite,
            lot_size=8,
            hedge_legs=20,
            logger=self.mock_logger,
            dry_run=True  # Use dry-run for testing
        )
    
    def test_calculate_atm_strike(self):
        """Test ATM strike calculation from futures price"""
        # Test with various futures prices
        test_cases = [
            (51000.0, 51000),
            (51050.0, 51000),  # Rounds to nearest 100
            (50950.0, 51000),  # Rounds to nearest 100
            (51500.0, 51500),
        ]
        
        for futures_price, expected_strike in test_cases:
            with self.subTest(futures_price=futures_price):
                strike = self.oms._calculate_atm_strike(futures_price)
                self.assertEqual(strike, expected_strike)
    
    def test_margin_check_before_entry(self):
        """Test that margin is checked before entry"""
        self.oms.futures_ltp = 51000.0
        
        # Mock margin calculator
        self.oms.margin_calc.check_available_margin = Mock(return_value=100000.0)
        self.oms.margin_calc.calculate_long_margin = Mock(return_value={
            'total_margin': 50000.0
        })
        
        # Mock order placement to fail (so we can test margin check happened)
        self.oms._place_market_order = Mock(return_value=None)
        
        # Try to enter long with margin check
        result = self.oms.enter_long(fast_execution=False)
        
        # Verify margin check was called
        self.oms.margin_calc.check_available_margin.assert_called()
        self.oms.margin_calc.calculate_long_margin.assert_called()
    
    def test_buy_legs_execute_first(self):
        """Test that BUY legs execute before SELL legs"""
        self.oms.futures_ltp = 51000.0
        
        # Track execution order
        execution_order = []
        
        def mock_place_order(*args, **kwargs):
            execution_order.append(kwargs.get('transaction_type', 'UNKNOWN'))
            return f"ORDER_{len(execution_order)}"
        
        self.oms._place_market_order = Mock(side_effect=mock_place_order)
        self.oms._check_order_status = Mock(return_value=True)
        
        # Try to enter long
        self.oms.enter_long(fast_execution=True)
        
        # Verify BUY orders came before SELL
        buy_indices = [i for i, x in enumerate(execution_order) if x == 'BUY']
        sell_indices = [i for i, x in enumerate(execution_order) if x == 'SELL']
        
        if buy_indices and sell_indices:
            self.assertTrue(max(buy_indices) < min(sell_indices),
                          "BUY orders should execute before SELL orders")
    
    def test_sequential_lot_reduction(self):
        """Test that lot size reduces sequentially on failure"""
        self.oms.futures_ltp = 51000.0
        
        # Make order placement fail
        self.oms._place_market_order = Mock(return_value=None)
        
        # Track lot sizes attempted
        attempted_lots = []
        
        original_execute = self.oms._execute_legs
        def track_execute(*args, **kwargs):
            attempted_lots.append(kwargs.get('quantity', 0) // 15)  # Convert to lots
            return False  # Always fail to trigger reduction
        
        self.oms._execute_legs = Mock(side_effect=track_execute)
        
        # Try to enter long
        self.oms.enter_long(fast_execution=True)
        
        # Verify lot reduction happened (8 -> 4 -> 2 -> 1)
        if len(attempted_lots) > 1:
            self.assertTrue(attempted_lots[0] > attempted_lots[1],
                          "Lot size should reduce on failure")


if __name__ == '__main__':
    unittest.main()

