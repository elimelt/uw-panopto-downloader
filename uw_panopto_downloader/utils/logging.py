"""Logging utilities for Panopto Downloader."""

import logging
import os
from typing import Optional

# Configure rich logger if available
try:
    from rich.logging import RichHandler
    from rich.console import Console
    
    console = Console()
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Global logger configuration
LOG_FILE = "panopto_downloader.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = logging.INFO

# Store configured loggers to avoid duplicate handlers
_loggers = {}


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        logging.Logger: Configured logger
    """
    if name in _loggers:
        return _loggers[name]
    
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)
    
    # Remove any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add file handler
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(file_handler)
    
    # Add rich handler if available, otherwise use stream handler
    if RICH_AVAILABLE:
        rich_handler = RichHandler(rich_tracebacks=True, markup=True)
        logger.addHandler(rich_handler)
    else:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(stream_handler)
    
    # Store logger to avoid duplicate configuration
    _loggers[name] = logger
    
    return logger