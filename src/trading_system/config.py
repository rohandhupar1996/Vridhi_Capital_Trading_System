"""
Central configuration dataclasses for the trading system.

These abstractions decouple configuration concerns from individual
scripts so components can be reused across CLIs, notebooks, and services.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class DataStoreConfig:
    """Database and credential settings for historical data storage."""

    db_path: Path = Path("data") / "banknifty_data.db"
    env_paths: tuple[Path, ...] = (
        Path("configs") / ".env",
        Path(".env"),
    )
    tv_username: Optional[str] = None
    tv_password: Optional[str] = None
    project_root: Optional[Path] = None


@dataclass(slots=True)
class BacktestConfig:
    """High-level parameters shared across backtest engines."""

    symbol: str = "BANKNIFTY1!"
    timeframe: str = "15min"
    lookback_bars: int = 3_000
    start_bar: int = 200
    default_exit_bars: int = 4
    initial_capital: float = 100_000.0
    neighbors_count: int = 5
    max_bars_back: int = 3_000
    use_kernel_filter: bool = True
    use_volatility_filter: bool = True
    use_regime_filter: bool = True
    enable_reentry: bool = True
    track_drawdown: bool = True
    save_trades: bool = True
    verbose: bool = True
    # Optional output overrides
    trades_output: Optional[Path] = None


@dataclass(slots=True)
class ZerodhaConfig:
    """Zerodha broker configuration and credentials."""
    
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    request_token: Optional[str] = None
    token_file: Path = Path("configs") / "zerodha_tokens.json"
    connection_check_interval: int = 30  # seconds
    auto_reconnect: bool = True


@dataclass(slots=True)
class AppConfig:
    """Aggregate configuration for the entire trading system."""

    root_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parents[2])
    data: DataStoreConfig = field(default_factory=DataStoreConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    zerodha: ZerodhaConfig = field(default_factory=ZerodhaConfig)

    def resolve_path(self, relative: Path | str) -> Path:
        """Return an absolute path relative to the project root."""
        relative_path = Path(relative)
        if relative_path.is_absolute():
            return relative_path
        return self.root_dir / relative_path

    def __post_init__(self) -> None:
        if not self.data.project_root:
            self.data.project_root = self.root_dir

