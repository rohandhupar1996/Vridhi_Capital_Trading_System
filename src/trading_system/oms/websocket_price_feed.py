"""
WebSocket Price Feed for Live Trading
Subscribes to Zerodha tick feed and updates OrderManager with real-time prices

IMPORTANT: WebSocket requires Zerodha Connect subscription (₹500/month)
- Free Personal API does NOT include market data/WebSocket
- Connect subscription includes: WebSocket tick feed + historical data
- See: https://zerodha.com/products/api/
"""

from typing import Dict, List, Optional, Callable
from kiteconnect import KiteTicker
from ..logging import ComponentLogger


class WebSocketPriceFeed:
    """
    Manages WebSocket connection to Zerodha tick feed for real-time price updates.
    
    For live trading, this provides tick-by-tick price updates without rate limits.
    Prices are automatically pushed to subscribed callbacks.
    """
    
    def __init__(
        self,
        kite,
        futures_token: int,
        order_manager,
        logger: Optional[ComponentLogger] = None
    ):
        """
        Initialize WebSocket price feed.
        
        Args:
            kite: Authenticated KiteConnect instance
            futures_token: Instrument token for BankNifty futures contract
            order_manager: OrderManager instance to update with prices
            logger: Optional logger instance
        """
        self.kite = kite
        self.futures_token = futures_token
        self.order_manager = order_manager
        self.logger = logger or ComponentLogger.get_logger("websocket_price_feed")
        
        # Initialize KiteTicker (WebSocket client)
        self.kws: Optional[KiteTicker] = None
        self.is_connected = False
        
    def start(self) -> bool:
        """
        Start WebSocket connection and subscribe to futures tick feed.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Get access token from kite instance
            access_token = self.kite.access_token
            
            # Initialize KiteTicker with API key and access token
            self.kws = KiteTicker(
                api_key=self.kite.api_key,
                access_token=access_token
            )
            
            # Set up callbacks
            self.kws.on_ticks = self._on_ticks
            self.kws.on_connect = self._on_connect
            self.kws.on_close = self._on_close
            self.kws.on_error = self._on_error
            
            # Start WebSocket connection FIRST (non-blocking)
            self.kws.connect(threaded=True)
            
            # Wait a moment for connection to establish
            import time
            time.sleep(1)
            
            # Then subscribe to futures contract (LTP mode for price updates)
            self.kws.subscribe([self.futures_token])
            self.kws.set_mode(self.kws.MODE_LTP, [self.futures_token])
            
            self.logger.info(
                "WebSocket connection initiated",
                futures_token=self.futures_token
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start WebSocket: {e}", exc_info=True)
            return False
    
    def stop(self) -> None:
        """Stop WebSocket connection and unsubscribe."""
        if self.kws:
            try:
                self.kws.unsubscribe([self.futures_token])
                self.kws.close()
                self.is_connected = False
                self.logger.info("WebSocket connection closed")
            except Exception as e:
                self.logger.error(f"Error closing WebSocket: {e}")
    
    def _on_connect(self, ws, response):
        """Callback when WebSocket connects."""
        self.is_connected = True
        self.logger.info(
            "WebSocket connected",
            response=response
        )
    
    def _on_close(self, ws, code, reason):
        """Callback when WebSocket closes."""
        self.is_connected = False
        self.logger.warning(
            "WebSocket closed",
            code=code,
            reason=reason
        )
    
    def _on_error(self, ws, code, reason):
        """Callback when WebSocket error occurs."""
        self.logger.error(
            "WebSocket error",
            code=code,
            reason=reason
        )
    
    def _on_ticks(self, ws, ticks: List[Dict]):
        """
        Callback when tick data arrives.
        Updates OrderManager with latest futures price.
        
        Args:
            ws: WebSocket instance
            ticks: List of tick dictionaries from Zerodha
        """
        for tick in ticks:
            # Only process ticks for our futures contract
            if tick.get('instrument_token') == self.futures_token:
                # Update OrderManager with latest price
                self.order_manager.update_futures_price(tick)
                
                # Log price update (debug level to avoid spam)
                price = tick.get('last_price')
                if price:
                    self.logger.debug(
                        "Futures price updated from tick",
                        price=price,
                        token=self.futures_token
                    )


# Example usage for live trading:
"""
from src.trading_system.oms.order_manager import OrderManager
from src.trading_system.oms.websocket_price_feed import WebSocketPriceFeed

# Initialize OMS
oms = OrderManager(kite=kite, lot_size=8, ...)

# Get futures token
futures_token = oms._get_futures_token()

# Start WebSocket feed
price_feed = WebSocketPriceFeed(
    kite=kite,
    futures_token=futures_token,
    order_manager=oms
)

# Connect and start receiving ticks
if price_feed.start():
    print("✅ WebSocket connected - receiving real-time prices")
    
    # Now prices will automatically update in oms.futures_ltp
    # No need to call kite.quote() anymore!
    
    # ... rest of trading logic ...
    
    # When done, stop the feed
    price_feed.stop()
"""

