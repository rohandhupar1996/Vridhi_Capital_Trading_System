"""
Shared State - Key-Value store for agent coordination
Stores current system state: prices, positions, flags, etc.
"""

from typing import Dict, Any, Optional
from threading import Lock, RLock
from datetime import datetime
from dataclasses import dataclass, asdict
import json
from pathlib import Path


@dataclass
class SystemState:
    """Complete system state snapshot"""
    # Market Data
    futures_ltp: Optional[float] = None
    futures_token: Optional[int] = None
    last_tick_time: Optional[datetime] = None
    
    # Timeframe
    effective_timeframe: str = "15min"
    is_expiry_day: bool = False
    
    # Earnings Filter
    earnings_blocked: bool = False
    
    # Margin
    available_margin: float = 0.0
    pre_calculated_margins: Optional[Dict] = None
    
    # Position
    current_position: Optional[Dict] = None
    
    # Health
    auth_status: str = "unknown"
    websocket_connected: bool = False
    last_heartbeat: Optional[datetime] = None
    
    # Circuit Breakers
    trading_enabled: bool = True
    read_only_mode: bool = False


class SharedState:
    """
    Thread-safe shared state store
    All agents read/write to this for coordination
    """
    
    def __init__(self, checkpoint_dir: Optional[Path] = None):
        self._state = SystemState()
        self._lock = RLock()
        self._checkpoint_dir = checkpoint_dir or Path("data/checkpoints")
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a state value"""
        with self._lock:
            return getattr(self._state, key, default)
    
    def set(self, key: str, value: Any):
        """Set a state value"""
        with self._lock:
            if hasattr(self._state, key):
                setattr(self._state, key, value)
            else:
                # Allow dynamic attributes
                setattr(self._state, key, value)
    
    def get_state(self) -> SystemState:
        """Get complete state snapshot"""
        with self._lock:
            return SystemState(**asdict(self._state))
    
    def update_state(self, **kwargs):
        """Update multiple state values atomically"""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._state, key):
                    setattr(self._state, key, value)
    
    def checkpoint(self, name: str = "latest"):
        """Save state to checkpoint file"""
        with self._lock:
            checkpoint_file = self._checkpoint_dir / f"{name}.json"
            state_dict = asdict(self._state)
            # Convert datetime to ISO string
            for key, value in state_dict.items():
                if isinstance(value, datetime):
                    state_dict[key] = value.isoformat()
            
            with open(checkpoint_file, 'w') as f:
                json.dump(state_dict, f, indent=2)
    
    def restore(self, name: str = "latest") -> bool:
        """Restore state from checkpoint file"""
        checkpoint_file = self._checkpoint_dir / f"{name}.json"
        if not checkpoint_file.exists():
            return False
        
        try:
            with open(checkpoint_file, 'r') as f:
                state_dict = json.load(f)
            
            with self._lock:
                # Restore state
                for key, value in state_dict.items():
                    if key.endswith('_time') or key == 'last_heartbeat':
                        # Parse datetime
                        if value:
                            value = datetime.fromisoformat(value)
                    setattr(self._state, key, value)
            
            return True
        except Exception as e:
            print(f"Error restoring checkpoint: {e}")
            return False


# Global shared state instance
_global_shared_state = SharedState()


def get_shared_state() -> SharedState:
    """Get the global shared state instance"""
    return _global_shared_state

