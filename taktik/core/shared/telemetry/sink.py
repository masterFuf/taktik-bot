"""The step-telemetry sink — a configurable global callback, no-op by default.

Same singleton pattern as the Instagram IPCEmitter bridge adapter, but
platform-agnostic and living under `shared/`. The bridge configures a sink
function; the shared primitives call `emit_step(...)` unconditionally and it is
a no-op until a sink is wired (standalone runs / unit tests stay silent).
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional
import time

from loguru import logger


@dataclass
class StepMetric:
    """One atomic action the bot performed.

    category: the kind of action — 'keystroke' | 'tap' | 'double_tap' |
        'button_click' | 'scroll' | 'follower_decision' | 'post_entry' | ...
    action:   a finer label within the category (e.g. 'backspace', 'flick_up').
    target:   what it acted on (a username, a selector, a screen name).
    detail:   free-form structured payload (coordinates, distances, reason, …).
    ts:       epoch seconds, stamped at emit time.
    """

    category: str
    action: Optional[str] = None
    target: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)
    ts: float = 0.0


# Module-global sink (mirrors IPCEmitter._bridge_adapter). None = no-op.
_sink: Optional[Callable[[StepMetric], None]] = None


def configure_telemetry_sink(sink: Callable[[StepMetric], None]) -> None:
    """Install the sink that receives every StepMetric (called by the bridge)."""
    global _sink
    _sink = sink


def clear_telemetry_sink() -> None:
    """Detach the sink — subsequent emits become no-ops."""
    global _sink
    _sink = None


def is_telemetry_active() -> bool:
    """Whether a sink is currently wired (lets hot paths skip building payloads)."""
    return _sink is not None


def emit_step(
    category: str,
    *,
    action: Optional[str] = None,
    target: Optional[str] = None,
    **detail: Any,
) -> None:
    """Emit one step metric. No-op (and never raises) when no sink is configured."""
    sink = _sink
    if sink is None:
        return
    try:
        sink(StepMetric(
            category=category,
            action=action,
            target=target,
            detail=detail,
            ts=time.time(),
        ))
    except Exception as exc:  # telemetry must never break a workflow
        logger.debug(f"telemetry emit error ({category}/{action}): {exc}")


__all__ = [
    "StepMetric",
    "emit_step",
    "configure_telemetry_sink",
    "clear_telemetry_sink",
    "is_telemetry_active",
]
