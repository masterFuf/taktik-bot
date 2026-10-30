"""`app.lift_screen_lock`: what the door of a run does with the lock of the screen, unit by unit.

Platform-neutral: a lock screen belongs to Android. Each platform registers it under the same id, and
it calls the production function (`shared/device/screen.py`, the door's and the network watch's), so
a phone whose lock behaves differently shows it here before a run meets it.
"""

from typing import Any, Dict

from loguru import logger

from bridges.tools.lab.action_test.action_bundle import bundle_device_id
from taktik.core.shared.device.screen import phone_locked_after_lift, read_keyguard_showing


def lift_screen_lock(a, _p) -> Dict[str, Any]:
    """Read the lock, ask a lock to go, and say what is left. No gesture, a code is never typed.

    `lockedBefore` / `lockedAfter`: True, False, or None when `dumpsys window` does not say.
    """
    serial = bundle_device_id(a)
    if not serial:
        msg = "app.lift_screen_lock: no phone serial for this session, nothing was read"
        logger.error(msg)
        return {"success": False, "message": msg}
    locked_before = read_keyguard_showing(serial)
    locked_after = phone_locked_after_lift(serial)
    return {
        "lockedBefore": locked_before,
        "lockedAfter": locked_after,
        "runWouldStart": locked_after is not True,
    }


__all__ = ["lift_screen_lock"]
