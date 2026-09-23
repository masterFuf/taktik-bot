"""What an action costs on the phone: dumps, round trips, waits (M1 of the one-photo spec).

Every call the bot makes to the uiautomator2 server goes through ONE method of the connected
device, `jsonrpc_call(method, params, timeout)`: a dump is `dumpWindowHierarchy`, a wait is
`waitForExists` / `waitUntilGone` / `waitForWindowUpdate`, a `.info` or a click is one more round
trip. `instrument_device_io(device)` wraps that method (and `shell`, the adb round trips) once, at
the connection, so the 57 direct `dump_hierarchy` calls and every `.xpath(...).exists` are counted
without touching them. `measure_device_io(action)` takes the counters before and after an action
and emits the difference through `emit_step("device_io", ...)`, the telemetry the bridges already
forward.

Measuring changes nothing the bot does: the wrapper calls the original method with the same
arguments and returns what it returns (or raises what it raises). It never raises itself.
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterator

from loguru import logger

from taktik.core.shared.telemetry.sink import emit_step

DUMP_METHODS = frozenset({"dumpWindowHierarchy"})
WAIT_METHODS = frozenset({"waitForExists", "waitUntilGone", "waitForWindowUpdate"})

_MARKER = "_taktik_device_io_instrumented"


class DeviceIoMeter:
    """Running totals of the device calls of this process (one bridge process = one phone)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._totals: Dict[str, float] = {}
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self._totals = {
                "rpc": 0, "rpc_ms": 0.0,
                "dumps": 0, "dump_ms": 0.0, "dump_max_ms": 0.0,
                "waits": 0, "wait_ms": 0.0,
                "shells": 0, "shell_ms": 0.0,
                "errors": 0,
            }

    def record_rpc(self, method: str, elapsed_ms: float, failed: bool = False) -> None:
        with self._lock:
            totals = self._totals
            totals["rpc"] += 1
            totals["rpc_ms"] += elapsed_ms
            if method in DUMP_METHODS:
                totals["dumps"] += 1
                totals["dump_ms"] += elapsed_ms
                totals["dump_max_ms"] = max(totals["dump_max_ms"], elapsed_ms)
            elif method in WAIT_METHODS:
                totals["waits"] += 1
                totals["wait_ms"] += elapsed_ms
            if failed:
                totals["errors"] += 1

    def record_shell(self, elapsed_ms: float, failed: bool = False) -> None:
        with self._lock:
            self._totals["shells"] += 1
            self._totals["shell_ms"] += elapsed_ms
            if failed:
                self._totals["errors"] += 1

    def snapshot(self) -> Dict[str, float]:
        with self._lock:
            return dict(self._totals)


METER = DeviceIoMeter()


def _elapsed_ms(started_at: float) -> float:
    return (time.perf_counter() - started_at) * 1000.0


def instrument_device_io(device: Any, meter: DeviceIoMeter = METER) -> bool:
    """Count every server call and adb shell of this uiautomator2 device. Once per device.

    Returns True when the device is (now) instrumented. Never raises: a device without
    `jsonrpc_call` (a test double, another driver) is left as it is.
    """
    try:
        if getattr(device, _MARKER, False):
            return True
        original_rpc = getattr(device, "jsonrpc_call", None)
        if not callable(original_rpc):
            return False

        def jsonrpc_call(method, params=None, timeout=10, *args, **kwargs):
            started_at = time.perf_counter()
            failed = False
            try:
                return original_rpc(method, params, timeout, *args, **kwargs)
            except BaseException:
                failed = True
                raise
            finally:
                meter.record_rpc(str(method), _elapsed_ms(started_at), failed)

        device.jsonrpc_call = jsonrpc_call

        # The adb round trips: through the adbutils device when there is one, since uiautomator2
        # itself goes there without `Device.shell` (`app_current()` runs three `dumpsys`: 5.3 s on
        # the Pixel 6a, uncounted at first). `shell2` may call `shell` (shell v1): only the
        # outermost call of a thread is counted.
        adb = getattr(device, "_dev", None)
        targets = [(adb, name) for name in ("shell", "shell2") if callable(getattr(adb, name, None))]
        if not targets:
            targets = [(device, "shell")] if callable(getattr(device, "shell", None)) else []
        depth = threading.local()
        for owner, name in targets:
            original = getattr(owner, name)

            def counted(*args, _original=original, **kwargs):
                if getattr(depth, "value", 0):
                    return _original(*args, **kwargs)
                depth.value = 1
                started_at = time.perf_counter()
                failed = False
                try:
                    return _original(*args, **kwargs)
                except BaseException:
                    failed = True
                    raise
                finally:
                    depth.value = 0
                    meter.record_shell(_elapsed_ms(started_at), failed)

            setattr(owner, name, counted)

        setattr(device, _MARKER, True)
        return True
    except Exception as exc:  # measuring must never break a connection
        logger.debug(f"device io instrumentation skipped: {exc}")
        return False


def _delta(before: Dict[str, float], after: Dict[str, float]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in after.items():
        if key == "dump_max_ms":
            continue
        diff = value - before.get(key, 0)
        out[key] = round(diff, 1) if isinstance(diff, float) else int(diff)
    return out


@contextmanager
def measure_device_io(action: str, meter: DeviceIoMeter = METER, **context: Any) -> Iterator[None]:
    """Emit what `action` cost on the phone: one `device_io` step when it ends (even on error).

    Fields: `dumps`, `dump_ms`, `rpc` (every server round trip, dumps included), `rpc_ms`,
    `waits`, `wait_ms` (server-side waits), `shells`, `shell_ms` (adb), `errors`, `total_ms`
    (wall time of the action) and `other_ms` (the rest: parsing, sleeps, the bot's own work).
    """
    before = meter.snapshot()
    started_at = time.perf_counter()
    try:
        yield
    finally:
        try:
            total_ms = _elapsed_ms(started_at)
            delta = _delta(before, meter.snapshot())
            device_ms = delta.get("rpc_ms", 0.0) + delta.get("shell_ms", 0.0)
            emit_step(
                "device_io",
                action=action,
                total_ms=round(total_ms, 1),
                other_ms=round(max(total_ms - device_ms, 0.0), 1),
                **delta,
                **context,
            )
        except Exception as exc:  # telemetry must never break an action
            logger.debug(f"device io measure skipped for {action}: {exc}")


__all__ = [
    "DUMP_METHODS",
    "WAIT_METHODS",
    "DeviceIoMeter",
    "METER",
    "instrument_device_io",
    "measure_device_io",
]
