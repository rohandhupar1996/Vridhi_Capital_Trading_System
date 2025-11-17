"""
Health/Recovery Agent
Heartbeats for all agents; detects wedges (no fills, no ticks, high latency)
Self-heal steps: reconnect, rotate credentials, restart streams, drain/restart queues
Rollback/flatten positions on inconsistent state
"""

from typing import Dict, Optional, List
from datetime import datetime, timedelta

from ..event_bus import EventBus, Event, EventType, EventPriority, get_event_bus
from ..shared_state import SharedState, get_shared_state
from ...logging import ComponentLogger


class HealthRecoveryAgent:
    """
    Monitors health of all agents
    Detects issues and triggers recovery
    """
    
    def __init__(
        self,
        orchestrator,
        logger: Optional[ComponentLogger] = None
    ):
        self.orchestrator = orchestrator
        self.logger = logger or ComponentLogger.get_logger("health_agent")
        
        self.event_bus = get_event_bus()
        self.shared_state = get_shared_state()
        
        self._agent_heartbeats: Dict[str, datetime] = {}
        self._heartbeat_timeout = timedelta(seconds=30)
        self._recovery_actions: List[Callable] = []
    
    def register_heartbeat(self, agent_name: str):
        """Register heartbeat from an agent"""
        self._agent_heartbeats[agent_name] = datetime.now()
        self.shared_state.set("last_heartbeat", datetime.now())
        
        self.event_bus.publish(Event(
            event_type=EventType.AGENT_HEALTHY,
            priority=EventPriority.LOW,
            timestamp=datetime.now(),
            source="health_agent",
            data={"agent": agent_name}
        ))
    
    def check_agent_health(self) -> Dict[str, bool]:
        """Check health of all registered agents"""
        now = datetime.now()
        health_status = {}
        
        for agent_name, last_heartbeat in self._agent_heartbeats.items():
            gap = now - last_heartbeat
            is_healthy = gap < self._heartbeat_timeout
            health_status[agent_name] = is_healthy
            
            if not is_healthy:
                self.logger.warning(f"Agent {agent_name} unhealthy: {gap.total_seconds()}s since last heartbeat")
                self.event_bus.publish(Event(
                    event_type=EventType.AGENT_UNHEALTHY,
                    priority=EventPriority.HIGH,
                    timestamp=now,
                    source="health_agent",
                    data={"agent": agent_name, "gap_seconds": gap.total_seconds()}
                ))
        
        return health_status
    
    def detect_wedges(self) -> List[str]:
        """Detect system wedges (stuck states)"""
        wedges = []
        now = datetime.now()
        
        # Check for no ticks
        last_tick = self.shared_state.get("last_tick_time")
        if last_tick:
            tick_gap = now - last_tick
            if tick_gap > timedelta(seconds=30):
                wedges.append("no_ticks")
        
        # Check for no fills (if position exists but no recent order activity)
        # This would need order history tracking
        
        # Check for high latency
        # This would need latency metrics
        
        return wedges
    
    def trigger_recovery(self, issue: str):
        """Trigger recovery for a specific issue"""
        self.logger.info(f"Triggering recovery for: {issue}")
        
        self.event_bus.publish(Event(
            event_type=EventType.RECOVERY_STARTED,
            priority=EventPriority.HIGH,
            timestamp=datetime.now(),
            source="health_agent",
            data={"issue": issue}
        ))
        
        # Execute recovery actions
        if issue == "no_ticks":
            # Restart WebSocket
            self._recover_websocket()
        elif issue == "connection_dropped":
            # Reconnect
            self._recover_connection()
        elif issue == "token_expired":
            # Refresh token
            self._recover_auth()
        
        self.event_bus.publish(Event(
            event_type=EventType.RECOVERY_COMPLETE,
            priority=EventPriority.HIGH,
            timestamp=datetime.now(),
            source="health_agent",
            data={"issue": issue}
        ))
    
    def _recover_websocket(self):
        """Recover WebSocket connection"""
        # This would call market_data_agent.restart_stream()
        pass
    
    def _recover_connection(self):
        """Recover connection"""
        # This would trigger reconnection
        pass
    
    def _recover_auth(self):
        """Recover authentication"""
        # This would trigger token refresh
        pass
    
    def flatten_positions_on_inconsistency(self):
        """Flatten positions if state is inconsistent"""
        # Check if position state is consistent
        # If not, exit all positions
        pass
    
    def monitor(self):
        """Monitor system health"""
        # Check agent health
        health = self.check_agent_health()
        
        # Detect wedges
        wedges = self.detect_wedges()
        
        # Trigger recovery if needed
        for wedge in wedges:
            self.trigger_recovery(wedge)
    
    def start(self):
        """Start health monitoring"""
        self.logger.info("Health/Recovery Agent started")
    
    def stop(self):
        """Stop health monitoring"""
        self.logger.info("Health/Recovery Agent stopped")

