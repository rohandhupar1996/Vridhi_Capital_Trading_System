"""
Rate Limiter for Zerodha API calls
Implements rate limits based on Zerodha's API documentation:
- Quote: 1 req/second
- Historical candle: 3 req/second
- Order placement: 10 req/second
- All other endpoints: 10 req/second
"""

import time
from typing import Dict, Optional
from threading import Lock
from enum import Enum


class EndpointType(Enum):
    """API endpoint types with their rate limits"""
    QUOTE = "quote"  # 1 req/second
    HISTORICAL = "historical"  # 3 req/second
    ORDER = "order"  # 10 req/second
    OTHER = "other"  # 10 req/second


class RateLimiter:
    """
    Thread-safe rate limiter for Zerodha API calls.
    Uses token bucket algorithm with per-endpoint tracking.
    """
    
    # Rate limits per endpoint (requests per second)
    RATE_LIMITS: Dict[EndpointType, float] = {
        EndpointType.QUOTE: 1.0,  # 1 req/second
        EndpointType.HISTORICAL: 3.0,  # 3 req/second
        EndpointType.ORDER: 10.0,  # 10 req/second
        EndpointType.OTHER: 10.0,  # 10 req/second
    }
    
    def __init__(self):
        self._locks: Dict[EndpointType, Lock] = {
            endpoint: Lock() for endpoint in EndpointType
        }
        self._last_call_times: Dict[EndpointType, float] = {
            endpoint: 0.0 for endpoint in EndpointType
        }
    
    def wait_if_needed(self, endpoint: EndpointType) -> None:
        """
        Wait if necessary to respect rate limits for the given endpoint.
        
        Args:
            endpoint: Type of API endpoint being called
        """
        with self._locks[endpoint]:
            rate_limit = self.RATE_LIMITS[endpoint]
            min_interval = 1.0 / rate_limit  # Minimum seconds between requests
            
            current_time = time.time()
            last_call_time = self._last_call_times[endpoint]
            time_since_last_call = current_time - last_call_time
            
            if time_since_last_call < min_interval:
                sleep_time = min_interval - time_since_last_call
                time.sleep(sleep_time)
            
            self._last_call_times[endpoint] = time.time()
    
    def reset(self, endpoint: Optional[EndpointType] = None) -> None:
        """
        Reset rate limiter for a specific endpoint or all endpoints.
        
        Args:
            endpoint: Endpoint to reset, or None to reset all
        """
        if endpoint:
            with self._locks[endpoint]:
                self._last_call_times[endpoint] = 0.0
        else:
            for ep in EndpointType:
                with self._locks[ep]:
                    self._last_call_times[ep] = 0.0


# Global rate limiter instance
_global_rate_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance"""
    return _global_rate_limiter

