from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from ..locales import L

@dataclass
class NavigationSelectors:
    """Sélecteurs pour la navigation et les boutons système."""

    # === Navigation principale (listes pour fallbacks) ===
    # Use resource-id selectors first to avoid clicking Android system buttons
    _home_tab_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "com.instagram.android:id/feed_tab")]',
    ])

    @property
    def home_tab(self) -> List[str]:
        return self._home_tab_base + L("navigation.home_tab")
    home_tab_resource_id: str = "com.instagram.android:id/feed_tab"

    @property
    def home_tab_descriptions(self) -> List[str]:
        return L("navigation.home_tab_descriptions")

    @property
    def home_tab_description_contains(self) -> List[str]:
        return L("navigation.home_tab_description_contains")

    _search_tab_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "com.instagram.android:id/search_tab")]',
    ])

    @property
    def search_tab(self) -> List[str]:
        return self._search_tab_base + L("navigation.search_tab")
    search_tab_resource_id: str = "com.instagram.android:id/search_tab"

    @property
    def search_tab_descriptions(self) -> List[str]:
        return L("navigation.search_tab_descriptions")

    @property
    def search_tab_description_contains(self) -> List[str]:
        return L("navigation.search_tab_description_contains")

    reels_tab: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Reels")]',
        '//*[contains(@content-desc, "Shorts")]'
    ])

    @property
    def activity_tab(self) -> List[str]:
        return L("navigation.activity_tab")

    _profile_tab_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "profile_tab")]',
        '//*[contains(@resource-id, "tab_profile")]',
        '//*[contains(@resource-id, "tab_bar_profile")]',
        '(//android.widget.FrameLayout[contains(@resource-id, "tab_")])[last()]',
        '//*[contains(@resource-id, "tab") and position()=5]',
    ])

    @property
    def profile_tab(self) -> List[str]:
        return self._profile_tab_base + L("navigation.profile_tab")

    # === Boutons système (listes pour fallbacks) ===
    @property
    def back_button(self) -> List[str]:
        return L("navigation.back_button")

    @property
    def close_button(self) -> List[str]:
        return L("navigation.close_button")

    # === Boutons de retour Instagram (complet, FR+EN) ===
    _back_buttons_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/action_bar_button_back"]',
    ])

    @property
    def back_buttons(self) -> List[str]:
        return self._back_buttons_base + L("navigation.back_buttons")
    action_bar_back_button_resource_id: str = "com.instagram.android:id/action_bar_button_back"

    # === Boutons de retour pour la liste followers/following ===
    back_buttons_action_bar: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/left_action_bar_buttons"]//android.widget.ImageView[@clickable="true"]',
        '//*[@resource-id="com.instagram.android:id/left_action_bar_buttons"]/android.widget.ImageView',
        '//*[@resource-id="com.instagram.android:id/action_bar_button_back"]',
    ])

    # === Onglets de profil ===
    _posts_tab_options_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_tab_layout"]//android.widget.ImageView[1]',
    ])

    @property
    def posts_tab_options(self) -> List[str]:
        return self._posts_tab_options_base + L("navigation.posts_tab_options")

    # === Hashtag navigation ===
    @property
    def recent_tab_selectors(self) -> List[str]:
        return L("navigation.recent_tab_selectors")

    @property
    def top_tab_selectors(self) -> List[str]:
        return L("navigation.top_tab_selectors")

    # === Search bar on explore page ===
    _explore_search_bar_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/action_bar_search_edit_text"]',
    ])

    @property
    def explore_search_bar(self) -> List[str]:
        return self._explore_search_bar_base + L("navigation.explore_search_bar")
    explore_search_bar_resource_id: str = "com.instagram.android:id/action_bar_search_edit_text"

    @property
    def explore_search_bar_texts(self) -> List[str]:
        return L("navigation.explore_search_bar_texts")
    edit_text_class_name: str = "android.widget.EditText"
    search_accounts_tab_texts: List[str] = field(default_factory=lambda: ["Accounts"])

    # === Search result selectors (use .format(username=...) for dynamic parts) ===
    search_result_container_resource_id: str = 'com.instagram.android:id/row_search_user_container'
    search_result_username_resource_id: str = 'com.instagram.android:id/row_search_user_username'

    def search_result_selectors_for_username(self, username: str) -> List[str]:
        """Build selectors for a search result row matching an exact username."""
        container_id = self.search_result_container_resource_id
        username_id = self.search_result_username_resource_id
        return [
            f'//*[contains(@resource-id, "{container_id}")][.//*[contains(@resource-id, "{username_id}") and @text="{username}"]]',
            f'//*[contains(@resource-id, "{container_id}")][.//*[@text="{username}"]]',
            f'//android.widget.TextView[contains(@resource-id, "{username_id}") and @text="{username}"]',
            f'//*[@clickable="true"][.//*[contains(@resource-id, "{username_id}") and @text="{username}"]]',
        ]

    def hashtag_result_selectors(self, hashtag: str) -> List[str]:
        """Build selectors for a hashtag result entry."""
        hashtag_text = f"#{hashtag}"
        return [
            f'//android.widget.TextView[@text="{hashtag_text}"]',
            f'//*[contains(@text, "{hashtag_text}")]',
            f'//*[contains(@content-desc, "{hashtag_text}")]',
            '//android.widget.TextView[contains(@text, "publications")]/../..',
            '//android.widget.TextView[contains(@text, "posts")]/../..',
        ]

    def hashtag_text_contains(self, hashtag: str) -> str:
        """Build the confirmation selector for a loaded hashtag page."""
        return f'//*[contains(@text, "#{hashtag}")]'

@dataclass
class ButtonSelectors:
    """Sélecteurs pour les boutons d'interaction courants."""

    # === Boutons d'interaction posts (listes pour fallbacks) ===
    _like_button_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like"]',
        # Reel / clips player like button (dump 9CHAY1PNRW IG 410, 2026-06-11):
        # ImageView resource-id "like_button", content-desc "J'aime" with a CURLY
        # apostrophe (U+2019), which the straight-apostrophe content-desc selector above
        # misses. The feed id row_feed_button_like is absent in the clips UI, so without
        # this a Reel opened from a profile grid could never be liked (0/2 matched).
        # resource-id is language-agnostic (survives the FR/EN selector optimization).
        '//*[@resource-id="com.instagram.android:id/like_button"]',
    ])

    @property
    def like_button(self) -> List[str]:
        return self._like_button_base + L("button.like_button")

    _comment_button_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_button_comment"]'
    ])

    @property
    def comment_button(self) -> List[str]:
        return self._comment_button_base + L("button.comment_button")

    _save_button_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_button_save"]'
    ])

    @property
    def save_button(self) -> List[str]:
        return self._save_button_base + L("button.save_button")

    _share_button_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_button_share"]'
    ])

    @property
    def share_button(self) -> List[str]:
        return self._share_button_base + L("button.share_button")

NAVIGATION_SELECTORS = NavigationSelectors()
BUTTON_SELECTORS = ButtonSelectors()
