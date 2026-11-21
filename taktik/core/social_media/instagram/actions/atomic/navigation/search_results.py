"""What a profile search shows, read on one screen photo, and why a profile was not opened.

A slow search and an empty one used to give the same answer: the account row was looked for for
5 s, and its absence was taken for "this account is not listed". The captures of 2026-11-20
(Pixel 6a, Instagram 447, network throttled) tell the three screens apart on one tree:
- still loading: grey rows, no row of the query, no account row;
- answered, account absent: the row of the query alone;
- answered, account listed: the row of the query, then the account rows.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from taktik.core.contract.shared import PROFILE_NAVIGATION_FAILED, PROFILE_NOT_FOUND, PROFILE_SEARCH_SLOW
from taktik.core.social_media.instagram.ui.selectors.shell.navigation import NAVIGATION_SELECTORS


class SearchResultsState(str, Enum):
    """What the results list of a typed handle shows."""

    LOADING = "loading"
    LISTED = "listed"
    NOT_LISTED = "not_listed"
    UNRECOGNIZED = "unrecognized"


def read_search_results(photo, handle: str) -> SearchResultsState:
    """The state of the results of `handle` on `photo` (a `ScreenSnapshot`), without any gesture.

    Listed first: a row of the handle is a row to open, whatever is still loading under it. Then
    loading, before the query row: an answer is only read once nothing is loading any more. A
    screen showing neither is not a list without the account: it is a screen not recognized.
    """
    selectors = NAVIGATION_SELECTORS
    if photo.exists(selectors.search_result_selectors_for_username(handle)
                    + selectors.search_keyword_row_selectors_for_username(handle)):
        return SearchResultsState.LISTED
    if photo.exists(selectors.search_results_loading_rows):
        return SearchResultsState.LOADING
    if photo.exists(selectors.search_query_row_selectors_for_username(handle)):
        return SearchResultsState.NOT_LISTED
    return SearchResultsState.UNRECOGNIZED


class ProfileNavigationFailureReason(str, Enum):
    """Why `navigate_to_profile` opened no profile. The values are the codes the app reads."""

    NOT_A_HANDLE = "not_a_handle"
    SEARCH_UNREACHABLE = "search_unreachable"
    QUERY_NOT_TYPED = "query_not_typed"
    #: The results were answered and list no row of the handle (and its deep link, when tried,
    #: showed no profile): the account is not found.
    NOT_LISTED = "not_listed"
    #: The results were still loading when the wait ended: nothing is known of the account (the
    #: contract's own word for it).
    SEARCH_SLOW = PROFILE_SEARCH_SLOW
    RESULTS_UNRECOGNIZED = "results_unrecognized"
    ROW_NOT_TAPPED = "row_not_tapped"
    #: The row of the handle was tapped twice and the screen stayed the results list.
    TAP_NO_EFFECT = "tap_no_effect"
    PROFILE_WITHOUT_HANDLE = "profile_without_handle"
    OTHER_PROFILE = "other_profile"
    DEEP_LINK_FAILED = "deep_link_failed"
    PAGE_LEFT_OPEN = "page_left_open"


@dataclass(frozen=True)
class ProfileNavigationFailure:
    """The last failure of `navigate_to_profile`: by which route (`search`, `deep_link`, or
    `handle` before any gesture) and why."""

    route: str
    reason: ProfileNavigationFailureReason

    @property
    def account_not_found(self) -> bool:
        """The account is not found: the answered search lists it nowhere."""
        return self.reason is ProfileNavigationFailureReason.NOT_LISTED

    @property
    def search_slow(self) -> bool:
        """The search did not answer in time: the account may well exist."""
        return self.reason is ProfileNavigationFailureReason.SEARCH_SLOW

    @property
    def unopened_code(self) -> str:
        """The code a profile not opened is told to the app with, one of the contract's
        (`ProfileNotOpenedCode`): `not_found`, `search_slow`, else `navigation_failed`."""
        if self.account_not_found:
            return PROFILE_NOT_FOUND
        if self.search_slow:
            return PROFILE_SEARCH_SLOW
        return PROFILE_NAVIGATION_FAILED


def settle_profile_navigation_failure(
    search: Optional[ProfileNavigationFailure],
    deep_link: Optional[ProfileNavigationFailure],
) -> Optional[ProfileNavigationFailure]:
    """The failure a navigation reports when both routes were tried. A deep link that showed no
    profile adds nothing to what the search said (the page of an absent account is empty, as is a
    page still loading): the search's failure is kept. Anything else the deep link met is the news.
    """
    if deep_link is None:
        return search
    if search is not None and deep_link.reason is ProfileNavigationFailureReason.PROFILE_WITHOUT_HANDLE:
        return search
    return deep_link


__all__ = [
    "ProfileNavigationFailure",
    "ProfileNavigationFailureReason",
    "SearchResultsState",
    "read_search_results",
    "settle_profile_navigation_failure",
]
