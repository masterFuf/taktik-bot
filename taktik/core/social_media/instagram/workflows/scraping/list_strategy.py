"""Strategy pattern for `_scrape_list` — abstracts over the type of list being scraped.

The same scraping loop (dedup → click → enrich → AI → back → save → scroll) is shared
between followers/following/likers (rows in a vertical list) and post commenters
(button widgets in a comments popup). The only differences are:

  * how to enumerate currently visible profile rows
  * which detector confirms we're on the right list (used for back-retry recovery)
  * how to scroll the list down
  * a few optional end-of-list hints (Instagram suggestions, "And X others" footer…)

`ListScrapingStrategy` captures these as callables, and the factories below produce
the two concrete strategies used today.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

from ..common.detection import is_likers_popup_open, is_comments_view_open


# Action-button labels that pass the username regex but are NOT usernames.
# Used to filter commenter button candidates.
_COMMENTER_ACTION_TEXTS = frozenset({
    'Reply', 'Hide', 'Like', 'Follow', 'Following', 'Remove',
    'Post', 'Translate', 'Report', 'Signaler', 'Retirer',
    'Répondre', 'Masquer', 'Suivre', 'Publier',
})
_COMMENTER_USERNAME_RE = re.compile(r'^[a-zA-Z0-9._]{1,30}$')


@dataclass
class ListScrapingStrategy:
    """Strategy object injected into `_scrape_list`.

    Each callable is invoked with no arguments and returns the documented type.
    Defaults are safe no-ops so a strategy only needs to implement what's relevant.
    """

    # REQUIRED — enumerate visible profiles. Each dict must contain at least
    # 'username' (str) and 'element' (clickable XMLElement, may be None).
    get_visible: Callable[[], List[Dict[str, Any]]]

    # REQUIRED — predicate used after navigating away from a profile to verify
    # we successfully returned to the list (back-retry loop).
    is_on_list: Callable[[], bool]

    # REQUIRED — scroll the list down by one viewport-ish.
    scroll_down: Callable[[], None]

    # Optional — "Load more" / "See more" button click. Returns True if clicked.
    check_load_more: Callable[[], bool] = field(default=lambda: False)

    # Optional — end-of-list footer ("And X others" for likers/followers).
    is_end_reached: Callable[[], bool] = field(default=lambda: False)

    # Optional — generic loading spinner check (between scrolls).
    is_loading: Callable[[], bool] = field(default=lambda: False)

    # Optional — Instagram's "Suggested for you" section that follows real
    # followers/likers (signals end of organic list).
    is_in_suggestions: Callable[[], bool] = field(default=lambda: False)
    is_suggestions_visible: Callable[[], bool] = field(default=lambda: False)

    # When False, the scraper skips the suggestions-section heuristics entirely
    # (commenters popup has no such section).
    enable_suggestions_check: bool = True


# ──────────────────────────────────────────────────────────────────────────────
# Followers / Following / Likers strategy
# ──────────────────────────────────────────────────────────────────────────────

def make_followers_strategy(workflow) -> ListScrapingStrategy:
    """Default strategy: followers, following, and post likers all live in a
    standard followers-style list with the same detectors and scrolls.
    """
    det = workflow.detection_actions
    scr = workflow.scroll_actions

    def _is_on_list() -> bool:
        # Accept EITHER a followers list OR a likers popup (post likers reopen
        # into the same kind of bottom sheet).
        try:
            if det.is_followers_list_open():
                return True
        except Exception:
            pass
        try:
            return is_likers_popup_open(workflow.device, workflow.logger)
        except Exception:
            return False

    return ListScrapingStrategy(
        get_visible=det.get_visible_followers_with_elements,
        is_on_list=_is_on_list,
        scroll_down=scr.scroll_followers_list_down,
        check_load_more=scr.check_and_click_load_more,
        is_end_reached=det.is_followers_list_end_reached,
        is_loading=det.is_loading_spinner_visible,
        is_in_suggestions=det.is_in_suggestions_section,
        is_suggestions_visible=det.is_suggestions_section_visible,
        enable_suggestions_check=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Commenters strategy (Instagram comments popup)
# ──────────────────────────────────────────────────────────────────────────────

def make_commenters_strategy(workflow) -> ListScrapingStrategy:
    """Commenters live in the comments bottom-sheet popup. Each commenter's
    username is rendered as an `android.widget.Button` whose @content-desc is
    empty (action buttons like Reply / Like / See translation have non-empty
    @content-desc). Clicking the button navigates to the commenter's profile.
    """
    device = workflow.device
    logger = workflow.logger
    scr = workflow.scroll_actions

    def _get_visible() -> List[Dict[str, Any]]:
        try:
            buttons = device.xpath('//android.widget.Button').all()
        except Exception as e:
            logger.debug(f"[commenters] xpath dump failed: {e}")
            return []

        out: List[Dict[str, Any]] = []
        for elem in buttons:
            try:
                text = (elem.text or '').strip().lstrip('@')
                cd = elem.attrib.get('content-desc', None)
                # Discriminator:
                #   username buttons → content-desc == '' (empty string)
                #   action buttons   → content-desc equals visible label
                if cd != '':
                    continue
                if not text or not _COMMENTER_USERNAME_RE.match(text):
                    continue
                if text in _COMMENTER_ACTION_TEXTS:
                    continue
                out.append({'username': text, 'element': elem})
            except Exception:
                continue
        return out

    def _is_on_list() -> bool:
        try:
            return is_comments_view_open(device, logger)
        except Exception:
            return False

    def _scroll_down() -> None:
        scr.scroll_down()
        # Small extra settle delay: the comments popup re-renders buttons
        # whose bounds change frequently.
        time.sleep(0.3)

    return ListScrapingStrategy(
        get_visible=_get_visible,
        is_on_list=_is_on_list,
        scroll_down=_scroll_down,
        # No "load more", no "And X others", no suggestions section in comments.
        enable_suggestions_check=False,
    )
