"""
Component-wise logging system with daily rotation
Tracks ML, filters, kernel, trading system, and broker components
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from typing import Optional


class ComponentLogger:
    """
    Component-specific logger with daily rotation and structured logging
    """
    
    _loggers: dict[str, ComponentLogger] = {}
    _log_dir: Optional[Path] = None
    
    def __init__(self, component_name: str, log_dir: Path | str = "logs"):
        self.component_name = component_name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create logger
        self.logger = logging.getLogger(f"trading_system.{component_name}")
        self.logger.setLevel(logging.DEBUG)
        
        # Prevent duplicate handlers
        if self.logger.handlers:
            return
        
        # Console handler (INFO and above)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            f'[%(asctime)s] [{component_name}] %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # Component-specific file handler (daily rotation)
        component_file = self.log_dir / f"{component_name}.log"
        file_handler = TimedRotatingFileHandler(
            component_file,
            when='midnight',
            interval=1,
            backupCount=30,  # Keep 30 days of logs
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Error log (all components, daily rotation)
        error_file = self.log_dir / "errors.log"
        error_handler = TimedRotatingFileHandler(
            error_file,
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        self.logger.addHandler(error_handler)
        
        # Login/authentication log (daily rotation)
        auth_file = self.log_dir / "authentication.log"
        auth_handler = TimedRotatingFileHandler(
            auth_file,
            when='midnight',
            interval=1,
            backupCount=90,  # Keep 90 days of auth logs
            encoding='utf-8'
        )
        auth_handler.setLevel(logging.INFO)
        auth_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        auth_handler.setFormatter(auth_formatter)
        auth_handler.addFilter(lambda record: 'auth' in record.name.lower() or 'login' in record.getMessage().lower())
        self.logger.addHandler(auth_handler)
    
    @classmethod
    def get_logger(cls, component_name: str, log_dir: Path | str = "logs") -> ComponentLogger:
        """Get or create logger for a component"""
        if component_name not in cls._loggers:
            cls._loggers[component_name] = ComponentLogger(component_name, log_dir)
        return cls._loggers[component_name]
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message"""
        self.logger.debug(self._format_message(message, **kwargs))
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message"""
        self.logger.info(self._format_message(message, **kwargs))
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message"""
        self.logger.warning(self._format_message(message, **kwargs))
    
    def error(self, message: str, exc_info: bool = False, **kwargs) -> None:
        """Log error message"""
        self.logger.error(self._format_message(message, **kwargs), exc_info=exc_info)
    
    def critical(self, message: str, exc_info: bool = False, **kwargs) -> None:
        """Log critical message"""
        self.logger.critical(self._format_message(message, **kwargs), exc_info=exc_info)
    
    def _format_message(self, message: str, **kwargs) -> str:
        """Format message with optional context"""
        if kwargs:
            context = " | ".join(f"{k}={v}" for k, v in kwargs.items())
            return f"{message} | {context}"
        return message
    
    def log_ml_operation(self, operation: str, duration_ms: float, **kwargs) -> None:
        """Log ML operation with timing"""
        self.info(f"ML {operation} completed", duration_ms=duration_ms, **kwargs)
    
    def log_filter_operation(self, filter_name: str, passed: int, total: int, **kwargs) -> None:
        """Log filter operation"""
        pass_rate = (passed / total * 100) if total > 0 else 0
        self.debug(f"Filter {filter_name} applied", passed=passed, total=total, pass_rate=f"{pass_rate:.1f}%", **kwargs)
    
    def log_kernel_operation(self, operation: str, duration_ms: float, **kwargs) -> None:
        """Log kernel operation with timing"""
        self.info(f"Kernel {operation} completed", duration_ms=duration_ms, **kwargs)
    
    def log_trade_signal(self, signal_type: str, bar: int, price: float, **kwargs) -> None:
        """Log trade signal"""
        self.info(f"Trade signal: {signal_type}", bar=bar, price=price, **kwargs)
    
    def log_connection_event(self, event: str, status: str, **kwargs) -> None:
        """Log connection-related event"""
        self.info(f"Connection {event}", status=status, **kwargs)
    
    def log_authentication(self, event: str, success: bool, **kwargs) -> None:
        """Log authentication event"""
        status = "SUCCESS" if success else "FAILED"
        self.info(f"Authentication {event}", status=status, **kwargs)


def setup_logging(log_dir: Path | str = "logs") -> None:
    """Setup logging for entire trading system"""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Set log directory for all component loggers
    ComponentLogger._log_dir = log_dir
    
    # Create component loggers
    components = [
        "ml_extension",
        "kernel_function",
        "lorentzian_classifier",
        "trading_system",
        "backtest_engine",
        "zerodha_auth",
        "connection_monitor",
        "data_collector"
    ]
    
    for component in components:
        ComponentLogger.get_logger(component, log_dir)





