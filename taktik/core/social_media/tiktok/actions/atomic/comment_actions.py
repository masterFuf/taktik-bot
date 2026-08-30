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

from taktik.core.shared.text import as_xml_dumped
from taktik.core.shared.input.taktik_keyboard import (
    activate_taktik_keyboard,
    clear_text_with_taktik_keyboard,
    is_taktik_keyboard_active,
    type_with_taktik_keyboard,
)

from ..core.base_action import BaseAction
from ..core.utils import first_matching

from ...services.profile.username import read_open_profile_handle
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
        """The comments visible on the sheet: author, text, likes — each read INSIDE its own row.

        Returns [] when the sheet is not open — and logs why, so an empty list is never mistaken
        for "this video has no comments".

        Read row by row rather than by pairing flat lists. The earlier version collected authors,
        bodies and likes as three independent lists and joined them by index; since a text read
        drops empty nodes, one comment without a body node shifted every pairing after it and
        filed one person's words under the next person down. Measured on 46.6.3, that is not
        hypothetical: an emoji-only comment reads as empty once the dump has eaten the emoji.
        """
        if not self.is_comment_sheet_open():
            self.logger.warning("read_comments: the comment sheet is not open — reading nothing")
            return []

        comments = [row for _, row in self._visible_rows(limit=max_comments)]
        self.logger.debug(f"💬 Read {len(comments)} comment(s)")
        return comments

    def _visible_rows(self, limit: int = 50) -> List[tuple]:
        """(index, fields) for each comment row on screen, fields read within that row.

        The index is the row's position among the author nodes, and it is what a caller taps: the
        display names repeat — two commenters rendered as `.` on one sheet — so picking a row by
        its name opens the first of them over and over.
        """
        author_selector = self._author_selector()
        if not author_selector:
            return []

        try:
            count = len(self.device.xpath(author_selector).all())
        except Exception:
            return []

        rows: List[tuple] = []
        for index in range(min(count, limit)):
            fields = self._row_fields(author_selector, index)
            if fields:
                rows.append((index, fields))
        return rows

    def _author_selector(self) -> str:
        """The first author selector that resolves on this screen, or "".

        A selector list is an ordered set of alternatives -- the package name differs between the
        musically and trill builds -- so the one that matched has to be carried forward, not
        re-guessed: a positional xpath built on a selector that finds nothing addresses no row.
        """
        for selector in self.comment_selectors.comment_author:
            try:
                if self.device.xpath(selector).all():
                    return selector
            except Exception:
                continue
        return ""

    def _row_fields(self, author_selector: str, index: int) -> Optional[Dict[str, Any]]:
        """Author, body and like count of the row at `index`, each read from that row's subtree.

        Every xpath comes from the catalogue, scoped to one row. Reading three flat lists and
        joining them by index -- what this replaced -- attributed one person's words to the next
        person down as soon as a single row rendered no body node, which an emoji-only comment
        does the moment the dump has eaten the emoji.
        """
        selectors = self.comment_selectors
        author = self._first_text(selectors.author_at(author_selector, index))
        if not author:
            return None

        return {
            "author": author,
            "text": self._first_text(selectors.body_at(author_selector, index)),
            # None, never 0: absent means no likes or an old build, never "the sheet is shut".
            "like_count": self._first_text(selectors.like_count_at(author_selector, index)) or None,
        }

    def _first_text(self, selectors) -> str:
        """The text of the first node any of these selectors resolves to, or ""."""
        for element in first_matching(self.device, selectors):
            text = (getattr(element, "text", "") or "").strip()
            if text:
                return text
        return ""

    def read_commenter_handles(
        self,
        max_commenters: int = 20,
        *,
        max_scrolls: int = 8,
    ) -> List[Dict[str, Any]]:
        """The people who commented, by their HANDLE -- opening each profile to read it.

        Why the detour, measured on 46.6.3 on 2026-08-30. A comment row carries four nodes and
        not one of them is a username: `:id/title` holds the DISPLAY NAME, `:id/f1j` the body,
        `:id/el6` the date, `:id/ejy` the reply link. Eight real rows from one post gave seven
        display names no search would ever resolve:

            'secretdrxx'   -> @secretdrxx        (the only one that would have worked by luck)
            'Lau'          -> @laurie_bouchardd
            '.'            -> @polo12079         (an emoji-only name, eaten by the dump)
            'Benjamin ..'  -> @benjzmzn

        A scrape that files people under those names produces rows no later workflow can match --
        the same failure the welcome pass hit on the new-followers page, which renders display
        names for the same reason.

        Tapping the name opens the profile and `back` returns to the sheet at its scroll position;
        both measured three times running. Rows are walked BY INDEX within a screenful, never by
        name: display names repeat, and picking by name opens the first of them over and over.

        Costs about 13 seconds per commenter, nearly all of it the profile round trip. That is the
        price of a usable handle, and it is why `max_commenters` exists.
        """
        if not self.is_comment_sheet_open() and not self.open_comments():
            self.logger.warning("read_commenter_handles: no comment sheet to read")
            return []

        collected: Dict[str, Dict[str, Any]] = {}
        for _ in range(max_scrolls):
            rows = self._visible_rows()
            if not rows:
                self.logger.debug("read_commenter_handles: no author row on this screenful")
                break

            found_here = 0
            for index in range(len(rows)):
                if len(collected) >= max_commenters:
                    break
                record = self._open_commenter_at(index)
                if record and record["username"] not in collected:
                    collected[record["username"]] = record
                    found_here += 1
                    self.logger.info(
                        "\U0001f4ac {0!r} -> @{1}".format(record["display_name"], record["username"])
                    )

            if len(collected) >= max_commenters:
                break

            # Stop on "this pass brought nobody new", not on "the names look the same as before".
            # Comparing display names was the obvious check and it is unreliable for the very
            # reason this method exists: they repeat. Two rows rendering `..` after a scroll that
            # DID move would read as a sheet that had not moved, and the walk would end early with
            # no sign of it -- which is what an unexplained 4-out-of-8 run looked like.
            if not found_here:
                self.logger.debug(
                    "read_commenter_handles: a full pass brought nobody new -- end of list"
                )
                break
            self._scroll_comment_sheet()

        self.logger.info(f"\U0001f4ac {len(collected)} commenter(s) identified")
        return list(collected.values())

    def _open_commenter_at(self, index: int) -> Optional[Dict[str, Any]]:
        """Open the profile of the comment row at `index`, read the handle, come back.

        Returns None whenever the round trip failed, INCLUDING failing to get back to the sheet:
        a caller that kept walking indices on the wrong screen would tap whatever sits there.
        """
        author_selector = self._author_selector()
        if not author_selector:
            return None
        fields = self._row_fields(author_selector, index)
        if not fields:
            return None

        rows = first_matching(self.device, self.comment_selectors.comment_author)
        if index >= len(rows):
            return None
        display_name = fields["author"]

        try:
            rows[index].click()
        except Exception as exc:
            self.logger.debug(f"read_commenter_handles: row {index} not tappable ({exc})")
            return None
        self._human_like_delay('navigation')

        handle = read_open_profile_handle(self.device, label=display_name, timeout=6)
        self.device.press("back")
        time.sleep(1.2)

        if not self.is_comment_sheet_open():
            self.logger.warning(
                "read_commenter_handles: back did not return to the comment sheet -- stopping"
            )
            return None
        if not handle:
            self.logger.debug(f"read_commenter_handles: no profile opened for {display_name!r}")
            return None

        return {"username": handle, "display_name": display_name, "text": fields["text"]}

    def _scroll_comment_sheet(self) -> None:
        """One scroll inside the sheet, through the humanized primitive every other list uses.

        A short scale because a comment sheet is a third of the screen -- a full-height swipe
        skips rows, and a skipped row is a commenter this never sees.
        """
        self._scroll_down(scale=0.4)
        time.sleep(0.8)

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
        """The Reply button of the row belonging to `author` (and, when given, to `to_text`).

        The body is read from the candidate's OWN row. It used to come from a flat list of every
        body on the sheet, joined to the rows by index -- and since that list drops rows whose
        body node is absent, `to_text` was matched against a neighbour's words. `to_text` exists
        precisely because one person leaves several comments, so getting it wrong sends the reply
        to the wrong comment, which is the failure it was added to prevent.
        """
        rows = first_matching(self.device, self.comment_selectors.comment_author)
        replies = first_matching(self.device, self.comment_selectors.reply_button)
        anchor = self._author_selector()
        if not rows or not replies or not anchor:
            return False

        wanted_body = (to_text or "").strip()
        for index, element in enumerate(rows):
            name = (getattr(element, "text", "") or "").strip()
            if name != author:
                continue
            if wanted_body:
                body = self._first_text(self.comment_selectors.body_at(anchor, index))
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
        """Is `text` still in the field? Used both to confirm typing and to confirm sending.

        Compared through the DUMP PROJECTION, not raw. The field is read from an XML dump, and
        AOSP's sanitiser replaces every astral character with two dots — so an emoji makes a raw
        equality impossible. Measured on device 2026-08-30: `Bien vu 😂 vraiment` typed, `Bien vu
        .. vraiment` read back.

        Both directions were broken by that, and in opposite ways. Confirming the TYPING, the
        equality never held, so `_focus_and_type` returned False on a comment it had just typed
        correctly — silently, since that path logs nothing — and every AI-written comment (they
        almost always carry an emoji) was abandoned as a draft while the run reported zero
        comments. Confirming the SEND, the same mismatch reads as "the composer emptied", so a
        comment still sitting in the field would have been recorded as posted.
        """
        expected = as_xml_dumped(text).strip()
        for element in first_matching(self.device, self.comment_selectors.comment_input):
            try:
                return as_xml_dumped(getattr(element, "text", "") or "").strip() == expected
            except Exception:
                return False
        return False

    def discard_draft(self) -> bool:
        """Empty the composer without sending — what a probe or an aborted run must leave behind."""
        return bool(clear_text_with_taktik_keyboard(self._get_device_serial()))


__all__ = ["CommentActions"]
