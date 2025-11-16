"""Compatibility layer exposing strategy.core modules under the legacy 'core' namespace."""

from importlib import import_module
import sys as _sys

_SUBMODULES = [
    "dual_timeframe",
    "kernel_function",
    "lorentzian_classifier",
    "ml_extension",
    "trading_system",
    "volume_nodes",
]

for _name in _SUBMODULES:
    _module = import_module(f"strategy.core.{_name}")
    _sys.modules.setdefault(f"core.{_name}", _module)

# Re-export the main trading system types for convenience
from strategy.core.trading_system import LorentzianTradingSystem, TradingSettings  # noqa: E402,F401

__all__ = [
    "LorentzianTradingSystem",
    "TradingSettings",
]
