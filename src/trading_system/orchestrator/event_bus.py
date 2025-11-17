"""
Event Bus - Central event routing system
Routes events between agents, enforces priorities and SLAs
"""

from typing import Dict, List, Callable, Optional, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
import queue


class EventType(Enum):
    """Event types in the system"""
    # Auth/Connection events
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILED = "auth_failed"
    TOKEN_EXPIRED = "token_expired"
    CONNECTION_DROPPED = "connection_dropped"
    CONNECTION_RESTORED = "connection_restored"
    
    # Market Data events
    TICK_RECEIVED = "tick_received"
    STREAM_STALLED = "stream_stalled"
    DATA_GAP_DETECTED = "data_gap_detected"
    
    # Signal events
    SIGNAL_GENERATED = "signal_generated"
    SIGNAL_FLICKER = "signal_flicker"
    SIGNAL_REVERSAL = "signal_reversal"
    
    # Risk/Policy events
    MARGIN_CHECK = "margin_check"
    MARGIN_INSUFFICIENT = "margin_insufficient"
    RISK_LIMIT_BREACH = "risk_limit_breach"
    CIRCUIT_BREAKER = "circuit_breaker"
    
    # OMS/Execution events
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    ORDER_REJECTED = "order_rejected"
    POSITION_ENTERED = "position_entered"
    POSITION_EXITED = "position_exited"
    
    # Health events
    AGENT_HEALTHY = "agent_healthy"
    AGENT_UNHEALTHY = "agent_unhealthy"
    RECOVERY_STARTED = "recovery_started"
    RECOVERY_COMPLETE = "recovery_complete"
    
    # System events
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    SYSTEM_ERROR = "system_error"


class EventPriority(Enum):
    """Event priority levels"""
    CRITICAL = 1  # Immediate action required
    HIGH = 2      # Urgent
    NORMAL = 3    # Standard
    LOW = 4       # Background


@dataclass
class Event:
    """Event structure"""
    event_type: EventType
    priority: EventPriority
    timestamp: datetime
    source: str  # Agent name
    data: Dict[str, Any]
    correlation_id: Optional[str] = None


class EventBus:
    """
    Central event bus for routing events between agents
    Enforces priorities and SLAs
    """
    
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._priority_queue = queue.PriorityQueue()
        self._lock = Lock()
        self._event_history: List[Event] = []
        self._max_history = 1000
    
    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]):
        """Subscribe to an event type"""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(handler)
    
    def publish(self, event: Event):
        """Publish an event to the bus"""
        with self._lock:
            # Add to history
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history.pop(0)
            
            # Add to priority queue
            priority_value = event.priority.value
            self._priority_queue.put((priority_value, event.timestamp.timestamp(), event))
            
            # Notify subscribers immediately
            if event.event_type in self._subscribers:
                for handler in self._subscribers[event.event_type]:
                    try:
                        handler(event)
                    except Exception as e:
                        # Log error but don't break event bus
                        print(f"Error in event handler: {e}")
    
    def get_event_history(self, event_type: Optional[EventType] = None, limit: int = 100) -> List[Event]:
        """Get event history, optionally filtered by type"""
        with self._lock:
            if event_type:
                filtered = [e for e in self._event_history if e.event_type == event_type]
                return filtered[-limit:]
            return self._event_history[-limit:]


# Global event bus instance
_global_event_bus = EventBus()


def get_event_bus() -> EventBus:
    """Get the global event bus instance"""
    return _global_event_bus

