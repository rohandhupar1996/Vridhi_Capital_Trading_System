"""
Orchestrator - The Brain
Routes events, enforces priorities and SLAs, owns global runbook
Approves actions from sub-agents against hard policies
"""

from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

from .event_bus import EventBus, Event, EventType, EventPriority, get_event_bus
from .shared_state import SharedState, get_shared_state
from ..logging import ComponentLogger


@dataclass
class Policy:
    """Hard policy rule"""
    name: str
    condition: Callable[[Event], bool]
    action: str  # "block", "warn", "degrade", "allow"
    priority: EventPriority


class Orchestrator:
    """
    Central orchestrator - the brain of the system
    Routes events, enforces policies, coordinates agents
    """
    
    def __init__(self, logger: Optional[ComponentLogger] = None):
        self.logger = logger or ComponentLogger.get_logger("orchestrator")
        self.event_bus = get_event_bus()
        self.shared_state = get_shared_state()
        
        # Policies
        self.policies: List[Policy] = []
        self._setup_policies()
        
        # Agent registry
        self.agents: Dict[str, Any] = {}
        
        # SLA tracking
        self.sla_metrics: Dict[str, Dict] = {}
        
        # Subscribe to all events
        self.event_bus.subscribe(EventType.AUTH_FAILED, self._handle_auth_failed)
        self.event_bus.subscribe(EventType.CONNECTION_DROPPED, self._handle_connection_dropped)
        self.event_bus.subscribe(EventType.RISK_LIMIT_BREACH, self._handle_risk_breach)
        self.event_bus.subscribe(EventType.ORDER_REJECTED, self._handle_order_rejected)
        self.event_bus.subscribe(EventType.AGENT_UNHEALTHY, self._handle_agent_unhealthy)
    
    def _setup_policies(self):
        """Setup hard policies"""
        # Policy: Never trade if margin insufficient
        self.policies.append(Policy(
            name="margin_check",
            condition=lambda e: e.event_type == EventType.MARGIN_INSUFFICIENT,
            action="block",
            priority=EventPriority.CRITICAL
        ))
        
        # Policy: Never trade if circuit breaker active
        self.policies.append(Policy(
            name="circuit_breaker",
            condition=lambda e: self.shared_state.get("read_only_mode", False),
            action="block",
            priority=EventPriority.CRITICAL
        ))
        
        # Policy: Never trade if earnings blocked
        self.policies.append(Policy(
            name="earnings_block",
            condition=lambda e: self.shared_state.get("earnings_blocked", False),
            action="block",
            priority=EventPriority.HIGH
        ))
    
    def register_agent(self, name: str, agent: Any):
        """Register an agent with the orchestrator"""
        self.agents[name] = agent
        self.logger.info(f"Agent registered: {name}")
    
    def approve_action(self, action_type: str, agent_name: str, data: Dict) -> bool:
        """Approve action from agent against hard policies"""
        # Check all policies
        for policy in self.policies:
            # Create mock event for policy check
            mock_event = Event(
                event_type=EventType.SYSTEM_START,  # Placeholder
                priority=EventPriority.NORMAL,
                timestamp=datetime.now(),
                source=agent_name,
                data=data
            )
            
            if policy.condition(mock_event):
                if policy.action == "block":
                    self.logger.warning(
                        f"Action blocked by policy: {policy.name}",
                        agent=agent_name,
                        action=action_type
                    )
                    return False
        
        return True
    
    def _handle_auth_failed(self, event: Event):
        """Handle authentication failure"""
        self.logger.error("Authentication failed - triggering recovery")
        self.shared_state.set("auth_status", "failed")
        # Trigger recovery agent
    
    def _handle_connection_dropped(self, event: Event):
        """Handle connection drop"""
        self.logger.warning("Connection dropped - triggering reconnection")
        self.shared_state.set("websocket_connected", False)
        # Trigger reconnection
    
    def _handle_risk_breach(self, event: Event):
        """Handle risk limit breach"""
        self.logger.critical("Risk limit breached - activating circuit breaker")
        self.shared_state.set("read_only_mode", True)
        self.shared_state.set("trading_enabled", False)
        # Trigger circuit breaker
    
    def _handle_order_rejected(self, event: Event):
        """Handle order rejection"""
        self.logger.warning("Order rejected", data=event.data)
        # May trigger lot reduction or stop trading
    
    def _handle_agent_unhealthy(self, event: Event):
        """Handle agent health issue"""
        self.logger.error(f"Agent unhealthy: {event.source}")
        # Trigger health recovery
    
    def start(self):
        """Start the orchestrator"""
        self.logger.info("Orchestrator started")
        self.event_bus.publish(Event(
            event_type=EventType.SYSTEM_START,
            priority=EventPriority.CRITICAL,
            timestamp=datetime.now(),
            source="orchestrator",
            data={}
        ))
    
    def stop(self):
        """Stop the orchestrator"""
        self.logger.info("Orchestrator stopped")
        self.event_bus.publish(Event(
            event_type=EventType.SYSTEM_STOP,
            priority=EventPriority.CRITICAL,
            timestamp=datetime.now(),
            source="orchestrator",
            data={}
        ))

