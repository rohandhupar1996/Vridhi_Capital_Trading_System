"""
Repaint Detection and Handling
Monitors signal changes during candle formation
"""

import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class RepaintCheck:
    """Track signal state for repaint detection"""
    signal_15m_active: bool = False
    signal_1h_active: bool = False
    direction_15m: int = 0  # 1=long, -1=short, 0=none
    direction_1h: int = 0
    last_check_bar_15m: int = -1
    last_check_bar_1h: int = -1


class RepaintDetector:
    """Detects and handles signal repainting"""
    
    def __init__(self):
        self.state = RepaintCheck()
    
    def update(self, signal_15m: Optional[int], signal_1h: Optional[int],
               bar_15m: int, bar_1h: int) -> Tuple[bool, str]:
        """
        Check for repainting
        
        Returns: (repaint_detected, action)
        action: 'exit', 'switch_to_15m', 'switch_to_1h', 'stay', 'none'
        """
        repaint = False
        action = 'none'
        
        # First time setup
        if self.state.last_check_bar_15m == -1:
            self.state.signal_15m_active = signal_15m is not None
            self.state.signal_1h_active = signal_1h is not None
            self.state.direction_15m = signal_15m if signal_15m else 0
            self.state.direction_1h = signal_1h if signal_1h else 0
            self.state.last_check_bar_15m = bar_15m
            self.state.last_check_bar_1h = bar_1h
            return False, 'none'
        
        # Detect changes
        sig_15m_changed = (signal_15m != self.state.direction_15m)
        sig_1h_changed = (signal_1h != self.state.direction_1h)
        
        if not sig_15m_changed and not sig_1h_changed:
            return False, 'stay'
        
        repaint = True
        
        # Determine action based on what remains
        both_active = self.state.signal_15m_active and self.state.signal_1h_active
        
        if sig_15m_changed and sig_1h_changed:
            # Both repaints
            if signal_15m is None and signal_1h is None:
                action = 'exit'
            elif signal_15m is not None and signal_1h is None:
                action = 'switch_to_15m'
            elif signal_15m is None and signal_1h is not None:
                action = 'switch_to_1h'
            else:
                # Both still exist
                action = 'stay'
        
        elif sig_15m_changed:
            # 15m repaints
            if both_active:
                if signal_15m is None and signal_1h is not None:
                    action = 'stay'  # Keep 1h
                else:
                    action = 'stay'
            else:
                # Was 15m only
                if signal_15m is None:
                    action = 'exit'
                else:
                    action = 'stay'
        
        elif sig_1h_changed:
            # 1h repaints
            if both_active:
                if signal_1h is None and signal_15m is not None:
                    action = 'switch_to_15m'
                else:
                    action = 'stay'
            else:
                action = 'stay'
        
        # Update state
        self.state.signal_15m_active = signal_15m is not None
        self.state.signal_1h_active = signal_1h is not None
        self.state.direction_15m = signal_15m if signal_15m else 0
        self.state.direction_1h = signal_1h if signal_1h else 0
        self.state.last_check_bar_15m = bar_15m
        self.state.last_check_bar_1h = bar_1h
        
        return repaint, action
    
    def reset(self):
        """Reset state for new trade"""
        self.state = RepaintCheck()


def check_candle_close_confirmation(results_15m: dict, results_1h: dict,
                                    bar_15m: int, bar_1h: int) -> Tuple[bool, bool]:
    """
    Check if signals still exist at candle close
    
    Returns: (signal_15m_confirmed, signal_1h_confirmed)
    """
    sig_15m = (results_15m['start_long'][bar_15m] or 
               results_15m['start_short'][bar_15m])
    
    sig_1h = (results_1h['start_long'][bar_1h] or 
              results_1h['start_short'][bar_1h])
    
    return sig_15m, sig_1h


# ==================== TESTING ====================

if __name__ == "__main__":
    print("Repaint Detection Test\n" + "="*60)
    
    detector = RepaintDetector()
    
    # Simulate scenarios
    scenarios = [
        # (bar_15m, bar_1h, sig_15m, sig_1h, description)
        (0, 0, 1, 1, "Both long signals"),
        (1, 0, 1, 1, "Still both active"),
        (2, 0, 1, None, "1hr repaints away"),
        (3, 1, 1, 1, "1hr comes back"),
        (4, 1, None, 1, "15m repaints away"),
        (5, 1, None, None, "Both gone"),
    ]
    
    print("Scenario tests:\n")
    for bar_15m, bar_1h, sig_15m, sig_1h, desc in scenarios:
        repaint, action = detector.update(sig_15m, sig_1h, bar_15m, bar_1h)
        
        sig_str_15m = {1: 'LONG', -1: 'SHORT', None: 'NONE'}[sig_15m]
        sig_str_1h = {1: 'LONG', -1: 'SHORT', None: 'NONE'}[sig_1h]
        
        print(f"Bar {bar_15m}/{bar_1h}: {desc}")
        print(f"  15m={sig_str_15m}, 1h={sig_str_1h}")
        print(f"  Repaint={repaint}, Action={action}\n")
    
    print("✅ Repaint detection ready")