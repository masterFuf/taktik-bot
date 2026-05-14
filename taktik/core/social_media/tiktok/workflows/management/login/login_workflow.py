"""
TikTok Login Workflow

Handles the full login flow on a TikTok device session.
TODO: Implement using uiautomator2 selectors once UI dumps are collected.
"""
import time
from loguru import logger
from bridges.common.ipc import IPC

_ipc = IPC()


class TikTokLoginWorkflow:
    """Workflow for logging into TikTok on a connected Android device."""

    def __init__(self, device, device_id: str):
        self.device = device
        self.device_id = device_id
        self.logger = logger.bind(device=device_id)

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
        self.logger.info(f"🔐 TikTok login — @{username}")

        try:
            _ipc.status("running", f"Navigating to login screen...")
            _ipc.log("info", "🔍 Looking for login entry point...")

            # TODO: Implement full login flow using UI selectors
            # Steps to implement (see dumps for actual XPaths):
            # 1. Detect current screen (home / login screen / profile selector)
            # 2. Navigate to login screen if not already there
            #    → Look for "Use phone / email / username" or "Already have an account?"
            # 3. Tap "Use phone / email / username" or "Log in" button
            # 4. Fill username field
            # 5. Fill password field
            # 6. Tap "Log in" button
            # 7. Handle post-login popups (notification permission, etc.)
            # 8. Verify success by checking home screen indicators

            # --- Placeholder until dumps are collected ---
            _ipc.log("warning", "⚠️ TikTok login automation not yet implemented. Collect UI dumps first.")
            return {
                "success": False,
                "message": "TikTok login automation not yet implemented",
                "error_type": "not_implemented",
            }

        except Exception as e:
            self.logger.error(f"Login error: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return {
                "success": False,
                "message": str(e),
                "error_type": "exception",
            }
