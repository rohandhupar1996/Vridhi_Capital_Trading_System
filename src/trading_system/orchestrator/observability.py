"""
Observability/Guardrails
Structured logs + metrics (auth latency, tick freshness, quote/ltp drift, order reject rates)
Runbooks for: token expired, websocket flaps, margin reject, rate limits, weekend/market-closed
Audit trail for every action; simulation mode on weekends (dry-run orders expected to reject)
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import json
from pathlib import Path

from .event_bus import EventBus, Event, EventType, get_event_bus
from ..logging import ComponentLogger


@dataclass
class Metric:
    """Metric data point"""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str] = None


class MetricsCollector:
    """Collects and stores system metrics"""
    
    def __init__(self, logger: Optional[ComponentLogger] = None):
        self.logger = logger or ComponentLogger.get_logger("metrics")
        self.metrics: List[Metric] = []
        self._max_metrics = 10000
    
    def record(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Record a metric"""
        metric = Metric(
            name=name,
            value=value,
            timestamp=datetime.now(),
            tags=tags or {}
        )
        self.metrics.append(metric)
        
        # Trim if too many
        if len(self.metrics) > self._max_metrics:
            self.metrics = self.metrics[-self._max_metrics:]
    
    def get_metrics(self, name: Optional[str] = None, limit: int = 100) -> List[Metric]:
        """Get metrics, optionally filtered by name"""
        if name:
            filtered = [m for m in self.metrics if m.name == name]
            return filtered[-limit:]
        return self.metrics[-limit:]


class Runbook:
    """Runbook for handling common issues"""
    
    RUNBOOKS = {
        "token_expired": {
            "steps": [
                "1. Check token expiry time",
                "2. Call auth_agent.refresh_token()",
                "3. If fails, prompt for manual login",
                "4. Do not halt data/OMS if current token valid"
            ],
            "severity": "high"
        },
        "websocket_flaps": {
            "steps": [
                "1. Detect connection drop",
                "2. Exponential backoff reconnect",
                "3. Failover to REST polling if needed",
                "4. Cap retries at 3",
                "5. Notify if persistent"
            ],
            "severity": "medium"
        },
        "margin_reject": {
            "steps": [
                "1. Reduce lot size (8→4→2→1)",
                "2. Ensure hedges placed first",
                "3. Switch to limit order at smart price if needed",
                "4. If still failing, flatten partials",
                "5. Stop new entries until margin OK"
            ],
            "severity": "high"
        },
        "rate_limits": {
            "steps": [
                "1. Detect rate limit error",
                "2. Apply jittered backoff",
                "3. Reduce request frequency",
                "4. Degrade to safe mode if persistent"
            ],
            "severity": "medium"
        },
        "weekend_market_closed": {
            "steps": [
                "1. Detect market closed",
                "2. Switch to simulation mode",
                "3. Dry-run orders (expected to reject)",
                "4. Continue signal generation for testing"
            ],
            "severity": "low"
        }
    }
    
    @classmethod
    def get(cls, issue: str) -> Optional[Dict]:
        """Get runbook for an issue"""
        return cls.RUNBOOKS.get(issue)
    
    @classmethod
    def list_all(cls) -> List[str]:
        """List all available runbooks"""
        return list(cls.RUNBOOKS.keys())


class AuditTrail:
    """Audit trail for all actions"""
    
    def __init__(self, log_file: Optional[Path] = None):
        self.log_file = log_file or Path("logs/audit_trail.jsonl")
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.event_bus = get_event_bus()
        
        # Subscribe to all events
        for event_type in EventType:
            self.event_bus.subscribe(event_type, self._log_event)
    
    def _log_event(self, event: Event):
        """Log event to audit trail"""
        audit_entry = {
            "timestamp": event.timestamp.isoformat(),
            "event_type": event.event_type.value,
            "priority": event.priority.value,
            "source": event.source,
            "data": event.data,
            "correlation_id": event.correlation_id
        }
        
        # Append to JSONL file
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(audit_entry) + '\n')


# Global instances
_global_metrics = MetricsCollector()
_global_audit = AuditTrail()


def get_metrics() -> MetricsCollector:
    """Get global metrics collector"""
    return _global_metrics


def get_audit_trail() -> AuditTrail:
    """Get global audit trail"""
    return _global_audit

