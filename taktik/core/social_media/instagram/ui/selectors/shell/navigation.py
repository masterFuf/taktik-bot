from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from taktik.core.social_media.instagram.ui.selectors.locales import L

@dataclass
class NavigationSelectors:
    """Selectors for navigation and system buttons."""

    # === Main navigation (lists, for fallbacks) ===
    # Use resource-id selectors first to avoid clicking Android system buttons. The home tab's
    # `contains` names the bottom bar's `feed_tab` and nothing else on the 2 527 Instagram dumps of
    # the corpus and the captures (no other id holds "feed_tab").
    _home_tab_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "com.instagram.android:id/feed_tab")]',
    ])

    @property
    def home_tab(self) -> List[str]:
        return self._home_tab_base + L("navigation.home_tab")

    # The bottom bar's tab, by its exact id: `contains(@resource-id, ".../search_tab")` also names
    # `search_tab_bar_layout`, the tab bar of a hashtag page (For you, Accounts, Not personalized,
    # Audio), which hides the bottom bar; a tap in its middle opened one of its tabs.
    _search_tab_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/search_tab"]',
    ])

    @property
    def search_tab(self) -> List[str]:
        return self._search_tab_base + L("navigation.search_tab")

    # The bottom bar's tab, by its exact id: `contains(@resource-id, "profile_tab")` also names
    # the grid tabs of a profile page (profile_tabs_container, profile_tab_layout,
    # profile_tab_icon_view), earlier in the dump, and a tap there opens Reels or Reposts.
    _profile_tab_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_tab"]',
    ])

    @property
    def profile_tab(self) -> List[str]:
        return self._profile_tab_base + L("navigation.profile_tab")

    # === System buttons (lists, for fallbacks) ===
    @property
    def back_button(self) -> List[str]:
        return L("navigation.back_button")

    @property
    def close_button(self) -> List[str]:
        return L("navigation.close_button")

    # === Back buttons, every supported language ===
    _back_buttons_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/action_bar_button_back"]',
    ])

    @property
    def back_buttons(self) -> List[str]:
        return self._back_buttons_base + L("navigation.back_buttons")

    # === Instagram root screens ===
    # A main tab's own screen (home feed, Explore, Reels, DM inbox, own profile): the tab bar is
    # up and Instagram shows no back arrow. Back there leaves Instagram (home feed) or jumps to
    # another tab. Told by the tab bar, not the selected tab: after a cold start no tab is
    # selected yet (every home feed of the C0 captures).
    main_tab_bar: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/feed_tab"]',
        '//*[@resource-id="com.instagram.android:id/clips_tab"]',
        '//*[@resource-id="com.instagram.android:id/search_tab"]',
        '//*[@resource-id="com.instagram.android:id/profile_tab"]',
        '//*[@resource-id="com.instagram.android:id/direct_tab"]',
    ])

    # What a Back closes without leaving the screen under it: a bottom sheet (comments, likers,
    # share: one chassis on IG 410), a dialog, the keyboard of a focused field.
    back_closable_layers: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/layout_container_bottom_sheet"]',
        '//*[@resource-id="com.instagram.android:id/background_dimmer"]',
        '//*[@resource-id="com.instagram.android:id/igds_alert_dialog_headline"]',
        '//*[@resource-id="com.instagram.android:id/dialog_container"]',
        '//android.widget.EditText[@focused="true" and @package="com.instagram.android"]',
    ])

    # === Back buttons for the followers/following list ===
    back_buttons_action_bar: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/left_action_bar_buttons"]//android.widget.ImageView[@clickable="true"]',
        '//*[@resource-id="com.instagram.android:id/left_action_bar_buttons"]/android.widget.ImageView',
        '//*[@resource-id="com.instagram.android:id/action_bar_button_back"]',
    ])

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

    @property
    def search_screen_bar(self) -> List[str]:
        """The search screen's own bar (Explore, and the results of a query), by its id alone.

        It tells the search screen apart without its tab bar, which Instagram 447 hides under the
        results of a query. Without the labels of `explore_search_bar`: "Rechercher" also names the
        search fields of a likers sheet or a follow list (`search_edit_text`), screens of another
        kind. The id is on the search screens only, in the capture corpus (67 dumps 410, 26 dumps 447).
        """
        return self._explore_search_bar_base

    # === Search result selectors (use .format(username=...) for dynamic parts) ===
    search_result_container_resource_id: str = 'com.instagram.android:id/row_search_user_container'
    search_result_username_resource_id: str = 'com.instagram.android:id/row_search_user_username'

    # A row that names an account without being an account row: the "keyword" row of Instagram
    # 447, whose title is a query ("nasa", or "interpretação espiritual nasa") and whose subtitle
    # names the account: "nasa • 104 M followers". `{username}` stands for the exact handle; the
    # " •" after it keeps out a neighbour that holds it ("nasasolarsystem • 2,7 M followers").
    # Empty in the reference: no keyword row of the 410 corpus has a subtitle (25 search screens
    # with a keyword row, 2026-09-25 to 09-28); the 447 entry is in the version overrides.
    _search_result_keyword_row_templates: List[str] = field(default_factory=list)

    # What a tap on a result row must never reach: the avatar ring, a button of its own over the
    # row (left of an account row, right of a keyword row), which opens the account's story.
    search_result_avatar_ring: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_search_avatar_with_ring"]',
    ])

    def search_result_selectors_for_username(self, username: str) -> List[str]:
        """Build selectors for a search result row matching an exact username: its account row
        first, then a row of another kind that names that exact handle (version overrides)."""
        container_id = self.search_result_container_resource_id
        username_id = self.search_result_username_resource_id
        return [
            f'//*[contains(@resource-id, "{container_id}")][.//*[contains(@resource-id, "{username_id}") and @text="{username}"]]',
            f'//*[contains(@resource-id, "{container_id}")][.//*[@text="{username}"]]',
            f'//android.widget.TextView[contains(@resource-id, "{username_id}") and @text="{username}"]',
            f'//*[@clickable="true"][.//*[contains(@resource-id, "{username_id}") and @text="{username}"]]',
        ] + [template.replace("{username}", username) for template in self._search_result_keyword_row_templates]

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
    """Selectors for the common interaction buttons."""

    # === Post interaction buttons (lists, for fallbacks) ===
    _like_button_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_feed_button_like"]',
        # Reel / clips player like button (dump real-device IG 410, 2026-06-11):
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

    # Bare LABELS (not xpaths) of the same four buttons, for the cases where a button is
    # already in hand and the question is "which one is it?" — post scraping reads the
    # counter that FOLLOWS an action button, so it has to name the button first.
    @property
    def action_label_like(self) -> List[str]:
        return L("button.action_label_like")

    @property
    def action_label_comment(self) -> List[str]:
        return L("button.action_label_comment")

    @property
    def action_label_share(self) -> List[str]:
        return L("button.action_label_share")

    @property
    def action_label_save(self) -> List[str]:
        return L("button.action_label_save")


NAVIGATION_SELECTORS = NavigationSelectors()
BUTTON_SELECTORS = ButtonSelectors()
