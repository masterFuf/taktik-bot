"""Hard wall-clock boundary for optional, fail-open work.

Library timeouts are not always sufficient: a device client can block below the layer
that owns its timeout. Optional enrichment must never hold the workflow hostage, so it
runs in a daemon worker and the caller resumes after the requested wall-clock budget.
The abandoned worker may finish later, but optional calls using this helper must remain
read-only; side effects stay on the caller thread after a successful result.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Callable, Generic, Optional, TypeVar

from loguru import logger

T = TypeVar("T")


@dataclass(frozen=True)
class OptionalCallResult(Generic[T]):
    completed: bool
    value: Optional[T] = None
    timed_out: bool = False
    error: Optional[Exception] = None


def run_bounded_optional(
    operation: Callable[[], T],
    *,
    timeout_seconds: float,
    label: str,
) -> OptionalCallResult[T]:
    """Run a read-only optional operation behind a strict wall-clock boundary."""
    timeout = max(0.01, float(timeout_seconds))
    result_queue: queue.Queue = queue.Queue(maxsize=1)

    def invoke() -> None:
        try:
            result_queue.put_nowait(("ok", operation()))
        except Exception as exc:
            result_queue.put_nowait(("error", exc))

    worker = threading.Thread(
        target=invoke,
        daemon=True,
        name=f"optional-{label.replace(' ', '-')[:32]}",
    )
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        logger.warning(
            f"{label} exceeded its {timeout:.1f}s wall-clock budget; "
            "continuing without this optional result"
        )
        return OptionalCallResult(completed=False, timed_out=True)

    try:
        status, payload = result_queue.get_nowait()
    except queue.Empty:
        return OptionalCallResult(completed=False)
    if status == "error":
        logger.debug(f"{label} failed: {payload}")
        return OptionalCallResult(completed=True, error=payload)
    return OptionalCallResult(completed=True, value=payload)


__all__ = ["OptionalCallResult", "run_bounded_optional"]
