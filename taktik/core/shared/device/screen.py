"""The screen of a connected phone: its size and its lock, one reading each for the whole engine.

Every gesture computed in proportion of the screen (a scroll of 60 % of its height, a tap in its
middle) starts from this size, so a wrong size is a wrong gesture that does not fail. The size is
read, never made up:

1. uiautomator2's `deviceInfo` (`device.info`, `displayWidth` / `displayHeight`), the size in the
   current orientation;
2. when the server cannot answer it, `wm size` through the engine's adb door: Android 17 refuses
   `deviceInfo` with `IllegalStateException: ApplicationSharedMemory not initialized` while its
   UiDevice has no window context (Pixel 6 Pro, 2026-10-24; the first calls of a run, later ones may
   answer), where the engine took 1080 x 1920 for a 1440 x 3120 screen. `wm size` gives the size of
   the natural orientation (portrait on a phone, the one Instagram and TikTok are driven in), the
   override first when one is set (what the apps are laid out on).

When neither answers, `ScreenSizeUnreadable`: the caller says so, it does not guess.

**The lock.** A run on a locked phone taps on the lock screen and ends on a motive that is not its
own: a scraping on a C57S (Android 14, 2026-10-30) ran a minute there and ended
`target_never_reached` (« Search tab not found », deep link « No handle shown »). `dumpsys window`
says the state (`isKeyguardShowing`); `phone_locked_after_lift` lifts a lock without code, by a
dismissal and never a gesture, and reads the state again. A lock with a code stays, whatever is sent:
the second reading is the verdict, the engine never has to know which kind of lock it met. Who decides
what to do of the verdict: the run's door (`diagnostics/run_door.py`) and the watch of a run
(`network_watch.py`).
"""

import time
from typing import Any, List, Optional, Tuple, cast

from loguru import logger

from taktik.core.shared.device.adb import run_adb_shell_process

#: The lines of `wm size`, the one an app is laid out on first.
_WM_SIZE_LABELS = ("Override size:", "Physical size:")

#: The state of the lock in `dumpsys window`, on a line of its own (Android 14) or among others (Android 11).
_KEYGUARD_MARK = "isKeyguardShowing="

#: How many times the lock is read after the dismissal, and how long apart: it takes its animation.
LIFT_CHECKS = 4
LIFT_CHECK_DELAY_S = 0.5


class ScreenSizeUnreadable(RuntimeError):
    """Neither uiautomator2 nor `wm size` gave the screen size."""


def read_screen_size(device: Any) -> Tuple[int, int]:
    """(width, height) in pixels of the phone behind `device` (a uiautomator2 device, the clone
    proxy or a facade, all of which answer `info` and `serial`). Raises `ScreenSizeUnreadable`."""
    try:
        info = device.info
        return int(info["displayWidth"]), int(info["displayHeight"])
    except Exception as exc:
        info_error = exc
    serial = _serial_of(device)
    size = wm_size(serial) if serial else None
    if size is None:
        raise ScreenSizeUnreadable(
            f"screen size unread: deviceInfo failed ({_first_line(info_error)}) and wm size "
            f"{'gave nothing' if serial else 'needs a serial the device does not have'}"
        )
    logger.debug(f"Screen size read by wm size ({size[0]}x{size[1]}): deviceInfo failed ({_first_line(info_error)})")
    return size


def screen_size_of(device: Any) -> Tuple[int, int]:
    """(width, height) of the screen behind any device a caller holds: a facade keeps the size it
    read once (`BaseDeviceFacade.get_screen_size`), a uiautomator2 device or the clone proxy is read
    (`read_screen_size`). Raises `ScreenSizeUnreadable`."""
    keeper = getattr(device, "get_screen_size", None)
    if callable(keeper):
        width, height = cast(Tuple[int, int], keeper())
        return int(width), int(height)
    return read_screen_size(device)


def wm_size(serial: str) -> Optional[Tuple[int, int]]:
    """The size `adb shell wm size` gives, the override first; None, and why in the log, when the
    phone gives none."""
    try:
        result = run_adb_shell_process(serial, ["wm", "size"])
    except Exception as exc:
        logger.warning(f"wm size could not run on {serial}: {exc}")
        return None
    if result.returncode != 0:
        logger.warning(f"wm size failed on {serial} (exit {result.returncode}): {(result.stderr or '').strip()}")
        return None
    size = parse_wm_size(result.stdout or "")
    if size is None:
        logger.warning(f"wm size answered no size on {serial}: {(result.stdout or '').strip()!r}")
    return size


def parse_wm_size(output: str) -> Optional[Tuple[int, int]]:
    """(width, height) from the text of `wm size` ("Physical size: 1440x3120", and an
    "Override size: ..." line when one is set, which wins); None when it holds no size."""
    lines = [line.strip() for line in output.splitlines()]
    for label in _WM_SIZE_LABELS:
        for line in lines:
            if not line.startswith(label):
                continue
            width, _x, height = line[len(label):].strip().partition("x")
            if width.isdigit() and height.isdigit():
                return int(width), int(height)
    return None


def parse_keyguard_showing(output: str) -> Optional[bool]:
    """Whether the text of `dumpsys window` says the lock screen is up; None when it does not say."""
    _before, mark, after = output.partition(_KEYGUARD_MARK)
    if not mark:
        return None
    if after.startswith("true"):
        return True
    return False if after.startswith("false") else None


def read_keyguard_showing(serial: str) -> Optional[bool]:
    """Whether the lock screen of the phone is up; None, and why in the log, when it cannot be read."""
    output = _dumpsys_window(serial)
    if output is None:
        return None
    showing = parse_keyguard_showing(output)
    if showing is None:
        logger.debug(f"dumpsys window on {serial} does not say the state of the lock")
    return showing


def phone_locked_after_lift(serial: str) -> Optional[bool]:
    """True when the phone stays locked once its lock was asked to go, False when it is not locked
    (any more), None when the state cannot be read: no conclusion, and nothing sent to the phone."""
    showing = read_keyguard_showing(serial)
    if not showing:
        return showing
    logger.info(f"{serial} is locked: asking the lock to go")
    # The screen first: the lock of a phone asleep does not go while its screen is off.
    _tell_phone(serial, ["input", "keyevent", "KEYCODE_WAKEUP"])
    _tell_phone(serial, ["wm", "dismiss-keyguard"])
    for _check in range(LIFT_CHECKS):
        time.sleep(LIFT_CHECK_DELAY_S)
        showing = read_keyguard_showing(serial)
        if showing is False:
            logger.info(f"{serial}: the lock is lifted")
            return False
    return showing


def _dumpsys_window(serial: str) -> Optional[str]:
    try:
        result = run_adb_shell_process(serial, ["dumpsys", "window"], encoding="utf-8", errors="replace")
    except Exception as exc:
        logger.debug(f"dumpsys window could not run on {serial}: {exc}")
        return None
    if result.returncode != 0:
        logger.debug(f"dumpsys window failed on {serial} (exit {result.returncode}): {(result.stderr or '').strip()}")
        return None
    return result.stdout or ""


def _tell_phone(serial: str, command: List[str]) -> None:
    """A command the next reading of the lock judges: its own failure is only said here."""
    try:
        result = run_adb_shell_process(serial, command)
    except Exception as exc:
        logger.warning(f"{' '.join(command)} could not run on {serial}: {exc}")
        return
    if result.returncode != 0:
        logger.warning(f"{' '.join(command)} failed on {serial} (exit {result.returncode}): {(result.stderr or '').strip()}")


def _serial_of(device: Any) -> Optional[str]:
    try:
        serial = device.serial
    except Exception as exc:
        logger.debug(f"No serial on the device for wm size: {exc}")
        return None
    return serial if isinstance(serial, str) and serial else None


def _first_line(exc: BaseException) -> str:
    text = str(exc).strip()
    return text.splitlines()[0][:200] if text else type(exc).__name__


__all__ = [
    "LIFT_CHECKS",
    "LIFT_CHECK_DELAY_S",
    "ScreenSizeUnreadable",
    "parse_keyguard_showing",
    "parse_wm_size",
    "phone_locked_after_lift",
    "read_keyguard_showing",
    "read_screen_size",
    "screen_size_of",
    "wm_size",
]
