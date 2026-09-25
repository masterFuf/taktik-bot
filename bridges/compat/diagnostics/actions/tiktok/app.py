"""App lifecycle actions for TikTok compat diagnostics.

Exposes a launch action so the Cartography Lab auto-test can guarantee its
first precondition — TikTok in the foreground — before running any test.
Reuses the TikTok manager (package resolution + main activity).
"""

import time

from loguru import logger

from bridges.compat.diagnostics.actions.tiktok import action
from bridges.compat.diagnostics.runtime.action_test.action_bundle import bundle_device_id
from taktik.core.social_media.tiktok.core.manager import TikTokManager, TIKTOK_PACKAGES


@action("app.launch")
def launch(a, p):
    """Foreground TikTok on the session's phone and confirm it reached the front.

    The manager gets the session's serial AND its already-connected device. Built without the
    serial, it relaunched TikTok on the first phone of `adb devices` (measured on 2026-09-23: the
    session drove the 6a, TikTok was stopped and restarted on the 4a), and its adb fallbacks
    (installed package, stop) asked no phone in particular either.
    """
    device_id = bundle_device_id(a)
    if not device_id:
        logger.error("app.launch: the session's phone is unknown, TikTok not launched")
        return {"success": False, "message": "app.launch: unknown phone serial, nothing launched"}

    mgr = TikTokManager(device_id)
    mgr.device_manager.device = a.device  # reuse connected device, skip reconnect
    # Clean restart (force-stop + launch) so a cold start always lands on the home feed,
    # never resuming a trapped sub-screen — keeps the auto-test self-healing.
    if not mgr.restart():
        logger.error("app.launch: failed to start TikTok")
        return False
    for _ in range(16):
        time.sleep(0.6)
        try:
            if a.device.app_current().get("package") in TIKTOK_PACKAGES:
                return True
        except Exception:
            pass
    logger.warning("app.launch: TikTok did not reach foreground in time")
    return False
