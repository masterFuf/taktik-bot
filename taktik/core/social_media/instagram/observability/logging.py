"""
Logging configuration.

Configures the logger with custom output formats and the appropriate handlers.

"""

import logging
import sys
from typing import Optional, Dict, Any
from pathlib import Path
from loguru import logger

class InterceptHandler(logging.Handler):
    """Redirect the standard logging records to loguru."""
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )

def setup_logger(
    name: str = "instagram",
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    rotation: str = "10 MB",
    retention: str = "30 days",
    serialize: bool = False,
    backtrace: bool = True,
    diagnose: bool = False,
) -> logger:
    """
    Configure the logger.

    Args:
        name: logger name
        log_level: Niveau de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: output file, optional
        rotation: log file rotation
        retention: log file retention
        serialize: emit the records as JSON
        backtrace: include the full trace on errors
        diagnose: show the local variables on errors

    Returns:
        The configured logger instance
    """
    # Log configuration
    log_config = {
        "handlers": [
            {
                "sink": sys.stderr,
                "format": "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                         "<level>{level: <8}</level> | "
                         "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
            }
        ],
        "levels": [
            {"name": "DEBUG", "color": "<blue>"},
            {"name": "INFO", "color": "<green>"},
            {"name": "WARNING", "color": "<yellow>"},
            {"name": "ERROR", "color": "<red>"},
            {"name": "CRITICAL", "color": "<red><bold>"},
        ]
    }

    # Add a log file when one is given
    if log_file:
        log_config["handlers"].append({
            "sink": log_file,
            "rotation": rotation,
            "retention": retention,
            "serialize": serialize,
            "enqueue": True,
            "backtrace": backtrace,
            "diagnose": diagnose,
            "level": log_level,
        })

    # Logger configuration
    logger.configure(**log_config)
    logger.level("INFO", color="<green>")
    logger.level("WARNING", color="<yellow>")
    logger.level("ERROR", color="<red>")
    
    # Intercept the standard library records
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    
    # Silence the noisiest loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("uiautomator2").setLevel(logging.WARNING)
    
    # Return a logger bound to the given name
    return logger.bind(module=f"instagram.{name}")

# Create a default logger instance
instagram_logger = setup_logger()
