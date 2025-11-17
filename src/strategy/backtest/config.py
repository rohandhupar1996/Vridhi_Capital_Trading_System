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
    exit_mode: str = 'default'  # 'default' - Fixed N-bar exit
    
    default_exit_bars: int = 4
    
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
        assert self.exit_mode == 'default', \
            f"Invalid exit_mode: {self.exit_mode} (only 'default' supported)"
        
        assert self.primary_timeframe in ['15min', '1hour', '1min', '5min'], \
            f"Invalid timeframe: {self.primary_timeframe}"
    
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
            f"  Exit after:       {self.default_exit_bars} bars",
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
    """Dual timeframe with default exit"""
    return BacktestConfig(
        name="Dual TF - Complete",
        use_dual_timeframe=True,
        exit_mode='default',
        default_exit_bars=4,
        track_drawdown=True,
        use_repaint_detection=True
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
              .with_exit_mode('default', bars=6)
              .build())
    
    print(custom.summary())