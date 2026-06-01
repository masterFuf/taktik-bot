"""Shared helpers for YouTube diagnostic action families."""

from bridges.youtube.diagnostics.runtime.events import log
from taktik.core.shared.device.wait import (
    try_tap as _try_tap_shared,
    wait_for_any as _wait_for_any_shared,
)


def wait_for_any(d, selectors: list, timeout: float = 6.0, label: str = "") -> str | None:
    """Bridge wrapper around shared wait_for_any that forwards JSON logs."""
    return _wait_for_any_shared(d, selectors, timeout=timeout, label=label, log=log)


def try_tap(d, selectors: list, timeout: float = 4.0, label: str = "") -> bool:
    """Bridge wrapper around shared try_tap that forwards JSON logs."""
    return _try_tap_shared(d, selectors, timeout=timeout, label=label, log=log)


__all__ = ["try_tap", "wait_for_any"]
