"""
Exit Strategy Manager
Unified exit logic for all backtest scenarios
"""

import numpy as np
from typing import Tuple, Optional, List
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
    
    # Volume nodes at entry (if using volume exits)
    volume_nodes: Optional[List[float]] = None


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
    2. Volume node (if enabled for direction)
    3. Default N-bar (if in default/hybrid mode)
    """
    
    def __init__(self, config):
        """
        Args:
            config: BacktestConfig instance
        """
        self.config = config
        self.volume_detector = None
        
        # Initialize volume detector if needed
        if config.exit_mode in ['volume', 'hybrid']:
            # Import here to avoid circular dependency
            try:
                from core.volume_nodes import VolumeNodeDetector
                self.volume_detector = VolumeNodeDetector(
                    lookback=config.volume_lookback,
                    num_rows=config.volume_num_rows
                )
            except ImportError:
                print("⚠️  Warning: VolumeNodeDetector not available")
                self.volume_detector = None
    
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
        
        # Priority 2: Volume node exit (if enabled for this direction)
        if self.config.exit_mode in ['volume', 'hybrid']:
            should_exit, reason = self._check_volume_exit(trade, data)
            if should_exit:
                return True, reason
        
        # Priority 3: Default N-bar exit
        if self.config.exit_mode in ['default', 'hybrid']:
            if self._check_default_exit(trade, data):
                return True, f"{self.config.default_exit_bars}_bars"
        
        return False, ""
    
    def _check_repaint_exit(self, trade: Trade, repaint_detector) -> bool:
        """Check if signal repainted (changed direction)"""
        if not repaint_detector:
            return False
        
        # Check if direction changed
        return repaint_detector.check_repaint(trade.direction)
    
    def _check_volume_exit(self, trade: Trade, data: MarketData) -> Tuple[bool, str]:
        """Check if price crossed volume node"""
        if not self.volume_detector or not trade.volume_nodes:
            return False, ""
        
        # Check if this direction uses volume exit
        direction_name = 'LONG' if trade.direction == 1 else 'SHORT'
        if direction_name not in self.config.volume_exit_directions:
            return False, ""
        
        # Only works on 15min timeframe
        if trade.timeframe != '15m':
            return False, ""
        
        current_price = data.close
        
        # For LONG: exit if price hits resistance (node above entry)
        # For SHORT: exit if price hits support (node below entry)
        for node_price in trade.volume_nodes:
            if trade.direction == 1:  # LONG
                # Check if we hit resistance above
                if node_price > trade.entry_price:
                    if current_price >= node_price:
                        return True, "volume_node"
            else:  # SHORT
                # Check if we hit support below
                if node_price < trade.entry_price:
                    if current_price <= node_price:
                        return True, "volume_node"
        
        return False, ""
    
    def _check_default_exit(self, trade: Trade, data: MarketData) -> bool:
        """Check if N bars have passed"""
        bars_in_trade = data.bar - trade.entry_bar
        return bars_in_trade >= self.config.default_exit_bars
    
    def update_volume_nodes(self, high: np.ndarray, low: np.ndarray, 
                           volume: np.ndarray, close: np.ndarray):
        """Update volume profile (call this each bar)"""
        if self.volume_detector:
            self.volume_detector.update(high, low, volume, close)
    
    def get_current_volume_nodes(self) -> List[float]:
        """Get current volume peak prices"""
        if self.volume_detector and hasattr(self.volume_detector, 'peak_prices'):
            return self.volume_detector.peak_prices
        return []
    
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
    from config import BacktestConfig, get_config_dual_tf_complete
    
    print("\n" + "="*70)
    print("TESTING EXIT STRATEGY MANAGER")
    print("="*70)
    
    # Test different configs
    configs_to_test = [
        BacktestConfig(exit_mode='default', name='Default Exit'),
        BacktestConfig(exit_mode='volume', volume_exit_directions=['SHORT'], name='Volume SHORT'),
        BacktestConfig(exit_mode='hybrid', volume_exit_directions=['LONG', 'SHORT'], name='Hybrid Both'),
    ]
    
    for cfg in configs_to_test:
        print(f"\n{cfg.name}:")
        manager = ExitStrategyManager(cfg)
        print(f"  Exit mode: {cfg.exit_mode}")
        print(f"  Volume detector: {'✓' if manager.volume_detector else '✗'}")
        print(f"  Volume directions: {cfg.volume_exit_directions}")
    
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
        timeframe='15m',
        volume_nodes=[49500.0, 50500.0, 51000.0]
    )
    
    # Test at different prices
    test_cases = [
        (100, 50100.0, "Entry - no exit expected"),
        (101, 50500.0, "Hit volume node - should exit"),
        (104, 50000.0, "4 bars passed - should exit on hybrid"),
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