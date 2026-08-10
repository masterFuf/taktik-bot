"""Selectors of the "Discover people" surface (account suggestions).

Provenance : dumps reels device, Instagram v410.0.0.53.71, 2026-07-26
(feed -> carousel netego "Suggested for you" -> "See all" -> modale contacts ->
"Discover people" list). See also `POPUP_SELECTORS.contacts_access_*` for the contacts
access modal that comes between the two screens.

Deux familles volontairement separees :

- XPATHS for direct device access (screen detection, tapping a button);
- BARE resource-ids for the fast-path parsing of the XML dump. A suggestion row is a
  subtree that ALREADY holds its username, its button and its social context, so there
  is no need to pair bounds by vertical proximity as on the notifications surface. Some
  rows are rendered with a bare resource-id, so the parsing matches by SUBSTRING.

The button state labels are NOT redefined here: they live in
`PROFILE_SELECTORS.follow_state_labels_*` and are read by `classify_follow_state()`,
the single source of truth shared with the profile header.
"""

from typing import List
from dataclasses import dataclass, field

from ..locales import L


@dataclass
class DiscoverPeopleSelectors:
    """The people-discovery screen: a list of suggested accounts, one button per row."""

    # === Screen title (language-dependent, locales overlay) ===
    _screen_title_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/action_bar_title"]',
    ])

    @property
    def screen_title(self) -> List[str]:
        return self._screen_title_base

    @property
    def screen_title_texts(self) -> List[str]:
        """Raw title labels (not xpaths) — surface confirmation."""
        return L("discover_people.screen_title_texts")

    # === Surface proof: at least one recommendation row rendered ===
    # NB (regle AGENTS "preuve de surface specifique") : `row_recommended_user_username`
    # On its own it is too broad, since it also appears in the suggestions tail of a
    # followers list. The proof used is the row CONTAINER plus its action button, which
    # only exist together on a recommendation list.
    suggestion_row: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "recommended_user_row_content_identifier")]',
    ])
    suggestion_follow_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "row_recommended_user_follow_button")]',
    ])

    # === Conteneur scrollable ===
    list_container: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/recycler_view"]',
        '//*[@resource-id="com.instagram.android:id/refreshable_container"]',
    ])

    # === Fast-path XML dump: BARE resource-ids (substring matches) ===
    row_container_id: str = "recommended_user_row_content_identifier"
    row_username_id: str = "row_recommended_user_username"
    row_follow_button_id: str = "row_recommended_user_follow_button"
    row_social_context_id: str = "row_recommended_social_context"
    row_dismiss_id: str = "row_recommended_hide_icon_button"
    section_header_id: str = "row_header_textview"
    section_header_action_id: str = "row_header_action"

    # Call-to-action rows at the top of the screen. They carry an action button but are
    # NOT suggestions, so they are never touched.
    connect_row_ids: tuple = ("facebook_button", "contacts_button")


DISCOVER_PEOPLE_SELECTORS = DiscoverPeopleSelectors()
