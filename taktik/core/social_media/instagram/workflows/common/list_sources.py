"""Where the profiles of a post come from, for the shared interaction loop.

`_interact_with_likers_list` (likers_base) always read its rows from the likers popup. But a
post surrounds itself with TWO populations, and engaging either is the same intention:

  * the people who LIKED it        → the likers bottom-sheet (a standard follow-list);
  * the people who COMMENTED on it → the comments thread, whose rows are shaped differently.

The scraping side already abstracts exactly this distinction (`workflows/scraping/list_strategy`
— "followers/following/likers (rows in a vertical list) and post commenters (button widgets in
a comments popup)"). This is its counterpart for the INTERACTION loop, so the loop keeps one
implementation and only its row source changes.

Every callable takes no argument. `get_visible` returns dicts carrying at least 'username' and
'element' — the same shape both sides already produce.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from taktik.core.social_media.instagram.workflows.common.detection import (
    is_comments_view_open,
    read_visible_commenters,
)


@dataclass
class InteractionListSource:
    """The list the interaction loop walks, and how to operate it."""

    #: Short name used in logs ("likers" / "commenters").
    label: str

    #: REQUIRED — visible rows, each at least {'username': str, 'element': Any | None}.
    get_visible: Callable[[], List[Dict[str, Any]]]

    #: REQUIRED — are we still on that list? (used to detect a wrong screen)
    is_open: Callable[[], bool]

    #: REQUIRED — reveal more rows.
    scroll: Callable[[], None]

    #: REQUIRED — open the row of `username` (the row's element is passed when known).
    click: Callable[[str, Any], bool]

    #: REQUIRED — come back to the list after visiting a profile.
    ensure_open: Callable[..., bool]

    #: Optional — the row's follow-button state, read WITHOUT opening the profile. Rows that
    #: carry no such button return 'unknown', which the loop already treats as fail-open.
    row_follow_state: Callable[[str], str] = field(default=lambda _username: 'unknown')

    #: Optional — leave a screen that is not the expected list at all.
    exit_wrong_screen: Callable[[], None] = field(default=lambda: None)


def make_likers_source(workflow) -> InteractionListSource:
    """The historical source: the likers bottom-sheet, a standard follow-list.

    Every member is resolved at CALL time, not here: the loop only reads a row's follow state
    when a relationship filter is on, so a detector that lacks that optional method must not
    break a run that never asks for it.
    """
    return InteractionListSource(
        label="likers",
        get_visible=lambda: workflow.detection_actions.get_visible_followers_with_elements(),
        is_open=lambda: workflow._is_likers_popup_open(),
        scroll=lambda: workflow._scroll_likers_popup_up(),
        click=lambda username, _element: workflow.detection_actions.click_follower_in_list(username),
        ensure_open=lambda force_back=False: workflow._ensure_on_likers_popup(force_back=force_back),
        row_follow_state=lambda username: workflow.detection_actions.get_row_follow_state(username),
        exit_wrong_screen=lambda: workflow._exit_wrong_likers_screen(),
    )


def make_commenters_source(workflow) -> InteractionListSource:
    """The comments thread: commenters are the people who took the time to WRITE something.

    A commenter's username is an `android.widget.Button` whose @content-desc is empty; the
    action buttons around it (Reply / Like / See translation) carry a non-empty one. Clicking
    the username opens that person's profile — from there the loop is identical to likers.

    Row-level follow state is deliberately left unknown: a comment row has no follow button,
    so the relationship check falls back to the profile-level guard, which is the source of
    truth anyway.
    """
    device = workflow.device
    logger = workflow.logger
    scr = workflow.scroll_actions

    def _get_visible() -> List[Dict[str, Any]]:
        return read_visible_commenters(device, logger)

    def _is_open() -> bool:
        try:
            return is_comments_view_open(device, logger)
        except Exception:
            return False

    def _scroll() -> None:
        scr.scroll_down()
        # The comments sheet re-renders its buttons and their bounds move; give it a beat
        # before the next dump (same settle the scraping strategy applies).
        time.sleep(0.3)

    def _click(username: str, element: Any) -> bool:
        # Click the element we already located: unlike a follow-list row, a commenter has no
        # stable by-username selector to re-find it with.
        try:
            if element is not None:
                element.click()
                return True
        except Exception as exc:
            logger.debug(f"[commenters] click on @{username} failed: {exc}")
        return False

    def _ensure_open(force_back: bool = False) -> bool:
        """Back out of the profile until the comments thread is showing again."""
        for _ in range(3):
            if _is_open():
                return True
            try:
                device.press("back")
            except Exception:
                return False
            time.sleep(1.0)
        return _is_open()

    return InteractionListSource(
        label="commenters",
        get_visible=_get_visible,
        is_open=_is_open,
        scroll=_scroll,
        click=_click,
        ensure_open=_ensure_open,
    )


def resolve_list_source(workflow, mode: Optional[str]) -> InteractionListSource:
    """Pick the source for a run. Unknown/absent mode keeps the historical likers behaviour."""
    return make_commenters_source(workflow) if str(mode or '').lower() == 'commenters' \
        else make_likers_source(workflow)


__all__ = [
    "InteractionListSource",
    "make_likers_source",
    "make_commenters_source",
    "resolve_list_source",
]
