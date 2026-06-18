"""App lifecycle actions for Instagram compat diagnostics.

Exposes a launch action so the Cartography Lab auto-test can guarantee its
first precondition — Instagram in the foreground — before running any
surface/feed test. Clone-aware via the shared DeviceManager owner.
"""

import time

from loguru import logger

from bridges.compat.diagnostics.actions.instagram import action
from taktik.core.clone import get_active_package
from taktik.core.shared.device.manager import DeviceManager


@action("app.launch")
def launch(a, p):
    """Foreground Instagram (or the active clone) and confirm it reached the front.

    Reuses the already-connected device facade so DeviceManager does not reconnect.
    """
    pkg = get_active_package()
    dm = DeviceManager()
    dm.device = a.device  # facade proxies app_start/shell/app_current to the raw device
    if not dm.launch_app(pkg):
        logger.error(f"app.launch: failed to start {pkg}")
        return False
    # Wait for the app to reach the foreground, then verify (selectors load lazily).
    for _ in range(10):
        time.sleep(0.6)
        try:
            if a.device.app_current().get("package") == pkg:
                return True
        except Exception:
            pass
    logger.warning(f"app.launch: {pkg} did not reach foreground in time")
    return False
