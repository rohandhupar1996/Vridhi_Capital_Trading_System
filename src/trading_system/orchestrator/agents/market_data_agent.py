"""
Market Data Agent
Subscribes to BN futures only; validates tokens/ltp > 0
Restarts streams on stalls; fills gaps from REST; time-skews detection
"""

from typing import Optional
from datetime import datetime, timedelta
import time

from ..event_bus import EventBus, Event, EventType, EventPriority, get_event_bus
from ..shared_state import SharedState, get_shared_state
from ...logging import ComponentLogger
from ...oms.websocket_price_feed import WebSocketPriceFeed


class MarketDataAgent:
    """
    Manages market data streams
    Monitors WebSocket, detects stalls, handles gaps
    """
    
    def __init__(
        self,
        kite,
        futures_token: int,
        order_manager,
        orchestrator,
        logger: Optional[ComponentLogger] = None
    ):
        self.kite = kite
        self.futures_token = futures_token
        self.order_manager = order_manager
        self.orchestrator = orchestrator
        self.logger = logger or ComponentLogger.get_logger("market_data_agent")
        
        self.event_bus = get_event_bus()
        self.shared_state = get_shared_state()
        
        self.price_feed = WebSocketPriceFeed(
            kite=kite,
            futures_token=futures_token,
            order_manager=order_manager,
            logger=self.logger
        )
        
        self._last_tick_time: Optional[datetime] = None
        self._stall_threshold = timedelta(seconds=10)  # 10 seconds = stall
        self._gap_threshold = timedelta(seconds=5)  # 5 seconds = gap
    
    def on_tick(self, ws, ticks: list):
        """Handle tick data from WebSocket"""
        for tick in ticks:
            current_time = datetime.now()
            
            # Validate tick
            if not self._validate_tick(tick):
                continue
            
            # Update state
            price = tick.get('last_price')
            if price and price > 0:
                self.shared_state.set("futures_ltp", price)
                self.shared_state.set("last_tick_time", current_time)
                self.shared_state.set("websocket_connected", True)
                
                # Publish event
                self.event_bus.publish(Event(
                    event_type=EventType.TICK_RECEIVED,
                    priority=EventPriority.NORMAL,
                    timestamp=current_time,
                    source="market_data_agent",
                    data={"price": price, "token": tick.get('instrument_token')}
                ))
                
                # Check for gaps
                if self._last_tick_time:
                    gap = current_time - self._last_tick_time
                    if gap > self._gap_threshold:
                        self.logger.warning(f"Data gap detected: {gap.total_seconds()}s")
                        self.event_bus.publish(Event(
                            event_type=EventType.DATA_GAP_DETECTED,
                            priority=EventPriority.HIGH,
                            timestamp=current_time,
                            source="market_data_agent",
                            data={"gap_seconds": gap.total_seconds()}
                        ))
                
                self._last_tick_time = current_time
    
    def _validate_tick(self, tick: dict) -> bool:
        """Validate tick data"""
        # Check token matches
        if tick.get('instrument_token') != self.futures_token:
            return False
        
        # Check price is valid
        price = tick.get('last_price')
        if not price or price <= 0:
            return False
        
        return True
    
    def check_stream_health(self):
        """Check if stream is healthy"""
        last_tick = self.shared_state.get("last_tick_time")
        if not last_tick:
            return True  # Not started yet
        
        now = datetime.now()
        gap = now - last_tick
        
        if gap > self._stall_threshold:
            self.logger.warning(f"Stream stalled: {gap.total_seconds()}s since last tick")
            self.event_bus.publish(Event(
                event_type=EventType.STREAM_STALLED,
                priority=EventPriority.HIGH,
                timestamp=now,
                source="market_data_agent",
                data={"stall_seconds": gap.total_seconds()}
            ))
            
            # Try to restart
            self.restart_stream()
            return False
        
        return True
    
    def restart_stream(self):
        """Restart WebSocket stream"""
        self.logger.info("Restarting WebSocket stream")
        self.price_feed.stop()
        time.sleep(1)
        self.price_feed.start()
    
    def fill_gap_from_rest(self):
        """Fill data gap using REST API"""
        try:
            # Get latest quote from REST
            quote = self.kite.quote(f"NFO:{self.order_manager.futures_symbol}")
            price = quote.get('last_price')
            
            if price and price > 0:
                self.shared_state.set("futures_ltp", price)
                self.logger.info(f"Gap filled from REST: {price}")
        except Exception as e:
            self.logger.error(f"Failed to fill gap from REST: {e}")
    
    def start(self):
        """Start market data agent"""
        self.logger.info("Market Data Agent started")
        
        # Start WebSocket (callbacks already set in WebSocketPriceFeed)
        if self.price_feed.start():
            self.shared_state.set("websocket_connected", True)
            # Override on_ticks to add our processing
            if self.price_feed.kws:
                original_on_ticks = self.price_feed.kws.on_ticks
                def wrapped_on_ticks(ws, ticks):
                    # Call original handler (updates OMS)
                    if original_on_ticks:
                        original_on_ticks(ws, ticks)
                    # Then our processing
                    self.on_tick(ws, ticks)
                self.price_feed.kws.on_ticks = wrapped_on_ticks
        else:
            self.logger.error("Failed to start WebSocket")
    
    def stop(self):
        """Stop market data agent"""
        self.logger.info("Market Data Agent stopped")
        self.price_feed.stop()

