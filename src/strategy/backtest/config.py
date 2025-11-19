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
    # Exit modes (clearer naming):
    # - '4bar_only': Default 4-bar exit only (no volume exit)
    # - '4bar_with_volume': 4-bar exit + volume peak exit (both LONG and SHORT)
    # - '4bar_with_volume_long': 4-bar exit + volume peak exit (LONG only)
    # - '4bar_with_volume_short': 4-bar exit + volume peak exit (SHORT only)
    exit_mode: str = '4bar_only'  # '4bar_only', '4bar_with_volume', '4bar_with_volume_long', '4bar_with_volume_short'
    
    default_exit_bars: int = 4
    
    # Volume node exit settings (optimized for performance with Numba JIT)
    # Note: Pine Script defaults are 360 lookback, 100 rows - but these are optimized for speed
    # For Pine Script accuracy, set: volume_exit_lookback=360, volume_exit_num_rows=100
    volume_exit_lookback: int = 240  # Optimized: 240 bars (~60 hours of 15min data, sufficient for accuracy, 2x faster than 360)
    volume_exit_num_rows: int = 60   # Optimized: 60 price levels (2x faster than 100, still accurate)
    volume_exit_value_area: float = 0.7  # Pine Script default: 70% value area
    volume_exit_peak_percent: float = 0.09  # Pine Script default: 9% for peak nodes
    volume_exit_trough_percent: float = 0.07  # Pine Script default: 7% for trough nodes
    volume_exit_threshold: float = 0.01  # Pine Script default: 1% threshold
    
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
        valid_exit_modes = ['4bar_only', '4bar_with_volume', '4bar_with_volume_long', '4bar_with_volume_short',
                           # Legacy mode names (backward compatibility)
                           'default', 'volume_both', 'volume_long', 'volume_short']
        assert self.exit_mode in valid_exit_modes, \
            f"Invalid exit_mode: {self.exit_mode}. Valid: {valid_exit_modes}"
        
        # Map legacy names to new names
        legacy_map = {
            'default': '4bar_only',
            'volume_both': '4bar_with_volume',
            'volume_long': '4bar_with_volume_long',
            'volume_short': '4bar_with_volume_short',
        }
        if self.exit_mode in legacy_map:
            self.exit_mode = legacy_map[self.exit_mode]
        
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
            f"  Exit mode:        {self.exit_mode}",
            f"  Exit after:       {self.default_exit_bars} bars",
        ])
        
        if self.exit_mode in ['4bar_with_volume', '4bar_with_volume_long', '4bar_with_volume_short',
                             'volume_both', 'volume_long', 'volume_short']:  # Legacy names
            lines.append(f"  Volume exit enabled:")
            lines.append(f"    Lookback: {self.volume_exit_lookback} bars (optimized for speed)")
            lines.append(f"    Price levels: {self.volume_exit_num_rows} (optimized for speed)")
            lines.append(f"    Value area: {self.volume_exit_value_area*100:.0f}%")
            lines.append(f"    Peak node size: {self.volume_exit_peak_percent*100:.0f}%")
            if self.volume_exit_lookback == 240 and self.volume_exit_num_rows == 60:
                lines.append(f"    ✅ 2x faster than Pine Script defaults (360/100)")
            lines.append(f"    Optimized with Numba JIT for real-time performance")
        
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
    """Single 15min timeframe, 4-bar exit only (no volume exit)"""
    return BacktestConfig(
        name="Single TF - 4-Bar Exit Only",
        use_dual_timeframe=False,
        exit_mode='4bar_only',
        default_exit_bars=4
    )


def get_config_single_tf_no_volume() -> BacktestConfig:
    """Single 15min, no volume exits (like backtest_novolume.py)"""
    return BacktestConfig(
        name="Single TF - No Volume",
        use_dual_timeframe=False,
        exit_mode='4bar_only',
        default_exit_bars=4,
        track_drawdown=True
    )


def get_config_dual_tf_complete() -> BacktestConfig:
    """Dual timeframe with default exit"""
    return BacktestConfig(
        name="Dual TF - Complete",
        use_dual_timeframe=True,
        exit_mode='4bar_only',
        default_exit_bars=4,
        track_drawdown=True,
        use_repaint_detection=True
    )


def get_config_single_tf_volume_both() -> BacktestConfig:
    """Single 15min timeframe, 4-bar + volume peak exit (both LONG and SHORT)
    
    Uses optimized defaults (240 lookback, 60 rows) for 2x faster performance.
    For Pine Script accuracy: set volume_exit_lookback=360, volume_exit_num_rows=100
    Exit: Whichever triggers first - volume peak cross OR 4 bars held.
    """
    return BacktestConfig(
        name="Single TF - 4-Bar + Volume Exit (Both)",
        use_dual_timeframe=False,
        exit_mode='4bar_with_volume',
        default_exit_bars=4,
        volume_exit_lookback=240,  # Optimized for speed (Pine Script: 360)
        volume_exit_num_rows=60,   # Optimized for speed (Pine Script: 100)
        volume_exit_value_area=0.7,  # Pine Script default: 70%
        volume_exit_peak_percent=0.09,  # Pine Script default: 9%
        volume_exit_trough_percent=0.07,  # Pine Script default: 7%
        volume_exit_threshold=0.01,  # Pine Script default: 1%
    )


def get_config_single_tf_volume_long() -> BacktestConfig:
    """Single 15min timeframe, 4-bar + volume peak exit (LONG only)
    
    Uses optimized defaults (240 lookback, 60 rows) for 2x faster performance.
    For Pine Script accuracy: set volume_exit_lookback=360, volume_exit_num_rows=100
    Exit: Whichever triggers first - volume peak cross OR 4 bars held.
    """
    return BacktestConfig(
        name="Single TF - 4-Bar + Volume Exit (Long Only)",
        use_dual_timeframe=False,
        exit_mode='4bar_with_volume_long',
        default_exit_bars=4,
        volume_exit_lookback=240,  # Optimized for speed (Pine Script: 360)
        volume_exit_num_rows=60,   # Optimized for speed (Pine Script: 100)
        volume_exit_value_area=0.7,
        volume_exit_peak_percent=0.09,
        volume_exit_trough_percent=0.07,
        volume_exit_threshold=0.01,
    )


def get_config_single_tf_volume_short() -> BacktestConfig:
    """Single 15min timeframe, 4-bar + volume peak exit (SHORT only)
    
    Uses optimized defaults (240 lookback, 60 rows) for 2x faster performance.
    For Pine Script accuracy: set volume_exit_lookback=360, volume_exit_num_rows=100
    Exit: Whichever triggers first - volume peak cross OR 4 bars held.
    """
    return BacktestConfig(
        name="Single TF - 4-Bar + Volume Exit (Short Only)",
        use_dual_timeframe=False,
        exit_mode='4bar_with_volume_short',
        default_exit_bars=4,
        volume_exit_lookback=240,  # Optimized for speed (Pine Script: 360)
        volume_exit_num_rows=60,   # Optimized for speed (Pine Script: 100)
        volume_exit_value_area=0.7,
        volume_exit_peak_percent=0.09,
        volume_exit_trough_percent=0.07,
        volume_exit_threshold=0.01,
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