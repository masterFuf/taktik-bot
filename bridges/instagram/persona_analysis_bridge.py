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
import json
import time

# Bootstrap: UTF-8 + loguru + sys.path
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)
from bridges.common.bootstrap import setup_environment
setup_environment()

from bridges.common.signal_handler import setup_signal_handlers
from bridges.instagram.base import InstagramBridgeBase, _ipc, logger

setup_signal_handlers()


class PersonaAnalysisBridge(InstagramBridgeBase):
    """Bridge that scrapes own Instagram profile to build persona data."""

    def __init__(self, device_id: str, config: dict, package_name: str = None):
        super().__init__(device_id, package_name=package_name)
        self.config = config
        self.target_username = config.get("username", "").lstrip("@").lower()
        self.max_posts = int(config.get("max_posts", 4))
        self.max_comments = int(config.get("max_comments_per_post", 15))

    # ------------------------------------------------------------------
    def run(self):
        collected = {
            "username": self.target_username,
            "biography": None,
            "followers_count": None,
            "following_count": None,
            "posts_count": None,
            "post_captions": [],
            "comments": [],
        }

        try:
            # ── Step 1: Launch Instagram ──────────────────────────────
            _ipc.status("launching", "Lancement d'Instagram…")
            if not self._app.launch():
                _ipc.error("Impossible de lancer Instagram", error_code="LAUNCH_FAILED")
                return {"success": False, "error": "Failed to launch Instagram"}
            time.sleep(2)

            # ── Step 2: Navigate to own profile tab ───────────────────
            _ipc.status("navigating_own_profile", "Navigation vers l'onglet profil…")
            from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
            from taktik.core.social_media.instagram.actions.business.management.profile import ProfileBusiness

            nav = NavigationActions(self.device_manager)
            profile_biz = ProfileBusiness(self.device_manager)

            nav.navigate_to_profile_tab()
            time.sleep(2)

            # ── Step 3: Detect logged-in username ─────────────────────
            _ipc.status("detecting_account", "Détection du compte connecté…")
            own_info = profile_biz.get_complete_profile_info(navigate_if_needed=False)
            own_username = (own_info.get("username") or "").lower() if own_info else ""

            is_own = (own_username == self.target_username)

            if is_own:
                _ipc.status("own_profile_detected",
                    f"Compte @{self.target_username} connecté — profil propre utilisé")
                # Already on profile page, collect basic info
                if own_info:
                    collected["biography"]       = own_info.get("biography")
                    collected["followers_count"] = own_info.get("followers_count")
                    collected["following_count"] = own_info.get("following_count")
                    collected["posts_count"]     = own_info.get("posts_count")
            else:
                # Navigate to target's public profile
                _ipc.status("navigating_public_profile",
                    f"Compte différent ({own_username or 'inconnu'}), navigation vers @{self.target_username}…")
                ok = nav.navigate_to_profile(self.target_username)
                if not ok:
                    _ipc.error(f"Impossible d'accéder au profil @{self.target_username}")
                    return {"success": False, "error": f"Cannot navigate to @{self.target_username}"}
                time.sleep(2)
                profile_info = profile_biz.get_complete_profile_info(navigate_if_needed=False)
                if profile_info:
                    collected["biography"]       = profile_info.get("biography")
                    collected["followers_count"] = profile_info.get("followers_count")
                    collected["following_count"] = profile_info.get("following_count")
                    collected["posts_count"]     = profile_info.get("posts_count")

            # ── Step 4: Scrape posts ───────────────────────────────────
            _ipc.status("scraping_posts", f"Scraping des {self.max_posts} derniers posts…")
            from taktik.core.social_media.instagram.actions.atomic.interaction.post_interaction import PostInteractionActions
            from taktik.core.social_media.instagram.ui.selectors import POST_SELECTORS

            post_actions = PostInteractionActions(self.device_manager)

            for post_idx in range(self.max_posts):
                try:
                    # Make sure we're on the profile grid
                    from taktik.core.social_media.instagram.actions.atomic.detection import DetectionActions
                    detect = DetectionActions(self.device_manager)

                    if not detect.is_post_grid_visible():
                        # Try pressing back to go back to grid
                        self.device.press("back")
                        time.sleep(1)

                    _ipc.status("opening_post",
                        f"Ouverture du post {post_idx + 1}/{self.max_posts}…")

                    clicked = post_actions.click_post_thumbnail(post_index=post_idx)
                    if not clicked:
                        logger.warning(f"[PersonaAnalysis] Could not click post {post_idx}")
                        break
                    time.sleep(2)

                    # Get caption
                    caption = ""
                    for selector in [
                        '//com.instagram.ui.widget.textview.IgTextLayoutView',
                        '//*[@resource-id="com.instagram.android:id/media_viewer_caption_text_view"]',
                    ]:
                        try:
                            elem = self.device.xpath(selector)
                            if elem.exists:
                                caption = elem.get_text() or ""
                                break
                        except Exception:
                            pass

                    if caption:
                        collected["post_captions"].append(caption.strip())
                        _ipc.status("post_caption_collected",
                            f"Caption post {post_idx + 1} collectée")

                    # Get comments
                    comments = self._collect_comments(post_idx)
                    collected["comments"].extend(comments)

                    # Go back to profile
                    self.device.press("back")
                    time.sleep(1.5)

                except Exception as e:
                    logger.warning(f"[PersonaAnalysis] Error on post {post_idx}: {e}")
                    try:
                        self.device.press("back")
                        time.sleep(1)
                    except Exception:
                        pass

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

    # ------------------------------------------------------------------
    def _collect_comments(self, post_idx: int) -> list:
        """Open the comments section and collect up to max_comments text comments."""
        comments = []
        try:
            from taktik.core.social_media.instagram.ui.selectors import POST_SELECTORS

            # Open comments
            _ipc.status("scraping_comments",
                f"Collecte des commentaires du post {post_idx + 1}…")

            # Try tapping comment icon
            opened = False
            for selector in POST_SELECTORS.comment_button_selectors[:2]:
                try:
                    elem = self.device.xpath(selector)
                    if elem.exists:
                        elem.click()
                        time.sleep(2)
                        opened = True
                        break
                except Exception:
                    pass

            if not opened:
                return comments

            # Verify comments view is open
            is_open = any(
                self.device.xpath(s).exists
                for s in POST_SELECTORS.comments_view_indicators[:2]
            )
            if not is_open:
                self.device.press("back")
                return comments

            # Collect comment text elements
            seen = set()
            scroll_attempts = 0
            while len(comments) < self.max_comments and scroll_attempts < 4:
                try:
                    comment_nodes = self.device.xpath(
                        '//android.widget.TextView[contains(@resource-id, "row_comment_textview_comment") or '
                        'contains(@resource-id, "comment_text")]'
                    ).all()
                    found_new = False
                    for node in comment_nodes:
                        try:
                            text = node.get_text() or ""
                            text = text.strip()
                            if text and text not in seen and len(text) > 3:
                                seen.add(text)
                                comments.append(text)
                                found_new = True
                                if len(comments) >= self.max_comments:
                                    break
                        except Exception:
                            pass
                    if not found_new:
                        scroll_attempts += 1
                    else:
                        scroll_attempts = 0
                    if len(comments) < self.max_comments:
                        self.device.swipe(540, 1200, 540, 400, duration=0.5)
                        time.sleep(0.8)
                except Exception:
                    break

            _ipc.status("comments_collected",
                f"{len(comments)} commentaires collectés pour le post {post_idx + 1}",
                stats={"count": len(comments)})

        except Exception as e:
            logger.warning(f"[PersonaAnalysis] Comment scraping error: {e}")

        finally:
            try:
                self.device.press("back")
                time.sleep(1)
            except Exception:
                pass

        return comments


# =============================================================================
# Entry point
# =============================================================================

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "Usage: persona_analysis_bridge.py <config.json>"}))
        sys.exit(1)

    config_path = sys.argv[1]
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(json.dumps({"success": False, "error": f"Failed to read config: {e}"}))
        sys.exit(1)

    device_id   = config.get("deviceId")
    package_name = config.get("packageName")

    if not device_id:
        print(json.dumps({"success": False, "error": "deviceId is required"}))
        sys.exit(1)

    bridge = PersonaAnalysisBridge(device_id, config, package_name=package_name)
    result = bridge.run()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
