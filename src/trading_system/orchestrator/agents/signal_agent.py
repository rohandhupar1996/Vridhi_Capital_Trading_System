"""
Signal Agent
Runs models on the effective timeframe (expiry switch), running-candle updates
Applies earnings filter (block entries only), flicker cleanup, same-candle reversal intent
"""

from typing import Optional, Literal
from datetime import datetime

from ..event_bus import EventBus, Event, EventType, EventPriority, get_event_bus
from ..shared_state import SharedState, get_shared_state
from ...logging import ComponentLogger
from ...oms.running_signal_executor import RunningSignalExecutor
from ...oms.dynamic_timeframe import DynamicTimeframeController
from ...oms.earnings_filter import EarningsSeasonFilter


SignalType = Literal["LONG", "SHORT", "NONE"]


class SignalAgent:
    """
    Generates and processes trading signals
    Handles running-candle logic, flicker, reversals
    """
    
    def __init__(
        self,
        signal_executor: RunningSignalExecutor,
        timeframe_controller: DynamicTimeframeController,
        earnings_filter: EarningsSeasonFilter,
        orchestrator,
        logger: Optional[ComponentLogger] = None
    ):
        self.executor = signal_executor
        self.timeframe_controller = timeframe_controller
        self.earnings_filter = earnings_filter
        self.orchestrator = orchestrator
        self.logger = logger or ComponentLogger.get_logger("signal_agent")
        
        self.event_bus = get_event_bus()
        self.shared_state = get_shared_state()
    
    def generate_signal(self, data: Dict) -> SignalType:
        """
        Generate signal from market data
        TODO: Integrate your ML model here
        """
        # Placeholder - integrate your signal generation logic
        # For now, return NONE
        return "NONE"
    
    def process_signal(self, signal: SignalType, candle_id: str, futures_price: float):
        """Process signal through executor"""
        # Update effective timeframe
        effective_tf = self.timeframe_controller.get_effective_timeframe(datetime.now())
        self.shared_state.set("effective_timeframe", effective_tf)
        
        # Check earnings filter
        is_blocked = self.earnings_filter.is_blocked(datetime.now())
        self.shared_state.set("earnings_blocked", is_blocked)
        
        # Process through executor
        self.executor.on_running_signal(signal, candle_id, futures_price)
        
        # Publish event
        self.event_bus.publish(Event(
            event_type=EventType.SIGNAL_GENERATED,
            priority=EventPriority.NORMAL,
            timestamp=datetime.now(),
            source="signal_agent",
            data={"signal": signal, "candle_id": candle_id}
        ))
    
    def on_candle_close(self, final_signal: SignalType, candle_id: str, futures_price: float):
        """Handle candle close"""
        self.executor.on_candle_close(final_signal, candle_id, futures_price)
    
    def start(self):
        """Start signal agent"""
        self.logger.info("Signal Agent started")
    
    def stop(self):
        """Stop signal agent"""
        self.logger.info("Signal Agent stopped")

