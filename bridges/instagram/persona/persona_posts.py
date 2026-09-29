"""Post scraping helpers for the Instagram Persona Analysis bridge."""

from __future__ import annotations

import re
import time

from bridges.instagram.common.ipc import _ipc, logger


def comment_count_signal(text: str):
    """Coarse signal from a post's comment-count label: 0 (none), 1 (has some — exact value
    irrelevant), or None (unknown). Only the 0-vs-nonzero distinction matters: whether to bother
    opening the comment sheet. Handles abbreviated counts ("1.2k") as > 0."""
    t = (text or "").strip()
    if not t:
        return None
    if re.search(r"[1-9]", t):
        return 1
    if "0" in t:
        return 0
    return None


class PersonaPostsMixin:
    """Collect captions and comments from recent posts on the current profile grid."""

    def collect_posts(self, collected: dict) -> None:
        _ipc.status("scraping_posts", f"Recherche de posts comment\u00e9s (objectif {self.max_posts})\u2026")

        from taktik.core.social_media.instagram.actions.atomic.detection import DetectionActions
        from taktik.core.social_media.instagram.workflows.common.post_navigation import (
            open_post_at_position,
        )

        detect = DetectionActions(self.device_manager)

        # Dedup the analyzed account's own writing lines across ALL scanned posts.
        style_seen: set = set()
        posts_with_comments = 0
        # Keep looking PAST comment-less posts to reach `max_posts` posts that actually have comments
        # (the richest voice signal). `open_post_at_position` SCROLLS THE GRID to reveal deeper rows,
        # so the scan is NOT limited to the initially visible posts; bounded so we don't crawl the
        # whole profile. Captions are collected on EVERY opened post.
        max_scan = min(max(self.max_posts * 4, 20), 30)

        for post_idx in range(max_scan):
            if posts_with_comments >= self.max_posts:
                break
            try:
                if not detect.is_post_grid_visible():
                    self.device.press("back")
                    time.sleep(1)

                _ipc.status("opening_post", f"Ouverture du post {post_idx + 1}\u2026")

                # Absolute 1-based position; scrolls the grid to reach posts past the visible ones.
                if not open_post_at_position(self.device, post_idx + 1, logger):
                    logger.info(f"[PersonaAnalysis] No more posts to scan at position {post_idx + 1}")
                    break

                # Caption = the account's own writing too (voice signal) \u2014 collected on every post.
                caption = self._extract_post_caption()
                if caption:
                    collected["post_captions"].append(caption.strip())
                    _ipc.status("post_caption_collected", f"L\u00e9gende du post {post_idx + 1} collect\u00e9e")

                # Skip opening the comment sheet when the post visibly has NO comments (no point
                # clicking the comment button). Unknown count -> open anyway, so a missed read never
                # skips real comments.
                if self._post_comment_count() == 0:
                    _ipc.status("opening_post", f"Post {post_idx + 1} sans commentaire \u2014 suivant")
                else:
                    comments, owner_lines = self._collect_comments(post_idx, style_seen)
                    collected["comments"].extend(comments)
                    collected["writing_style_samples"].extend(owner_lines)
                    if comments:
                        posts_with_comments += 1

                self.device.press("back")
                time.sleep(1.5)

            except Exception as e:
                logger.warning(f"[PersonaAnalysis] Error on post {post_idx}: {e}")
                try:
                    self.device.press("back")
                    time.sleep(1)
                except Exception:
                    pass

    def _post_comment_count(self):
        """Best-effort read of the OPEN post's comment count (0-vs-nonzero only). Returns 0, 1
        (has some) or None (unknown). Uses the catalog's comment-count selectors; unknown when none
        match, so the caller opens the sheet anyway."""
        from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_DETAIL_SELECTORS
        for selector in POST_DETAIL_SELECTORS.post_comments_count_selectors:
            try:
                el = self.device.xpath(selector)
                if not el.exists:
                    continue
                signal = comment_count_signal(el.get_text() or "")
                if signal is not None:
                    return signal
            except Exception:
                continue
        return None

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
