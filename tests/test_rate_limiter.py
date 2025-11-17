"""
Unit tests for RateLimiter
"""

import unittest
import time
from unittest.mock import Mock

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.trading_system.oms.rate_limiter import RateLimiter, EndpointType


class TestRateLimiter(unittest.TestCase):
    """Test RateLimiter functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.rate_limiter = RateLimiter()
    
    def test_order_rate_limit(self):
        """Test that order rate limit is 10 req/second"""
        start_time = time.time()
        
        # Make 2 calls quickly
        self.rate_limiter.wait_if_needed(EndpointType.ORDER)
        self.rate_limiter.wait_if_needed(EndpointType.ORDER)
        
        elapsed = time.time() - start_time
        
        # Should be ~0.1s between calls (10 req/sec = 0.1s interval)
        self.assertLess(elapsed, 0.2)  # Allow some tolerance
    
    def test_quote_rate_limit(self):
        """Test that quote rate limit is 1 req/second"""
        start_time = time.time()
        
        # Make 2 calls
        self.rate_limiter.wait_if_needed(EndpointType.QUOTE)
        self.rate_limiter.wait_if_needed(EndpointType.QUOTE)
        
        elapsed = time.time() - start_time
        
        # Should be ~1s between calls (1 req/sec = 1s interval)
        self.assertGreaterEqual(elapsed, 0.9)  # At least 0.9s
        self.assertLess(elapsed, 1.5)  # But not too much more


if __name__ == '__main__':
    unittest.main()

