"""Sélecteurs UI pour la recherche et découverte TikTok."""

from typing import List
from dataclasses import dataclass, field

from ..locales import L


@dataclass
class SearchSelectors:
    """Sélecteurs pour la recherche et découverte TikTok.
    
    Basé sur UI dumps:
    - ui_dump_20260111_121059.xml (For You page with search icon)
    - ui_dump_20260111_121110.xml (Search input page)
    - ui_dump_20260111_121127.xml (Search results page)
    
    Resource-IDs identifiés:
    - giv: Search input field (EditText)
    - y61: Search button (to submit search)
    - b9c: Back button (in search page)
    - c87: Clear search field button
    - ksc: Search icon in input field
    - spd: More button (3 dots)
    """
    
    # === Search icon on For You page (header) — langue-dependant (overlay locales/) ===
    @property
    def search_icon(self) -> List[str]:
        return L("search.search_icon")

    # === Search input field — base neutre (resource-id) + overlay locales/ ===
    _search_input_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/giv")]',
        '//android.widget.EditText[contains(@resource-id, ":id/giv")]',
    ])

    @property
    def search_input(self) -> List[str]:
        return self._search_input_base + L("search.search_input")

    # === Search submit button — base neutre (resource-id) + overlay locales/ ===
    _search_submit_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/y61")]',
    ])

    @property
    def search_submit_button(self) -> List[str]:
        return self._search_submit_button_base + L("search.search_submit_button")

    # === Back button in search page ===
    search_back_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/b9c")]',
        '//android.widget.ImageView[contains(@resource-id, ":id/b9c")]',
    ])
    
    # === Clear search field button ===
    clear_search_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/c87")]',
        '//android.widget.ImageView[@content-desc="Clear search field"]',
    ])
    
    # === More button (3 dots) ===
    more_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/spd")]',
        '//android.widget.ImageView[@content-desc="More"]',
    ])
    
    # Legacy selectors for compatibility — base neutre (resource-id) + overlay locales/
    _search_bar_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/giv")]',
    ])

    @property
    def search_bar(self) -> List[str]:
        return self._search_bar_base + L("search.search_bar")

    _search_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/y61")]',
    ])

    @property
    def search_button(self) -> List[str]:
        return self._search_button_base + L("search.search_button")

    # === Filtres de recherche (tabs on results page) ===
    top_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Top"]',
    ])
    
    users_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Users"]',
        '//android.widget.TextView[@text="Utilisateurs"]',
    ])
    
    @property
    def videos_tab(self) -> List[str]:
        return L("search.videos_tab")

    photos_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Photos"]',
    ])

    _shop_tab_base: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Boutique"]',
    ])

    @property
    def shop_tab(self) -> List[str]:
        return self._shop_tab_base + L("search.shop_tab")

    @property
    def sounds_tab(self) -> List[str]:
        return L("search.sounds_tab")

    hashtags_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Hashtags"]',
    ])
    
    # === Search suggestions (trending) ===
    suggestion_item: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Trending")]',
        '//android.widget.TextView[contains(@text, "Trending")]',
    ])
    
    # === Search results ===
    # User result item container
    user_result_container: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/sh2")]',
        '//android.widget.RelativeLayout[contains(@resource-id, ":id/sh2")]',
    ])
    
    # Username in search results
    user_result_username: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ye2")]',
        '//android.widget.TextView[contains(@resource-id, ":id/ye2")]',
    ])
    
    # User bio in search results
    user_result_bio: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/x8i")]',
    ])
    
    # User followers count in search results
    user_result_followers: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/xf0")]',
    ])
    
    # Follow button in search results — base neutre (resource-id) + overlay locales/
    _user_result_follow_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/rdh")]',
    ])

    @property
    def user_result_follow_button(self) -> List[str]:
        return self._user_result_follow_button_base + L("search.user_result_follow_button")

    # Video thumbnail in search results
    video_thumbnail: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/cover")]',
        '//android.widget.ImageView[contains(@resource-id, ":id/cover")]',
    ])
    
    # Video container in search results (clickable)
    video_result_container: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/sq1")]',
        '//android.widget.FrameLayout[contains(@resource-id, ":id/sq1")]',
    ])
    
    # View all button — langue-dependant (overlay locales/)
    @property
    def view_all_button(self) -> List[str]:
        return L("search.view_all_button")

    # First search result (generic fallback)
    first_search_result: List[str] = field(default_factory=lambda: [
        '(//androidx.recyclerview.widget.RecyclerView//android.view.ViewGroup)[1]',
    ])

    def user_result_selectors_for_username(self, username: str) -> List[str]:
        """Build user-result selectors for an exact or partial username match."""
        return [
            f'//android.widget.TextView[@text="@{username}"]',
            f'//android.widget.TextView[contains(@text, "{username}")]',
            *self.first_search_result,
        ]


SEARCH_SELECTORS = SearchSelectors()
