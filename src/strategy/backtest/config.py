"""
Backtest Configuration System
Unified configuration for all backtest scenarios
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TradingSettings:
    """ML/Trading system settings"""
    neighbors_count: int = 5
    max_bars_back: int = 2000
    feature_count: int = 5
    
    # Filters
    use_kernel_filter: bool = True
    kernel_lookback: int = 8
    kernel_relative_weight: float = 8.0
    
    use_volatility_filter: bool = True
    use_regime_filter: bool = True
    regime_threshold: float = -0.1
    
    # Re-entry
    enable_reentry: bool = True
    reentry_window_start: int = 3
    reentry_window_end: int = 50


@dataclass
class BacktestConfig:
    """Master backtest configuration"""
    
    # ==== DATA SETTINGS ====
    db_path: str = "data/banknifty_data.db"
    primary_timeframe: str = '15min'  # '15min' or '1hour'
    lookback_bars: int = 3000
    
    # ==== TIMEFRAME SETTINGS ====
    use_dual_timeframe: bool = False  # Enable 15m + 1h confluence
    secondary_timeframe: str = '1hour'
    
    # ==== ML SETTINGS ====
    ml_settings: TradingSettings = field(default_factory=lambda: TradingSettings())
    
    # ==== EXIT STRATEGY ====
    exit_mode: str = 'default'  # 'default', 'volume', 'hybrid'
    # 'default' - Fixed N-bar exit
    # 'volume' - Volume node exit only
    # 'hybrid' - Volume nodes + fallback to N-bar
    
    default_exit_bars: int = 4  # Used in 'default' and 'hybrid' modes
    
    # Volume exit settings (for 'volume' and 'hybrid' modes)
    volume_exit_directions: List[str] = field(default_factory=lambda: ['SHORT'])
    # Options: ['LONG'], ['SHORT'], ['LONG', 'SHORT'], []
    
    volume_lookback: int = 360
    volume_num_rows: int = 100
    
    # ==== ADVANCED FEATURES ====
    track_drawdown: bool = True  # Calculate MFE/MAE
    use_repaint_detection: bool = True
    
    # ==== BACKTEST PARAMETERS ====
    initial_capital: float = 100000.0
    start_bar: int = 200  # Bars needed for ML warmup
    
    # ==== OUTPUT SETTINGS ====
    save_trades: bool = True
    output_filename: str = 'backtest_trades.csv'
    verbose: bool = True
    
    # ==== CONFIG NAME ====
    name: str = "Default Config"  # For comparison runs
    
    def __post_init__(self):
        """Validate configuration"""
        assert self.exit_mode in ['default', 'volume', 'hybrid'], \
            f"Invalid exit_mode: {self.exit_mode}"
        
        assert self.primary_timeframe in ['15min', '1hour', '1min', '5min'], \
            f"Invalid timeframe: {self.primary_timeframe}"
        
        for direction in self.volume_exit_directions:
            assert direction in ['LONG', 'SHORT'], \
                f"Invalid direction: {direction}"
    
    def summary(self) -> str:
        """Print configuration summary"""
        lines = [
            f"\n{'='*70}",
            f"BACKTEST CONFIG: {self.name}",
            f"{'='*70}",
            f"\n📊 DATA:",
            f"  Primary TF:       {self.primary_timeframe}",
            f"  Dual TF:          {self.use_dual_timeframe}",
        ]
        
        if self.use_dual_timeframe:
            lines.append(f"  Secondary TF:     {self.secondary_timeframe}")
        
        lines.extend([
            f"  Lookback:         {self.lookback_bars} bars",
            f"\n🚪 EXIT STRATEGY:",
            f"  Mode:             {self.exit_mode}",
        ])
        
        if self.exit_mode == 'default':
            lines.append(f"  Exit after:       {self.default_exit_bars} bars")
        elif self.exit_mode == 'volume':
            lines.append(f"  Volume exit:      {', '.join(self.volume_exit_directions)}")
        elif self.exit_mode == 'hybrid':
            lines.extend([
                f"  Volume exit:      {', '.join(self.volume_exit_directions)}",
                f"  Fallback:         {self.default_exit_bars} bars"
            ])
        
        lines.extend([
            f"\n⚙️  FEATURES:",
            f"  Track MFE/MAE:    {self.track_drawdown}",
            f"  Repaint detect:   {self.use_repaint_detection}",
            f"  ML neighbors:     {self.ml_settings.neighbors_count}",
            f"  Kernel filter:    {self.ml_settings.use_kernel_filter}",
            f"\n💰 CAPITAL:",
            f"  Initial:          ${self.initial_capital:,.0f}",
            f"\n{'='*70}\n"
        ])
        
        return '\n'.join(lines)


# ==== PRESET CONFIGURATIONS ====

def get_config_single_tf_default() -> BacktestConfig:
    """Single 15min timeframe, 4-bar exit (like backtest.py)"""
    return BacktestConfig(
        name="Single TF - Default Exit",
        use_dual_timeframe=False,
        exit_mode='default',
        default_exit_bars=4
    )


def get_config_single_tf_no_volume() -> BacktestConfig:
    """Single 15min, no volume exits (like backtest_novolume.py)"""
    return BacktestConfig(
        name="Single TF - No Volume",
        use_dual_timeframe=False,
        exit_mode='default',
        default_exit_bars=4,
        track_drawdown=True
    )


def get_config_dual_tf_complete() -> BacktestConfig:
    """Dual timeframe with volume exit for SHORT only (like complete_backtest.py)"""
    return BacktestConfig(
        name="Dual TF - Complete",
        use_dual_timeframe=True,
        exit_mode='hybrid',
        default_exit_bars=4,
        volume_exit_directions=['SHORT'],
        track_drawdown=True,
        use_repaint_detection=True
    )


def get_config_volume_both_directions() -> BacktestConfig:
    """Volume exit for both LONG and SHORT"""
    return BacktestConfig(
        name="Volume Both Directions",
        use_dual_timeframe=False,
        exit_mode='volume',
        volume_exit_directions=['LONG', 'SHORT'],
        track_drawdown=True
    )


# ==== QUICK CONFIG BUILDER ====

class ConfigBuilder:
    """Fluent interface for building configs"""
    
    def __init__(self):
        self.config = BacktestConfig()
    
    def with_dual_timeframe(self) -> 'ConfigBuilder':
        self.config.use_dual_timeframe = True
        return self
    
    def with_exit_mode(self, mode: str, bars: int = 4) -> 'ConfigBuilder':
        self.config.exit_mode = mode
        self.config.default_exit_bars = bars
        return self
    
    def with_volume_exit(self, directions: List[str]) -> 'ConfigBuilder':
        self.config.volume_exit_directions = directions
        return self
    
    def with_name(self, name: str) -> 'ConfigBuilder':
        self.config.name = name
        return self
    
    def build(self) -> BacktestConfig:
        return self.config


if __name__ == "__main__":
    # Test configurations
    print("\n" + "="*70)
    print("TESTING PRESET CONFIGURATIONS")
    print("="*70)
    
    configs = [
        get_config_single_tf_default(),
        get_config_single_tf_no_volume(),
        get_config_dual_tf_complete(),
        get_config_volume_both_directions()
    ]
    
    for cfg in configs:
        print(cfg.summary())
    
    # Test builder
    print("\n" + "="*70)
    print("TESTING CONFIG BUILDER")
    print("="*70)
    
    custom = (ConfigBuilder()
              .with_name("Custom Strategy")
              .with_dual_timeframe()
              .with_exit_mode('hybrid', bars=6)
              .with_volume_exit(['LONG', 'SHORT'])
              .build())
    
    print(custom.summary())