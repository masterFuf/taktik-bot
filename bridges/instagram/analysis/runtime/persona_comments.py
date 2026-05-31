"""Comment scraping helpers for the Instagram Persona Analysis bridge."""

from __future__ import annotations

import time

from bridges.instagram.runtime.ipc import _ipc, logger


class PersonaCommentsMixin:
    """Collect comments from a currently opened Persona Analysis post."""

    def _collect_comments(self, post_idx: int) -> list:
        """Open the comments section and collect up to max_comments text comments."""
        comments = []
        try:
            from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_COMMENTS_SELECTORS

            _ipc.status(
                "scraping_comments",
                f"Collecte des commentaires du post {post_idx + 1}…",
            )

            opened = False
            for selector in POST_COMMENTS_SELECTORS.comment_button_selectors[:2]:
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

            is_open = any(
                self.device.xpath(s).exists
                for s in POST_COMMENTS_SELECTORS.comments_view_indicators[:2]
            )
            if not is_open:
                self.device.press("back")
                return comments

            seen = set()
            scroll_attempts = 0
            while len(comments) < self.max_comments and scroll_attempts < 4:
                try:
                    comment_nodes = self.device.xpath(POST_COMMENTS_SELECTORS.comment_text_nodes_selector).all()
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

            _ipc.status(
                "comments_collected",
                f"{len(comments)} commentaires collectés pour le post {post_idx + 1}",
            )

        except Exception as e:
            logger.warning(f"[PersonaAnalysis] Comment scraping error: {e}")

        finally:
            try:
                self.device.press("back")
                time.sleep(1)
            except Exception:
                pass

        return comments
