"""Persona Analysis bridge runtime class."""

from __future__ import annotations

import time

from bridges.instagram.analysis.runtime.persona_comments import PersonaCommentsMixin
from bridges.instagram.analysis.runtime.persona_media import PersonaMediaMixin
from bridges.instagram.analysis.runtime.persona_posts import PersonaPostsMixin
from bridges.instagram.analysis.runtime.persona_profile import PersonaProfileMixin
from bridges.instagram.runtime.bridge import InstagramBridgeBase
from bridges.instagram.runtime.ipc import _ipc, logger


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
            _ipc.status("launching", "Red\u00e9marrage d'Instagram\u2026")
            if not self._app.restart():
                _ipc.error("Impossible de lancer Instagram", error_code="LAUNCH_FAILED")
                return {"success": False, "error": "Failed to launch Instagram"}
            time.sleep(2)

            nav, error_result = self.open_target_profile(collected)
            if error_result:
                return error_result

            self.capture_profile_screenshot(nav, collected)

            if self.profile_screenshot_only:
                _ipc.status("completed", "Screenshot du profil captur\u00e9")
                return {"success": True, "data": collected}

            self.collect_posts(collected)

            total = len(collected["post_captions"])
            total_comments = len(collected["comments"])
            _ipc.status(
                "completed",
                f"Analyse termin\u00e9e - {total} posts, {total_comments} commentaires collect\u00e9s",
            )

            return {"success": True, "data": collected}

        except Exception as exc:
            logger.exception(f"[PersonaAnalysis] Unexpected error: {exc}")
            _ipc.status("error", str(exc))
            return {"success": False, "error": str(exc)}


__all__ = ["PersonaAnalysisBridge"]
