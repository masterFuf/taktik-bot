"""App lifecycle actions for TikTok compat diagnostics.

Exposes a launch action so the Cartography Lab auto-test can guarantee its
first precondition — TikTok in the foreground — before running any test.
Reuses the TikTok manager (package resolution + main activity).
"""

import time

from loguru import logger

from bridges.compat.diagnostics.actions.tiktok import action
from taktik.core.social_media.tiktok.core.manager import TikTokManager, TIKTOK_PACKAGES


@action("app.launch")
def launch(a, p):
    """Foreground TikTok and confirm it reached the front.

    Reuses the already-connected device facade so the manager does not reconnect.
    """
    mgr = TikTokManager()
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
