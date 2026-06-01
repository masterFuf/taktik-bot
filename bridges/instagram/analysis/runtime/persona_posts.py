"""Post scraping helpers for the Instagram Persona Analysis bridge."""

from __future__ import annotations

import time

from bridges.instagram.runtime.ipc import _ipc, logger


class PersonaPostsMixin:
    """Collect captions and comments from recent posts on the current profile grid."""

    def collect_posts(self, collected: dict) -> None:
        _ipc.status("scraping_posts", f"Scraping des {self.max_posts} derniers posts\u2026")

        from taktik.core.social_media.instagram.actions.atomic.detection import DetectionActions
        from taktik.core.social_media.instagram.actions.atomic.interaction import ClickActions

        detect = DetectionActions(self.device_manager)
        post_actions = ClickActions(self.device_manager)

        for post_idx in range(self.max_posts):
            try:
                if not detect.is_post_grid_visible():
                    self.device.press("back")
                    time.sleep(1)

                _ipc.status(
                    "opening_post",
                    f"Ouverture du post {post_idx + 1}/{self.max_posts}\u2026",
                )

                clicked = post_actions.click_post_in_grid(post_index=post_idx)
                if not clicked:
                    clicked = post_actions.click_post_thumbnail(post_index=post_idx)
                if not clicked:
                    logger.warning(f"[PersonaAnalysis] Could not click post {post_idx}")
                    break
                time.sleep(2)

                caption = self._extract_post_caption()
                if caption:
                    collected["post_captions"].append(caption.strip())
                    _ipc.status(
                        "post_caption_collected",
                        f"Caption post {post_idx + 1} collect\u00e9e",
                    )

                comments = self._collect_comments(post_idx)
                collected["comments"].extend(comments)

                self.device.press("back")
                time.sleep(1.5)

            except Exception as e:
                logger.warning(f"[PersonaAnalysis] Error on post {post_idx}: {e}")
                try:
                    self.device.press("back")
                    time.sleep(1)
                except Exception:
                    pass

    def _extract_post_caption(self) -> str:
        from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_DETAIL_SELECTORS

        for selector in POST_DETAIL_SELECTORS.persona_caption_selectors:
            try:
                elem = self.device.xpath(selector)
                if elem.exists:
                    return elem.get_text() or ""
            except Exception:
                pass

        return ""
