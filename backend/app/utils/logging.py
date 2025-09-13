"""
StyleSync Structured Logging
Centralized logging configuration using loguru.
"""
import sys
from typing import Dict, Any, Optional

try:
    from loguru import logger
except ImportError:
    # Fallback to standard logging if loguru not available
    import logging
    
    class LoguruFallback:
        def __init__(self):
            logging.basicConfig(level=logging.INFO)
            self._logger = logging.getLogger("stylesync")
        
        def info(self, msg: str, **kwargs):
            self._logger.info(msg)
        
        def warning(self, msg: str, **kwargs):
            self._logger.warning(msg)
        
        def error(self, msg: str, **kwargs):
            self._logger.error(msg)
        
        def debug(self, msg: str, **kwargs):
            self._logger.debug(msg)
    
    logger = LoguruFallback()

from app.config import config


class StructuredLogger:
    """Structured logger for StyleSync segmentation service."""
    
    def __init__(self):
        """Initialize structured logger."""
        self._configure_logger()
    
    def _configure_logger(self):
        """Configure loguru logger with structured format."""
        if hasattr(logger, 'remove'):
            # Remove default handler
            logger.remove()
            
            # Add structured JSON handler
            logger.add(
                sys.stdout,
                format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message} | {extra}",
                level=config.LOG_LEVEL,
                serialize=False  # Set to True for JSON output
            )
    
    def info(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log info message with optional extra data."""
        if extra:
            logger.bind(**extra).info(message)
        else:
            logger.info(message)
    
    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log warning message with optional extra data."""
        if extra:
            logger.bind(**extra).warning(message)
        else:
            logger.warning(message)
    
    def error(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log error message with optional extra data."""
        if extra:
            logger.bind(**extra).error(message)
        else:
            logger.error(message)
    
    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log debug message with optional extra data."""
        if extra:
            logger.bind(**extra).debug(message)
        else:
            logger.debug(message)


# Global logger instance
_logger: Optional[StructuredLogger] = None


def get_logger() -> StructuredLogger:
    """Get or create global logger instance."""
    global _logger
    if _logger is None:
        _logger = StructuredLogger()
    return _logger
