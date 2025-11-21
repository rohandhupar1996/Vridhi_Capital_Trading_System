"""
Adapter layer to expose the production SingleTimeframeBacktester
and its BacktestConfig from a strategy/backtest namespace.

This keeps `run_single_tf.py` free from direct imports of
`src.trading_system.*` while preserving ALL existing maths/logic.
"""

from src.trading_system.backtest import SingleTimeframeBacktester as _SingleTimeframeBacktester  # noqa: F401
from src.trading_system.config import BacktestConfig as _BacktestConfig  # noqa: F401

# Re-export under a strategy/backtest-friendly namespace
SingleTimeframeBacktester = _SingleTimeframeBacktester
BacktestConfig = _BacktestConfig

__all__ = ["SingleTimeframeBacktester", "BacktestConfig"]



