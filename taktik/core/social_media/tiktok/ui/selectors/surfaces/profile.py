"""Sélecteurs UI pour les profils utilisateurs TikTok."""

from typing import Any, Dict, List
from dataclasses import dataclass, field

from ..locales import L


@dataclass
class ProfileSelectors:
    """Sélecteurs pour les profils utilisateurs TikTok.

    Basé sur UI dump: ui_dump_20260107_210156.xml (Profile page)
    Resource-IDs identifiés:
    - qf8: Display name
    - qh5: @username
    - qfw: Compteurs (following/followers/likes)
    - qfv: Labels des compteurs
    - b5s: Profile photo
    - h9p: Profile views button
    - xvy: Profile views count
    """

    # === Header profil ===
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

    # === Informations profil ===
    display_name: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qf8")]',
    ])

    username: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qh5")]',
    ])

    username_content_description: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "@")]',
    ])

    @property
    def edit_profile_button(self) -> List[str]:
        return L("profile.edit_profile_button")

    # === Compteurs (utilise qfw pour les valeurs, qfv pour les labels) ===
    stat_value: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qfw")]',
    ])

    stat_label: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qfv")]',
    ])

    @property
    def following_count(self) -> List[str]:
        return L("profile.following_count")

    @property
    def followers_count(self) -> List[str]:
        return L("profile.followers_count")

    @property
    def likes_count(self) -> List[str]:
        return L("profile.likes_count")

    # === Bio ===
    bio: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@text, "For ") or contains(@text, "http")]',
        '//*[contains(@text, "instagram.com") or contains(@text, "youtube.com")]',
    ])

    tiktok_studio_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/a_l")]',
        '//*[@text="TikTok Studio"]',
    ])

    # === Onglets de contenu profil ===
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

    video_item: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/e52")]',
    ])

    video_cover: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/cover")]',
    ])

    video_view_count: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/xxy")]',
    ])

    # === Boutons d'action profil (sur profil d'un autre utilisateur) ===
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
    ])

    @property
    def profile_page_indicator(self) -> List[str]:
        return self._profile_page_indicator_base + L("profile.profile_page_indicator")

    # Bio text (resource-id: qfx)
    bio_text: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qfx")]',
    ])

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
