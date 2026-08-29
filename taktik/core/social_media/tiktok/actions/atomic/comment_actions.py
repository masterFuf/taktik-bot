"""Atomic actions on the TikTok comment sheet.

The surface was opened for the first time on 2026-08-29 and its catalogue rebuilt from real
screens; before that it held six guessed Android resource names that scored 0 on both shipped
versions. Everything here rests on that measurement, and on one shape it forced:

**Nothing is read before the sheet says it is open.** `title`, the id carrying a comment's author,
is not comment-specific — it also resolves on the inbox and on the feed. Reading rows without the
gate returns one confident, wrong "comment" from whatever screen happens to be up.

**A send is confirmed by the composer emptying, not by the tap landing.** Same rule, same reason
as `DMActions.send_message`, which used to report success on a message still sitting on screen.
"""

import time
from typing import Any, Dict, List, Optional

from taktik.core.shared.input.taktik_keyboard import (
    activate_taktik_keyboard,
    clear_text_with_taktik_keyboard,
    is_taktik_keyboard_active,
    type_with_taktik_keyboard,
)

from ..core.base_action import BaseAction
from ..core.utils import first_matching
from ...ui.selectors.surfaces.video import VIDEO_SELECTORS
from ...ui.selectors.surfaces.video.comments import COMMENT_SELECTORS


class CommentActions(BaseAction):
    """Open, read and write the comment sheet of the video on screen."""

    def __init__(self, device):
        super().__init__(device)
        self.comment_selectors = COMMENT_SELECTORS
        self.video_selectors = VIDEO_SELECTORS

    # ------------------------------------------------------------------
    # The gate
    # ------------------------------------------------------------------

    def is_comment_sheet_open(self) -> bool:
        """Is the comment sheet actually up?

        Anchored on the per-comment like button: measured 3 and 5 on the two versions' sheets and
        ZERO on every other captured screen. It is the only candidate that says no.
        """
        return bool(first_matching(self.device, self.comment_selectors.sheet_indicator))

    def _wait_for_sheet(self, timeout: float = 6.0) -> bool:
        """The sheet slides up over the video and takes a beat.

        Reading once right after the tap is indistinguishable from "the tap did nothing" — on
        43.1.4 the same sequence failed on the first read and passed three seconds later.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.is_comment_sheet_open():
                time.sleep(0.4)
                return True
            time.sleep(0.4)
        return False

    # ------------------------------------------------------------------
    # Open / close
    # ------------------------------------------------------------------

    def open_comments(self) -> bool:
        """Open the comment sheet of the video on screen, and prove it opened."""
        if self.is_comment_sheet_open():
            return True

        self.logger.debug("💬 Opening the comment sheet")
        if not self._find_and_click(self.video_selectors.comment_button, timeout=5):
            self.logger.warning("❌ Comment button not found — no sheet opened")
            return False

        if not self._wait_for_sheet():
            self.logger.warning("❌ The comment button was tapped but no sheet appeared")
            return False
        return True

    def close_comments(self) -> bool:
        """Close the sheet. A bare 'Close' fires on several surfaces, so this is only ever called
        while the sheet is the surface in front of us."""
        if not self.is_comment_sheet_open():
            return True
        if self._find_and_click(self.comment_selectors.close_button, timeout=3):
            time.sleep(0.8)
        else:
            self.device.press("back")
            time.sleep(0.8)
        return not self.is_comment_sheet_open()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read_comments(self, max_comments: int = 20) -> List[Dict[str, Any]]:
        """The comments visible on the sheet: author, text, likes.

        Returns [] when the sheet is not open — and logs why, so an empty list is never mistaken
        for "this video has no comments".
        """
        if not self.is_comment_sheet_open():
            self.logger.warning("read_comments: the comment sheet is not open — reading nothing")
            return []

        authors = self._texts(self.comment_selectors.comment_author)
        bodies = self._texts(self.comment_selectors.comment_text)
        likes = self._texts(self.comment_selectors.comment_like_count)

        # Paired by ORDER, not by index across independent lists: a comment with no like count
        # has no node at all, so zipping the three would attach one comment's likes to another.
        # Only author and body are paired, because they are the two fields every row carries.
        comments: List[Dict[str, Any]] = []
        for index, author in enumerate(authors[:max_comments]):
            comments.append({
                "author": author,
                "text": bodies[index] if index < len(bodies) else "",
                # Reported apart, never guessed: absent on 43.1.4 entirely, and absent on any
                # comment with no like.
                "like_count": likes[index] if index < len(likes) else None,
            })
        self.logger.debug(f"💬 Read {len(comments)} comment(s)")
        return comments

    def comment_count(self) -> Optional[int]:
        """The sheet's own total, e.g. "16 commentaires" — None when it cannot be read."""
        for text in self._texts(self.comment_selectors.comment_count_header):
            digits = "".join(ch for ch in text if ch.isdigit())
            if digits:
                return int(digits)
        return None

    def _texts(self, selectors) -> List[str]:
        found: List[str] = []
        for element in first_matching(self.device, selectors):
            text = (getattr(element, "text", "") or "").strip()
            if text:
                found.append(text)
        return found

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def post_comment(self, text: str) -> bool:
        """Type a comment and send it, confirming it actually left the composer.

        The send button carries an UNRESOLVED Android resource as its description on both
        versions, so it is anchored by position after the mention affordance — and it only exists
        once the field holds text. That is why the flow is: focus, type, THEN look for send. A
        version of this that looked for the button first would find the search button instead.
        """
        comment = (text or "").strip()
        if not comment:
            self.logger.warning("post_comment: refusing to post an empty comment")
            return False
        if not self.is_comment_sheet_open():
            self.logger.warning("post_comment: the comment sheet is not open")
            return False

        if not self._focus_and_type(comment):
            return False

        send = first_matching(self.device, self.comment_selectors.post_comment_button)
        if not send:
            self.logger.warning(
                "post_comment: no send button once the text was typed — leaving the draft alone")
            return False

        try:
            send[0].click()
        except Exception as e:
            self.logger.warning(f"post_comment: could not tap send: {e}")
            return False
        self._human_like_delay('click')

        # A comment is posted when the composer EMPTIES. Reporting the tap would record a comment
        # that is still sitting in the field — the exact failure `send_message` had.
        for _ in range(8):
            if not self._composer_holds(comment):
                self.logger.success("💬 Comment posted")
                return True
            time.sleep(0.5)

        self.logger.warning(
            "post_comment: send reported no error but the composer still holds the text — not posted")
        return False

    def reply_to_comment(self, author: str, text: str, *, to_text: Optional[str] = None) -> bool:
        """Reply under one comment.

        Tapping Reply is what scopes the composer to that thread; without it the text becomes a
        top-level comment, which is a different thing said to a different person.

        `to_text` disambiguates, and it matters: one person often leaves several comments under
        the same video, and an author name alone picks the first of them. Replying to the wrong
        comment of the right person is the same family of mistake as engaging the wrong person —
        measured while verifying this, where three comments shared one author.
        """
        if not self.is_comment_sheet_open():
            self.logger.warning("reply_to_comment: the comment sheet is not open")
            return False

        if not self._tap_reply_of(author, to_text):
            self.logger.warning(
                f"reply_to_comment: no Reply button found under @{author}"
                + (f" for {to_text!r}" if to_text else "")
            )
            return False

        time.sleep(1.0)
        return self.post_comment(text)

    def _tap_reply_of(self, author: str, to_text: Optional[str] = None) -> bool:
        """The Reply button of the row belonging to `author` (and, when given, to `to_text`)."""
        rows = first_matching(self.device, self.comment_selectors.comment_author)
        bodies = self._texts(self.comment_selectors.comment_text)
        replies = first_matching(self.device, self.comment_selectors.reply_button)
        if not rows or not replies:
            return False

        wanted_body = (to_text or "").strip()
        for index, element in enumerate(rows):
            name = (getattr(element, "text", "") or "").strip()
            if name != author:
                continue
            if wanted_body:
                body = bodies[index] if index < len(bodies) else ""
                if wanted_body not in body:
                    continue
            # Paired by order: one Reply per named row, in the same order. Falling back to the
            # first Reply would answer the wrong person, which is worse than not replying.
            if index >= len(replies):
                return False
            try:
                replies[index].click()
                return True
            except Exception as e:
                self.logger.debug(f"Could not tap Reply for @{author}: {e}")
                return False
        return False

    # ------------------------------------------------------------------
    # Composer plumbing
    # ------------------------------------------------------------------

    def _focus_and_type(self, text: str) -> bool:
        """Focus the field and type through the project's own IME.

        uiautomator2's `send_keys` dies on these phones (`InputManager.getInstance` is gone on
        recent Android), which is why the project ships Taktik Keyboard. Using u2 here would fail
        on the device and work in every test.
        """
        inputs = first_matching(self.device, self.comment_selectors.comment_input)
        if not inputs:
            self.logger.warning("The comment composer was not found")
            return False
        try:
            inputs[0].click()
        except Exception as e:
            self.logger.warning(f"Could not focus the comment composer: {e}")
            return False
        self._human_like_delay('click')

        serial = self._get_device_serial()
        if not is_taktik_keyboard_active(serial):
            activate_taktik_keyboard(serial)
            time.sleep(0.8)
        if not type_with_taktik_keyboard(serial, text):
            self.logger.warning("Typing the comment failed")
            return False
        time.sleep(0.8)
        return self._composer_holds(text)

    def _composer_holds(self, text: str) -> bool:
        """Is `text` still in the field? Used both to confirm typing and to confirm sending."""
        for element in first_matching(self.device, self.comment_selectors.comment_input):
            try:
                return (getattr(element, "text", "") or "").strip() == text.strip()
            except Exception:
                return False
        return False

    def discard_draft(self) -> bool:
        """Empty the composer without sending — what a probe or an aborted run must leave behind."""
        return bool(clear_text_with_taktik_keyboard(self._get_device_serial()))


__all__ = ["CommentActions"]
