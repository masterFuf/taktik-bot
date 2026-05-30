"""
TikTok Login Workflow

Handles the full login flow on a TikTok device session.
TODO: Implement using uiautomator2 selectors once UI dumps are collected.
"""

from contextvars import ContextVar
from loguru import logger


class _NullNotifier:
    def status(self, *args, **kwargs):
        return None

    def log(self, *args, **kwargs):
        return None


_NULL_NOTIFIER = _NullNotifier()
_CURRENT_NOTIFIER: ContextVar = ContextVar("tiktok_login_notifier", default=_NULL_NOTIFIER)


class _NotifierProxy:
    def __getattr__(self, name):
        return getattr(_CURRENT_NOTIFIER.get(), name)


_ipc = _NotifierProxy()


class TikTokLoginWorkflow:
    """Workflow for logging into TikTok on a connected Android device."""

    def __init__(self, device, device_id: str, notifier=None):
        self.device = device
        self.device_id = device_id
        self.logger = logger.bind(device=device_id)
        self._notifier = notifier or _NULL_NOTIFIER

    def execute(
        self,
        username: str,
        password: str,
        max_retries: int = 3,
        save_session: bool = True,
    ) -> dict:
        """
        Execute the TikTok login workflow.

        Returns:
            dict with keys: success (bool), message (str), error_type (str|None)
        """
        self.logger.info(f"TikTok login - @{username}")
        token = _CURRENT_NOTIFIER.set(self._notifier)

        try:
            _ipc.status("running", "Navigating to login screen...")
            _ipc.log("info", "Looking for login entry point...")

            # TODO: Implement full login flow using UI selectors
            # Steps to implement (see dumps for actual XPaths):
            # 1. Detect current screen (home / login screen / profile selector)
            # 2. Navigate to login screen if not already there
            #    -> Look for "Use phone / email / username" or "Already have an account?"
            # 3. Tap "Use phone / email / username" or "Log in" button
            # 4. Fill username field
            # 5. Fill password field
            # 6. Tap "Log in" button
            # 7. Handle post-login popups (notification permission, etc.)
            # 8. Verify success by checking home screen indicators

            _ipc.log("warning", "TikTok login automation not yet implemented. Collect UI dumps first.")
            return {
                "success": False,
                "message": "TikTok login automation not yet implemented",
                "error_type": "not_implemented",
            }

        except Exception as exc:
            self.logger.exception("TikTok login failed")
            return {
                "success": False,
                "message": str(exc),
                "error_type": "exception",
            }
        finally:
            _CURRENT_NOTIFIER.reset(token)
