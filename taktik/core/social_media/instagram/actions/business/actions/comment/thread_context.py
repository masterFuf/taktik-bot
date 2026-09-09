"""Reading a post's comment thread just before writing under it.

WHY IT LIVES HERE — this is the only part of the feature that touches the device, and it needs
`_is_comments_view_open` / `_open_comments_view` / `_dismiss_share_sheet_if_open`, which are
`CommentAction`'s own. Putting it in `workflows/common/` would mean reaching into another
class's privates from a module that owns none of them. The selection rules, which are pure, do
live there (`workflows/common/comment_context.py`); this file is only the hand that opens the
sheet.

THE ORDER MATTERS, AND IT COSTS NOTHING — `comment_on_post` already opens the thread to reach
the composer, then waits 2-4 s before typing. Reading here does not ADD a navigation, it moves
the existing one a few seconds earlier: when we hand back with the composer already open,
`comment_on_post` skips its own click (the branch is already there, guarded by
`_is_comment_composer_open`). Net effect: ONE sheet transition per commented post instead of
two, so one tap fewer on `row_feed_button_comment` — and therefore half the exposure to the
documented mis-tap onto the neighbouring share button.

BEST EFFORT, ALWAYS — every failure returns the same thing an empty thread returns, and the run
continues exactly as it does today. A comment written without thread context is the current
behaviour, not a degraded one.
"""

from __future__ import annotations

import random
import time
from typing import Any, Dict, List, Optional

from loguru import logger

from taktik.core.social_media.instagram.workflows.common.comment_context import (
    ThreadSelection,
    select_thread_comments,
)
from taktik.core.social_media.instagram.workflows.common.comment_reading import (
    read_visible_comments,
)

# Two reads at most, and never a gesture between them: the thread loads asynchronously after the
# sheet opens, so a second look a beat later catches what the first missed. A THIRD read, or any
# scroll, would buy little and risk a lot — see the note on scrolling below.
SETTLE_MIN, SETTLE_MAX = 0.9, 1.6
SECOND_PASS_SLEEP = 1.2
SECOND_PASS_MIN_RECORDS = 4
DEFAULT_BUDGET_S = 12.0


class ThreadContextMixin:
    """Reads the open thread and hands the screen back in the state the caller expects."""

    def read_thread_context(
        self,
        *,
        post_author: str = "",
        own_handle: str = "",
        own_recent_texts: Optional[List[str]] = None,
        comment_lang: Optional[str] = None,
        base_lang: Optional[str] = None,
        budget_s: float = DEFAULT_BUDGET_S,
    ) -> ThreadSelection:
        """The thread's material, and the sheet left open on the composer when possible.

        NEVER raises. A caller checks `selection.has_material` and passes it along; there is no
        error path to handle because there is no outcome worse than "no context", which is what
        every run does today.
        """
        started = time.monotonic()
        status = "ok"
        try:
            if not self._ensure_thread_open():
                return self._empty("not_opened", started)

            # The mis-tap onto the neighbouring share button is the documented failure of this
            # surface. Caught HERE rather than later: left open, the sheet would sit there for
            # the whole 10-20 s of the model call, and `_click_comment_button` — a plain
            # hierarchical `.exists` with no visibility check — would then tap UNDER it.
            try:
                if self._dismiss_share_sheet_if_open():
                    return self._empty("share_sheet", started)
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"[thread-context] share-sheet check failed: {exc}")

            time.sleep(random.uniform(SETTLE_MIN, SETTLE_MAX))
            records = self._read_two_passes(started, budget_s)
            if not records:
                status = "empty"

            selection = select_thread_comments(
                records,
                own_handle=own_handle,
                own_recent_texts=own_recent_texts,
                post_author=post_author,
                comment_lang=comment_lang,
                base_lang=base_lang,
            )
            logger.info(
                f"[thread-context] {status} · seen={selection.seen} kept={selection.kept} "
                f"author={len(selection.author_replies)} praise={selection.praise_count} "
                f"dropped={selection.dropped} · {int((time.monotonic() - started) * 1000)} ms"
            )
            if selection.already_commented:
                logger.warning(
                    "[thread-context] this account already appears in this thread — "
                    "the post may have been commented before"
                )
            return selection
        except Exception as exc:  # noqa: BLE001 — context is a bonus, never a blocker
            logger.debug(f"[thread-context] aborted: {exc}")
            return self._empty("error", started)

    # ── device ──────────────────────────────────────────────────────────────────────────────
    def _ensure_thread_open(self) -> bool:
        """True when the comments view is on screen, opening it if needed."""
        try:
            if self._is_comments_view_open():
                return True
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"[thread-context] open-state check failed: {exc}")
        try:
            return bool(self._open_comments_view())
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"[thread-context] could not open the thread: {exc}")
            return False

    def _read_two_passes(self, started: float, budget_s: float) -> List[Dict[str, Any]]:
        """Read once, and once more only if the first look came back thin.

        No scrolling, ever. A scroll issued on a false positive of `_is_comments_view_open`
        would scroll the FEED — and the screenshot the vision model already read is frozen on
        disk since before this call, so the comment would be written about post X and published
        under post Y. That is the worst outcome this surface can produce, and it would be bought
        for the few extra comments below the fold, which are the least-seen ones anyway.
        """
        first_started = time.monotonic()
        records = self._read_once()
        first_took = time.monotonic() - first_started

        enough = len(records) >= SECOND_PASS_MIN_RECORDS
        spent = time.monotonic() - started
        if enough or spent > budget_s - 4.0 or first_took > 4.0:
            return records

        time.sleep(SECOND_PASS_SLEEP)
        second = self._read_once()
        if not second:
            return records

        merged = {self._key(r): r for r in records}
        for record in second:
            merged.setdefault(self._key(record), record)
        return list(merged.values())

    def _read_once(self) -> List[Dict[str, Any]]:
        try:
            return read_visible_comments(self.device) or []
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"[thread-context] read failed: {exc}")
            return []

    @staticmethod
    def _key(record: Dict[str, Any]) -> str:
        return f"{(record.get('username') or '').lower()}|{(record.get('text') or '')[:24]}"

    @staticmethod
    def _empty(status: str, started: float) -> ThreadSelection:
        logger.debug(
            f"[thread-context] {status} · {int((time.monotonic() - started) * 1000)} ms"
        )
        return ThreadSelection()


__all__ = ["ThreadContextMixin"]
