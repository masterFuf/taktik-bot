"""What an action costs on the phone: dumps, round trips, waits (M1 of the one-photo spec).

Every call the bot makes to the uiautomator2 server goes through ONE method of the connected
device, `jsonrpc_call(method, params, timeout)`: a dump is `dumpWindowHierarchy`, a wait is
`waitForExists` / `waitUntilGone` / `waitForWindowUpdate`, a `.info` or a click is one more round
trip. `instrument_device_io(device)` wraps that method (and `shell`, the adb round trips) once, at
the connection, so the 57 direct `dump_hierarchy` calls and every `.xpath(...).exists` are counted
without touching them. `measure_device_io(action)` takes the counters before and after an action
and emits the difference through `emit_step("device_io", ...)`, the telemetry the bridges already
forward; `DeviceIoMeasure` does the same for an action that ends in several places.

Measuring changes nothing the bot does: the wrapper calls the original method with the same
arguments and returns what it returns (or raises what it raises). It never raises itself.

The same two doors see every gesture the bot makes on the phone, so the meter also counts them by
kind (`taps`, `long_presses`, `swipes`, `touches`, `keys`, `texts`, `launches`, `stops`): the census
a phone run is reviewed from ("after a run, list every gesture"), emitted with the costs of each
action. A gesture is counted when it is sent, whether or not the server then fails it.
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

# The gestures of the uiautomator2 server, by kind. `click` with a third parameter (a duration) is
# `long_click`; `injectInputEvent` is the raw touch of `d.touch`, one touch per ACTION_DOWN (0).
GESTURE_KINDS = ("taps", "long_presses", "swipes", "touches", "keys", "texts", "launches", "stops")
_SWIPE_METHODS = frozenset({
    "swipe", "swipePoints", "drag", "dragTo", "gesture", "pinchIn", "pinchOut",
    "flingForward", "flingBackward", "flingToBeginning", "flingToEnd",
    "scrollForward", "scrollBackward", "scrollTo", "scrollToBeginning", "scrollToEnd",
})
_KEY_METHODS = frozenset({"pressKey", "pressKeyCode"})
_TEXT_METHODS = frozenset({"setText", "clearTextField", "clearInputText", "pasteClipboard"})
_TOUCH_DOWN = 0
# What an adb shell command does on the screen, by its first words. The keyboards type by
# broadcast: the Taktik keyboard (`ADB_INPUT_*`, `ADB_CLEAR_TEXT`) and uiautomator2's (`ADB_KEYBOARD_*`).
_SHELL_GESTURES = (
    ("input tap", "taps"),
    ("input swipe", "swipes"),
    ("input draganddrop", "swipes"),
    ("input keyevent", "keys"),
    ("input text", "texts"),
    ("am start", "launches"),
    ("monkey -p", "launches"),
    ("am force-stop", "stops"),
)
_TYPING_BROADCASTS = ("ADB_INPUT_", "ADB_CLEAR_TEXT", "ADB_KEYBOARD_INPUT", "ADB_KEYBOARD_CLEAR", "ADB_KEYBOARD_SMART_ENTER")


def rpc_gesture_kind(method: str, params: Any = None) -> str | None:
    """The kind of gesture a server call makes, or None for a read (a dump, a wait, `.info`)."""
    if method == "click":
        return "long_presses" if isinstance(params, (list, tuple)) and len(params) >= 3 else "taps"
    if method == "longClick":
        return "long_presses"
    if method == "injectInputEvent":
        first = params[0] if isinstance(params, (list, tuple)) and params else None
        return "touches" if first == _TOUCH_DOWN else None
    if method in _SWIPE_METHODS:
        return "swipes"
    if method in _KEY_METHODS:
        return "keys"
    if method in _TEXT_METHODS:
        return "texts"
    return None


def shell_gesture_kind(command: Any) -> str | None:
    """The kind of gesture an adb shell command makes, or None for a read (`dumpsys`, `getprop`...)."""
    text = " ".join(str(part) for part in command) if isinstance(command, (list, tuple)) else str(command or "")
    text = " ".join(text.split())
    for prefix, kind in _SHELL_GESTURES:
        if text.startswith(prefix):
            return kind
    if text.startswith("am broadcast") and any(marker in text for marker in _TYPING_BROADCASTS):
        return "texts"
    return None


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
                **{kind: 0 for kind in GESTURE_KINDS},
            }

    def record_rpc(self, method: str, elapsed_ms: float, failed: bool = False, params: Any = None) -> None:
        gesture = rpc_gesture_kind(method, params)
        with self._lock:
            totals = self._totals
            totals["rpc"] += 1
            if gesture:
                totals[gesture] += 1
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

    def record_shell(self, elapsed_ms: float, failed: bool = False, command: Any = None) -> None:
        gesture = shell_gesture_kind(command)
        with self._lock:
            self._totals["shells"] += 1
            if gesture:
                self._totals[gesture] += 1
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
                meter.record_rpc(str(method), _elapsed_ms(started_at), failed, params)

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
                    command = args[0] if args else kwargs.get("cmdargs", kwargs.get("cmd"))
                    meter.record_shell(_elapsed_ms(started_at), failed, command)

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


class DeviceIoMeasure:
    """What one action costs on the phone, from its creation to `finish()`.

    For an action that ends in several places (a loop turn that `continue`s): each exit calls
    `finish(**outcome)` with what the action turned out to be. Emits once; an action that never
    finishes emits nothing.
    """

    def __init__(self, action: str, meter: DeviceIoMeter = METER, **context: Any) -> None:
        self._action = action
        self._meter = meter
        self._context = context
        self._before = meter.snapshot()
        self._started_at = time.perf_counter()
        self._finished = False

    def finish(self, **outcome: Any) -> None:
        """Emit one `device_io` step. Fields: `dumps`, `dump_ms`, `rpc` (every server round trip,
        dumps included), `rpc_ms`, `waits`, `wait_ms` (server-side waits), `shells`, `shell_ms`
        (adb), `errors`, `gestures` (the gestures made, by kind: `GESTURE_KINDS`), `total_ms` (wall
        time), `other_ms` (the rest: parsing, sleeps, the bot's own work), then the context and the
        outcome."""
        if self._finished:
            return
        self._finished = True
        try:
            total_ms = _elapsed_ms(self._started_at)
            delta = _delta(self._before, self._meter.snapshot())
            gestures = {kind: delta.pop(kind, 0) for kind in GESTURE_KINDS}
            device_ms = delta.get("rpc_ms", 0.0) + delta.get("shell_ms", 0.0)
            fields = {
                "total_ms": round(total_ms, 1),
                "other_ms": round(max(total_ms - device_ms, 0.0), 1),
                **delta,
                "gestures": gestures,
                **self._context,
                **outcome,
            }
            emit_step("device_io", action=self._action, **fields)
        except Exception as exc:  # telemetry must never break an action
            logger.debug(f"device io measure skipped for {self._action}: {exc}")


@contextmanager
def measure_device_io(action: str, meter: DeviceIoMeter = METER, **context: Any) -> Iterator[Dict[str, Any]]:
    """Emit what `action` cost on the phone: one `device_io` step when it ends (even on error).

    Yields a dict: what the action learns only by running (the screen it found) goes there and is
    emitted with the costs. Fields: see `DeviceIoMeasure.finish`.
    """
    measure = DeviceIoMeasure(action, meter, **context)
    outcome: Dict[str, Any] = {}
    try:
        yield outcome
    finally:
        measure.finish(**outcome)


__all__ = [
    "DUMP_METHODS",
    "GESTURE_KINDS",
    "WAIT_METHODS",
    "DeviceIoMeasure",
    "DeviceIoMeter",
    "METER",
    "instrument_device_io",
    "measure_device_io",
    "rpc_gesture_kind",
    "shell_gesture_kind",
]
