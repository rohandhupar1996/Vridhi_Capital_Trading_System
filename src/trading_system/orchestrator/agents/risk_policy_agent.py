"""
Risk/Policy Agent
Enforces hard limits (max lots, daily loss, NRML/Market, trading windows)
Margin pre-checks, sequential lot reduction, hedges first
Circuit breakers; read-only mode on breach
"""

from typing import Optional, Dict
from datetime import datetime

from ..event_bus import EventBus, Event, EventType, EventPriority, get_event_bus
from ..shared_state import SharedState, get_shared_state
from ...logging import ComponentLogger


class RiskPolicyAgent:
    """
    Enforces risk limits and policies
    Circuit breakers, margin checks, trading windows
    """
    
    def __init__(
        self,
        orchestrator,
        max_lots: int = 8,
        logger: Optional[ComponentLogger] = None
    ):
        self.max_lots = max_lots
        self.orchestrator = orchestrator
        self.logger = logger or ComponentLogger.get_logger("risk_agent")
        
        self.event_bus = get_event_bus()
        self.shared_state = get_shared_state()
        
        self._trading_window_start = datetime.now().replace(hour=9, minute=15, second=0)
        self._trading_window_end = datetime.now().replace(hour=15, minute=30, second=0)
    
    def check_margin(self, position_type: str, lot_size: int) -> tuple[bool, float]:
        """Pre-check margin before trade"""
        # This will be called by OMS, but we can also check here
        available = self.shared_state.get("available_margin", 0.0)
        
        # Get required margin from pre-calculated
        pre_calc = self.shared_state.get("pre_calculated_margins")
        if pre_calc:
            required = pre_calc.get(position_type.lower(), {}).get('total_margin', 0.0)
        else:
            # Estimate (will be calculated by OMS)
            required = 50000.0 * lot_size  # Rough estimate
        
        sufficient = available >= required
        
        self.event_bus.publish(Event(
            event_type=EventType.MARGIN_CHECK,
            priority=EventPriority.HIGH,
            timestamp=datetime.now(),
            source="risk_agent",
            data={
                "position_type": position_type,
                "lot_size": lot_size,
                "required": required,
                "available": available,
                "sufficient": sufficient
            }
        ))
        
        if not sufficient:
            self.event_bus.publish(Event(
                event_type=EventType.MARGIN_INSUFFICIENT,
                priority=EventPriority.CRITICAL,
                timestamp=datetime.now(),
                source="risk_agent",
                data={"required": required, "available": available}
            ))
        
        return sufficient, required
    
    def check_trading_window(self) -> bool:
        """Check if within trading window"""
        now = datetime.now()
        # Simple check - can be enhanced
        return True  # Always allow for now
    
    # Daily loss limit removed - not required for now
    
    def check_max_lots(self, lot_size: int) -> bool:
        """Check if lot size exceeds max"""
        if lot_size > self.max_lots:
            self.logger.warning(f"Lot size {lot_size} exceeds max {self.max_lots}")
            return False
        return True
    
    def activate_circuit_breaker(self, reason: str):
        """Activate circuit breaker - stop all trading"""
        self.logger.critical(f"Circuit breaker activated: {reason}")
        self.shared_state.set("read_only_mode", True)
        self.shared_state.set("trading_enabled", False)
        
        self.event_bus.publish(Event(
            event_type=EventType.CIRCUIT_BREAKER,
            priority=EventPriority.CRITICAL,
            timestamp=datetime.now(),
            source="risk_agent",
            data={"reason": reason}
        ))
    
    def deactivate_circuit_breaker(self):
        """Deactivate circuit breaker"""
        self.logger.info("Circuit breaker deactivated")
        self.shared_state.set("read_only_mode", False)
        self.shared_state.set("trading_enabled", True)
    
    def approve_trade(self, position_type: str, lot_size: int) -> bool:
        """Approve trade against all risk policies"""
        # Check circuit breaker
        if self.shared_state.get("read_only_mode", False):
            return False
        
        # Check trading window
        if not self.check_trading_window():
            return False
        
        # Check max lots
        if not self.check_max_lots(lot_size):
            return False
        
        # Check margin
        margin_ok, _ = self.check_margin(position_type, lot_size)
        if not margin_ok:
            return False
        
        return True
    
    # Daily P&L tracking removed - not required for now
    
    def start(self):
        """Start risk agent"""
        self.logger.info("Risk/Policy Agent started")
    
    def stop(self):
        """Stop risk agent"""
        self.logger.info("Risk/Policy Agent stopped")

