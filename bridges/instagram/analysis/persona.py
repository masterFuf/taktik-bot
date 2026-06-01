#!/usr/bin/env python3
"""
Persona Analysis Bridge — scrapes an Instagram account's own posts & comments
to build a persona profile for the AI.

Workflow:
  1. Launch Instagram on the device
  2. Navigate to own profile tab → detect logged-in username
  3. If logged-in username == target: use own profile (already there)
     Else: navigate to @username via search/deeplink
  4. Collect profile bio + stats (fallback: already have it in DB)
  5. Open first N posts → extract caption
  6. Open comments for each post → extract first M comments
  7. Emit IPC events at every step for live UI feedback
  8. Return all collected data as JSON

Config JSON (from sys.argv[1]):
  deviceId             (str,  required)
  username             (str,  required) — target account username
  packageName          (str,  optional) — clone package
  max_posts            (int,  default 4)
  max_comments_per_post (int, default 15)
"""

import sys
import os
import time

# Bootstrap: UTF-8 + loguru + sys.path
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)
from bridges.common.runtime.bootstrap import setup_environment
setup_environment()

from bridges.common.runtime.signal_handler import setup_signal_handlers
from bridges.instagram.runtime.bridge import InstagramBridgeBase
from bridges.instagram.runtime.ipc import _ipc, logger
from bridges.instagram.analysis.runtime.persona_comments import PersonaCommentsMixin
from bridges.instagram.analysis.runtime.persona_media import PersonaMediaMixin
from bridges.instagram.analysis.runtime.persona_posts import PersonaPostsMixin
from bridges.instagram.analysis.runtime.persona_profile import PersonaProfileMixin

setup_signal_handlers()


class PersonaAnalysisBridge(
    PersonaProfileMixin,
    PersonaPostsMixin,
    PersonaMediaMixin,
    PersonaCommentsMixin,
    InstagramBridgeBase,
):
    """Bridge that scrapes own Instagram profile to build persona data."""

    def __init__(self, device_id: str, config: dict, package_name: str = None):
        super().__init__(device_id, package_name=package_name)
        self.config = config
        self.target_username = config.get("username", "").lstrip("@").lower()
        self.max_posts = int(config.get("max_posts", 4))
        self.max_comments = int(config.get("max_comments_per_post", 15))
        self.profile_screenshot_only = bool(config.get("profile_screenshot_only", False))

    # ------------------------------------------------------------------
    def run(self):
        collected = {
            "username": self.target_username,
            "full_name": None,
            "biography": None,
            "website": None,
            "followers_count": None,
            "following_count": None,
            "posts_count": None,
            "post_captions": [],
            "comments": [],
            "profile_screenshot": None,
        }

        try:
            # ── Step 1: Restart Instagram (clean state) ───────────────
            _ipc.status("launching", "Redémarrage d'Instagram…")
            if not self._app.restart():
                _ipc.error("Impossible de lancer Instagram", error_code="LAUNCH_FAILED")
                return {"success": False, "error": "Failed to launch Instagram"}
            time.sleep(2)

            nav, error_result = self.open_target_profile(collected)
            if error_result:
                return error_result

            self.capture_profile_screenshot(nav, collected)

            if self.profile_screenshot_only:
                _ipc.status("completed", "Screenshot du profil capturé")
                return {"success": True, "data": collected}

            self.collect_posts(collected)

            # ── Done ──────────────────────────────────────────────────
            total = len(collected["post_captions"])
            total_comments = len(collected["comments"])
            _ipc.status("completed",
                f"Analyse terminée — {total} posts, {total_comments} commentaires collectés")

            return {"success": True, "data": collected}

        except Exception as exc:
            logger.exception(f"[PersonaAnalysis] Unexpected error: {exc}")
            _ipc.status("error", str(exc))
            return {"success": False, "error": str(exc)}

# =============================================================================
# Entry point
# =============================================================================

def main():
    from bridges.instagram.analysis.runtime.persona_commands import run_persona_analysis_cli

    run_persona_analysis_cli(sys.argv[1:])


if __name__ == "__main__":
    main()
