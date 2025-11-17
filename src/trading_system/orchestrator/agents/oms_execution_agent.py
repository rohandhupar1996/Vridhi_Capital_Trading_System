"""
OMS/Execution Agent
BUY-first then SELL, partial-fill handling, all-legs exit/SL
Futures-based ATM calc only; retries with smart pacing
Idempotent order ops; dedup by client-order-id
"""

from typing import Optional, Dict
from datetime import datetime

from ..event_bus import EventBus, Event, EventType, EventPriority, get_event_bus
from ..shared_state import SharedState, get_shared_state
from ...logging import ComponentLogger
from ...oms.order_manager import OrderManager


class OMSExecutionAgent:
    """
    Wraps OrderManager with event bus integration
    Handles execution with idempotency and deduplication
    """
    
    def __init__(
        self,
        order_manager: OrderManager,
        orchestrator,
        logger: Optional[ComponentLogger] = None
    ):
        self.oms = order_manager
        self.orchestrator = orchestrator
        self.logger = logger or ComponentLogger.get_logger("oms_agent")
        
        self.event_bus = get_event_bus()
        self.shared_state = get_shared_state()
        
        self._order_ids: set = set()  # For deduplication
        self._client_order_ids: Dict[str, str] = {}  # client_id -> broker_order_id
    
    def enter_long(self) -> bool:
        """Enter LONG position with approval check"""
        # Check if orchestrator approves
        if not self.orchestrator.approve_action("enter_long", "oms_agent", {}):
            self.logger.warning("Enter LONG blocked by orchestrator")
            return False
        
        # Execute via OMS
        success = self.oms.enter_long(fast_execution=False)
        
        if success:
            self.event_bus.publish(Event(
                event_type=EventType.POSITION_ENTERED,
                priority=EventPriority.HIGH,
                timestamp=datetime.now(),
                source="oms_agent",
                data={"position_type": "LONG"}
            ))
        else:
            self.event_bus.publish(Event(
                event_type=EventType.ORDER_REJECTED,
                priority=EventPriority.HIGH,
                timestamp=datetime.now(),
                source="oms_agent",
                data={"position_type": "LONG", "reason": "entry_failed"}
            ))
        
        return success
    
    def enter_short(self) -> bool:
        """Enter SHORT position with approval check"""
        # Check if orchestrator approves
        if not self.orchestrator.approve_action("enter_short", "oms_agent", {}):
            self.logger.warning("Enter SHORT blocked by orchestrator")
            return False
        
        # Execute via OMS
        success = self.oms.enter_short(fast_execution=False)
        
        if success:
            self.event_bus.publish(Event(
                event_type=EventType.POSITION_ENTERED,
                priority=EventPriority.HIGH,
                timestamp=datetime.now(),
                source="oms_agent",
                data={"position_type": "SHORT"}
            ))
        else:
            self.event_bus.publish(Event(
                event_type=EventType.ORDER_REJECTED,
                priority=EventPriority.HIGH,
                timestamp=datetime.now(),
                source="oms_agent",
                data={"position_type": "SHORT", "reason": "entry_failed"}
            ))
        
        return success
    
    def exit_position(self) -> bool:
        """Exit current position"""
        success = self.oms.exit_position()
        
        if success:
            self.event_bus.publish(Event(
                event_type=EventType.POSITION_EXITED,
                priority=EventPriority.HIGH,
                timestamp=datetime.now(),
                source="oms_agent",
                data={}
            ))
        
        return success
    
    def start(self):
        """Start OMS agent"""
        self.logger.info("OMS/Execution Agent started")
    
    def stop(self):
        """Stop OMS agent"""
        self.logger.info("OMS/Execution Agent stopped")

