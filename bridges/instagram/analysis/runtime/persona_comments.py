"""Comment scraping helpers for the Instagram Persona Analysis bridge.

Besides the raw comment texts used to infer the persona, this also captures the analyzed
account's OWN lines in the comments (its top-level comments and its replies to other people) —
an authentic corpus of how it writes. Those samples ride along on the persona result and are fed
to the AI so Taktik Agent's smart comments sound like the account
(`app/ai/providers/openrouter.py::_build_style_block`). "Self" = the analyzed profile owner, so
the same flow serves a prospect (public) and our own account (connected).
"""

from __future__ import annotations

import time

from bridges.instagram.runtime.ipc import _ipc, logger


def owner_lines_from_comment_descs(desc_author_pairs, owner_username, seen=None,
                                   min_len: int = 3, max_len: int = 240):
    """Keep the comment lines AUTHORED BY the analyzed account -> its writing samples.

    Pure (no device): given `(content_desc, author)` pairs read off the comments sheet — where a
    row's content-desc is "<author> <comment text>" — returns the owner's own lines with the author
    handle stripped off, whitespace-collapsed, length-bounded and deduped (case-insensitively).
    `seen` lets the caller dedup ACROSS posts. Absent owner / no match -> [].
    """
    owner = (owner_username or "").lstrip("@").strip().lower()
    if not owner:
        return []
    if seen is None:
        seen = set()

    lines = []
    for desc, author in desc_author_pairs:
        handle = (author or "").lstrip("@").strip().lower()
        if not handle or handle != owner:
            continue
        # The row's content-desc leads with the author handle; strip it to keep just the text.
        text = " ".join((desc or "").replace(author or "", "", 1).split()).strip()
        if len(text) < min_len or len(text) > max_len:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        lines.append(text)
    return lines


class PersonaCommentsMixin:
    """Collect comments from a currently opened Persona Analysis post."""

    def _collect_comments(self, post_idx: int, style_seen: set = None):
        """Open the comments section and collect up to max_comments text comments.

        Returns `(comments, owner_lines)` where `comments` is the raw comment texts (persona
        inference, unchanged) and `owner_lines` are the lines authored by the analyzed account (its
        writing voice). `style_seen` dedups owner lines across posts.
        """
        comments = []
        owner_lines = []
        owner = getattr(self, "target_username", "") or ""
        if style_seen is None:
            style_seen = set()
        try:
            from taktik.core.social_media.instagram.actions.atomic.scroll.context_scroll import (
                comments_scroll_path,
            )
            from taktik.core.social_media.instagram.ui.selectors.surfaces.post import (
                POST_COMMENTS_SELECTORS,
                POST_DETAIL_SELECTORS,
            )

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
                return comments, owner_lines

            is_open = any(
                self.device.xpath(s).exists
                for s in POST_COMMENTS_SELECTORS.comments_view_indicators[:2]
            )
            if not is_open:
                self.device.press("back")
                return comments, owner_lines

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

                    # Attribute the analyzed account's OWN lines from the rows currently on screen
                    # (its writing voice). Reveal its REPLIES first (nested under others' comments).
                    self._expand_comment_replies(POST_COMMENTS_SELECTORS)
                    owner_lines.extend(
                        self._scan_owner_comment_lines(owner, style_seen, POST_DETAIL_SELECTORS)
                    )

                    if not found_new:
                        scroll_attempts += 1
                    else:
                        scroll_attempts = 0
                    if len(comments) < self.max_comments:
                        # Same bounds-scoped geometry as the production comments scroll. This used
                        # to be swipe(540, 1200, 540, 400): a 1080x2340 phone written down as four
                        # constants, so on any other screen it started off the sheet and scraped
                        # nothing — silently, since an empty scan just ends the loop.
                        screen_w, screen_h = self.device.window_size()
                        (start_x, start_y), (end_x, end_y) = comments_scroll_path(
                            self.device, int(screen_w), int(screen_h), logger
                        )
                        self.device.swipe(start_x, start_y, end_x, end_y, duration=0.5)
                        time.sleep(0.8)
                except Exception:
                    break

            _ipc.status(
                "comments_collected",
                f"{len(comments)} commentaires collectés pour le post {post_idx + 1}"
                + (f" · {len(owner_lines)} de sa plume" if owner_lines else ""),
            )

        except Exception as e:
            logger.warning(f"[PersonaAnalysis] Comment scraping error: {e}")

        finally:
            try:
                self.device.press("back")
                time.sleep(1)
            except Exception:
                pass

        return comments, owner_lines

    def _expand_comment_replies(self, comments_selectors) -> None:
        """Best-effort: tap visible 'View X replies' to reveal replies (where the owner's replies
        live). Reuses the production expand-replies selector; bounded to avoid loops."""
        try:
            reply_btns = self.device.xpath(comments_selectors.expand_replies_selector)
            if reply_btns.exists:
                for btn in reply_btns.all()[:3]:
                    try:
                        btn.click()
                        time.sleep(0.4)
                    except Exception:
                        pass
        except Exception:
            pass

    def _scan_owner_comment_lines(self, owner: str, style_seen: set, detail_selectors) -> list:
        """Read the comment rows currently on screen and return the analyzed account's own lines.

        Reuses the production comment-row read (a row is a ViewGroup whose content-desc is
        "<author> <text>", with the author handle exposed as a child Button) — same technique as
        the engagement comment scraper, so no new selector and no invented path. Defensive: any
        read error yields no line rather than breaking persona collection.
        """
        if not owner:
            return []
        pairs = []
        try:
            view_groups = self.device.xpath(detail_selectors.all_view_group_nodes_selector).all()
        except Exception:
            return []
        for vg in view_groups:
            try:
                desc = (vg.info.get("contentDescription") or "").strip()
                if len(desc) < 3:
                    continue
                author = None
                children = vg.child("android.widget.Button")
                if children.exists:
                    for child in (children.all() if hasattr(children, "all") else [children]):
                        token = child.get_text() if hasattr(child, "get_text") else ""
                        if token and " " not in token and len(token) <= 30:
                            author = token
                            break
                if author:
                    pairs.append((desc, author))
            except Exception:
                continue
        return owner_lines_from_comment_descs(pairs, owner, seen=style_seen)
