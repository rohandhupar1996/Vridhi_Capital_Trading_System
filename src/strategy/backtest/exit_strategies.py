"""
Exit Strategy Manager
Unified exit logic for all backtest scenarios
"""

import numpy as np
from typing import Tuple, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Trade:
    """Trade data structure"""
    entry_bar: int
    entry_time: datetime
    entry_price: float
    direction: int  # 1=LONG, -1=SHORT
    timeframe: str  # '15m' or '1h'
    
    # Exit info (filled when trade closes)
    exit_bar: Optional[int] = None
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: str = ""
    bars_held: int = 0
    pnl_pct: float = 0.0
    
    # Drawdown tracking (if enabled)
    max_favorable_pct: float = 0.0  # Max profit during trade
    max_adverse_pct: float = 0.0    # Max loss during trade


@dataclass
class MarketData:
    """Market data at current bar"""
    bar: int
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class ExitStrategyManager:
    """
    Manages all exit strategies in one place
    Priority order:
    1. Repaint detection (if enabled)
    2. Default N-bar exit
    """
    
    def __init__(self, config):
        """
        Args:
            config: BacktestConfig instance
        """
        self.config = config
    
    def check_exit(self, trade: Trade, data: MarketData, 
                   repaint_detector=None) -> Tuple[bool, str]:
        """
        Check if trade should exit
        
        Returns:
            (should_exit, exit_reason)
        """
        if trade is None:
            return False, ""
        
        # Priority 1: Repaint detection
        if self.config.use_repaint_detection and repaint_detector:
            if self._check_repaint_exit(trade, repaint_detector):
                return True, "repaint"
        
        # Priority 2: Default N-bar exit
        if self._check_default_exit(trade, data):
            return True, f"{self.config.default_exit_bars}_bars"
        
        return False, ""
    
    def _check_repaint_exit(self, trade: Trade, repaint_detector) -> bool:
        """Check if signal repainted (changed direction)"""
        if not repaint_detector:
            return False
        
        # Check if direction changed
        return repaint_detector.check_repaint(trade.direction)
    
    def _check_default_exit(self, trade: Trade, data: MarketData) -> bool:
        """Check if N bars have passed"""
        bars_in_trade = data.bar - trade.entry_bar
        return bars_in_trade >= self.config.default_exit_bars
    
    def calculate_trade_pnl(self, trade: Trade, exit_price: float) -> float:
        """Calculate P&L percentage"""
        if trade.direction == 1:  # LONG
            pnl = (exit_price - trade.entry_price) / trade.entry_price * 100
        else:  # SHORT
            pnl = (trade.entry_price - exit_price) / trade.entry_price * 100
        
        return pnl
    
    def update_trade_drawdown(self, trade: Trade, data: MarketData):
        """Update MFE/MAE for active trade"""
        if not self.config.track_drawdown or not trade:
            return
        
        current_price = data.close
        
        if trade.direction == 1:  # LONG
            # MFE = max profit
            favorable = (data.high - trade.entry_price) / trade.entry_price * 100
            # MAE = max loss
            adverse = (data.low - trade.entry_price) / trade.entry_price * 100
        else:  # SHORT
            # MFE = max profit
            favorable = (trade.entry_price - data.low) / trade.entry_price * 100
            # MAE = max loss
            adverse = (trade.entry_price - data.high) / trade.entry_price * 100
        
        trade.max_favorable_pct = max(trade.max_favorable_pct, favorable)
        trade.max_adverse_pct = min(trade.max_adverse_pct, adverse)


# ==== TESTING ====

if __name__ == "__main__":
    from strategy.backtest.config import BacktestConfig, get_config_dual_tf_complete
    
    print("\n" + "="*70)
    print("TESTING EXIT STRATEGY MANAGER")
    print("="*70)
    
    # Test different configs
    configs_to_test = [
        BacktestConfig(exit_mode='default', name='Default Exit'),
    ]
    
    for cfg in configs_to_test:
        print(f"\n{cfg.name}:")
        manager = ExitStrategyManager(cfg)
        print(f"  Exit mode: {cfg.exit_mode}")
    
    # Test trade exit logic
    print("\n" + "="*70)
    print("TESTING EXIT LOGIC")
    print("="*70)
    
    cfg = get_config_dual_tf_complete()
    manager = ExitStrategyManager(cfg)
    
    # Create test trade
    trade = Trade(
        entry_bar=100,
        entry_time=datetime.now(),
        entry_price=50000.0,
        direction=-1,  # SHORT
        timeframe='15m'
    )
    
    # Test at different prices
    test_cases = [
        (100, 50100.0, "Entry - no exit expected"),
        (104, 50000.0, "4 bars passed - should exit"),
    ]
    
    for bar, price, description in test_cases:
        data = MarketData(
            bar=bar,
            timestamp=datetime.now(),
            open=price,
            high=price + 50,
            low=price - 50,
            close=price,
            volume=1000
        )
        
        should_exit, reason = manager.check_exit(trade, data)
        print(f"\n{description}:")
        print(f"  Bar: {bar}, Price: {price:.0f}")
        print(f"  Exit: {should_exit}, Reason: {reason}")
    
    print("\n✅ Exit strategy manager ready!")