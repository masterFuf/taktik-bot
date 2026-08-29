"""UI selectors for TikTok user profiles."""

from typing import Any, Dict, List
from dataclasses import dataclass, field

from ..locales import L


@dataclass
class ProfileSelectors:
    """Selectors for TikTok user profiles.

    Based on a real dump of the profile page.
    Resource-IDs identifiés:
    - qf8: Display name
    - qh5: @username
    - qfw: Compteurs (following/followers/likes)
    - the counter labels
    - b5s: Profile photo
    - h9p: Profile views button
    - xvy: Profile views count
    """

    # === Profile header ===
    _profile_photo_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/b5s")]',
    ])

    @property
    def profile_photo(self) -> List[str]:
        return self._profile_photo_base + L("profile.profile_photo")

    @property
    def create_story_button(self) -> List[str]:
        return L("profile.create_story_button")

    _profile_views_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/h9p")]',
    ])

    @property
    def profile_views_button(self) -> List[str]:
        return self._profile_views_button_base + L("profile.profile_views_button")

    profile_views_count: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/xvy")]',
    ])

    @property
    def profile_menu_button(self) -> List[str]:
        return L("profile.profile_menu_button")

    # === Profile information ===
    _display_name_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qf8")]',
    ])

    @property
    def display_name(self) -> List[str]:
        return self._display_name_base + L("profile.display_name_anchors")

    _username_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qh5")]',
    ])

    @property
    def username(self) -> List[str]:
        return self._username_base + L("profile.username_anchors")

    username_content_description: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "@")]',
    ])

    @property
    def edit_profile_button(self) -> List[str]:
        return L("profile.edit_profile_button")

    # === Counters (one id for the values, another for the labels) ===
    _stat_value_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qfw")]',
    ])

    @property
    def stat_value(self) -> List[str]:
        return self._stat_value_base + L("profile.stat_value_anchors")

    _stat_label_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qfv")]',
    ])

    @property
    def stat_label(self) -> List[str]:
        return self._stat_label_base + L("profile.stat_label_anchors")

    @property
    def following_count(self) -> List[str]:
        return L("profile.following_count")

    @property
    def followers_count(self) -> List[str]:
        return L("profile.followers_count")

    @property
    def likes_count(self) -> List[str]:
        return L("profile.likes_count")

    # Bare LABELS of the three profile stats, used to tell which value you are holding
    # once the row has been paired by position. Read via `classify_profile_stat_label`.
    @property
    def stat_label_following(self) -> List[str]:
        return L("profile.stat_label_following")

    @property
    def stat_label_followers(self) -> List[str]:
        return L("profile.stat_label_followers")

    @property
    def stat_label_likes(self) -> List[str]:
        return L("profile.stat_label_likes")

    @property
    def friends_button_labels(self) -> List[str]:
        return L("profile.friends_button_labels")

    # === Bio ===
    bio: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@text, "For ") or contains(@text, "http")]',
        '//*[contains(@text, "instagram.com") or contains(@text, "youtube.com")]',
    ])

    tiktok_studio_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/a_l")]',
        '//*[@text="TikTok Studio"]',
    ])

    # === Profile content tabs ===
    @property
    def videos_tab(self) -> List[str]:
        return L("profile.videos_tab")

    @property
    def private_videos_tab(self) -> List[str]:
        return L("profile.private_videos_tab")

    @property
    def favourites_tab(self) -> List[str]:
        return L("profile.favourites_tab")

    @property
    def liked_videos_tab(self) -> List[str]:
        return L("profile.liked_videos_tab")

    # === Grille de vidéos ===
    video_grid: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/gxd")]',
        '//android.widget.GridView',
    ])

    _video_item_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/e52")]',
    ])

    @property
    def video_item(self) -> List[str]:
        return self._video_item_base + L("profile.video_item_anchors")

    video_cover: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/cover")]',
    ])

    _video_view_count_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/xxy")]',
    ])

    @property
    def video_view_count(self) -> List[str]:
        return self._video_view_count_base + L("profile.video_view_count_anchors")

    # === Profile action buttons, on someone else's profile ===
    @property
    def follow_button(self) -> List[str]:
        return L("profile.follow_button")

    @property
    def following_button(self) -> List[str]:
        return L("profile.following_button")

    _message_button_base: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Message"]',
        '//android.widget.Button[@text="Message"]',
        '//*[contains(@resource-id, ":id/eme")][@text="Message"]',
        '//android.widget.TextView[@text="Message"]',
    ])

    @property
    def message_button(self) -> List[str]:
        return self._message_button_base + L("profile.message_button")

    # === Page detection: profile page ===
    _profile_page_indicator_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qh5")]',
        '//*[contains(@resource-id, ":id/gxd")]',
        # A2. The two ids above are 43.1.4 only — on 46.6.3 the header is ss2/svt/fij and the
        # whole indicator read 0 while standing on charlidamelio's profile, so "am I on a
        # profile" answered no on every profile of the newer version.
        #
        # The handle itself is the anchor: TikTok renders it as a Button whose text starts with
        # "@", on both versions and in both languages. Measured 1 on a profile and 0 on the feed
        # on 43.1.4 AND 46.6.3 — the second half is what makes it an indicator rather than a
        # decoration.
        '//android.widget.Button[starts-with(@text, "@")]',
    ])

    @property
    def profile_page_indicator(self) -> List[str]:
        return self._profile_page_indicator_base + L("profile.profile_page_indicator")

    # Bio text (resource-id: qfx)
    _bio_text_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qfx")]',
    ])

    @property
    def bio_text(self) -> List[str]:
        return self._bio_text_base + L("profile.bio_text_anchors")

    # Verified badge
    @property
    def verified_badge(self) -> List[str]:
        return L("profile.verified_badge")

    # Private account indicator
    @property
    def private_indicator(self) -> List[str]:
        return L("profile.private_indicator")

    # === Story page detection ===
    story_timestamp: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/xyx")]',
    ])

    @property
    def story_close_button(self) -> List[str]:
        return L("profile.story_close_button")

    story_follow_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/rdo")]',
    ])

    _story_message_input_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qwz")][@text="Message..."]',
    ])

    @property
    def story_message_input(self) -> List[str]:
        return self._story_message_input_base + L("profile.story_message_input")

    story_page_indicator: List[str] = field(default_factory=lambda: [
    ])

    # Story username (clickable, leads to profile)
    story_username: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/title")][@clickable="true"]',
        '//*[contains(@resource-id, ":id/s28")]//android.widget.Button[contains(@resource-id, ":id/title")]',
    ])

    # === Privacy blocked conversation indicators ===
    @property
    def unable_to_send_message(self) -> List[str]:
        return L("profile.unable_to_send_message")

    _privacy_blocked_message_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/uq5")]',
        '//*[contains(@text, "privacy settings")]',
    ])

    @property
    def privacy_blocked_message(self) -> List[str]:
        return self._privacy_blocked_message_base + L("profile.privacy_blocked_message")

    website_text_probe: str = "http"
    verified_description_probe: str = "Verified"
    private_text_probe: str = "private"
    message_button_text_probe: str = "Message"

    @property
    def bio_button_fallback_selector(self) -> Dict[str, Any]:
        return {"className": "android.widget.Button", "clickable": True}

    @property
    def message_button_text_selector(self) -> Dict[str, Any]:
        return {"text": self.message_button_text_probe}


PROFILE_SELECTORS = ProfileSelectors()
