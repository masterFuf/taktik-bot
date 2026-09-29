"""JSON stdout events and logging setup for YouTube diagnostics."""

import io
import json
import sys

from loguru import logger


def configure_stdout() -> None:
    """Force UTF-8 stdout so diagnostic JSON remains parseable on Windows."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    else:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def emit(obj: dict) -> None:
    """Emit one JSON event on stdout."""
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def log(level: str, message: str) -> None:
    """Emit a diagnostic log event."""
    emit({"type": "log", "level": level, "message": message})


def configure_logger() -> None:
    """Route loguru messages through the JSON diagnostics protocol."""
    logger.remove()
    logger.add(
        lambda msg: log(msg.record["level"].name.lower(), msg.record["message"]),
        format="{message}",
        level="DEBUG",
    )


__all__ = ["configure_logger", "configure_stdout", "emit", "log"]
