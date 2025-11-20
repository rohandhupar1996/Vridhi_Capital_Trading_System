"""Protection modules for live trading (gap detection, stop loss, etc.)"""

from .gap_detector import GapDetector, GapResult, DEFAULT_GAP_THRESHOLD

__all__ = ['GapDetector', 'GapResult', 'DEFAULT_GAP_THRESHOLD']

