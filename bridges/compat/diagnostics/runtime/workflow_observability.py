"""Public observability facade for compat workflow diagnostics."""

from loguru import logger

from bridges.compat.diagnostics.runtime.workflow_observability_instagram import (
    infer_instagram_screen_from_log,
    setup_instagram_action_hooks,
)

_active_watchdog = None
_active_tracer = None
_last_stats: dict | None = None


def set_active_watchdog(watchdog) -> None:
    global _active_watchdog
    _active_watchdog = watchdog


def clear_active_watchdog() -> None:
    set_active_watchdog(None)


def set_active_tracer(tracer) -> None:
    global _active_tracer
    _active_tracer = tracer


def get_last_stats() -> dict | None:
    return _last_stats


def _set_last_stats(stats: dict) -> None:
    global _last_stats
    _last_stats = stats


def setup_log_sink(ipc) -> None:
    """Add a loguru sink that streams every log line to the renderer via IPC."""

    def ipc_sink(message):
        record = message.record
        msg_text = str(message).rstrip()
        ipc.send(
            "log",
            level=record["level"].name.lower(),
            text=msg_text,
            module=record.get("name", ""),
            function=record.get("function", ""),
            ts=record["time"].strftime("%H:%M:%S.%f")[:-3],
        )
        if _active_watchdog and record["level"].name.upper() in ("INFO", "SUCCESS", "WARNING"):
            _active_watchdog.heartbeat(msg_text[:80])
        if _active_tracer:
            screen = infer_instagram_screen_from_log(msg_text)
            if screen:
                _active_tracer.set_screen(screen)

    logger.add(ipc_sink, level="DEBUG", format="{message}")


def setup_action_hooks(ipc) -> None:
    """Install platform hooks used by the compat workflow diagnostic bridge."""
    setup_instagram_action_hooks(ipc, heartbeat=_heartbeat, record_stats_snapshot=_set_last_stats)


def _heartbeat(message: str) -> None:
    if _active_watchdog:
        _active_watchdog.heartbeat(message)


__all__ = [
    "clear_active_watchdog",
    "get_last_stats",
    "set_active_tracer",
    "set_active_watchdog",
    "setup_action_hooks",
    "setup_log_sink",
]
