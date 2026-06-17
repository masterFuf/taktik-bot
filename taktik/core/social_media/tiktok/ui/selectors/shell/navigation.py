"""Sélecteurs UI pour la navigation principale TikTok."""

from typing import List
from dataclasses import dataclass, field

from ..locales import L


@dataclass
class NavigationSelectors:
    """Sélecteurs pour la navigation principale TikTok.

    Basé sur UI dump: ui_dump_20260107_205804.xml (For You page)
    Resource-IDs identifiés:
    - mky: Bottom navigation container
    - mkq: Home tab
    - mkp: Friends tab
    - mkn: Create button
    - mkr: Inbox tab
    - mks: Profile tab
    """

    # === Bottom Navigation Bar (resource-ids réels) ===
    bottom_nav_container: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/mky")]',
    ])

    _home_tab_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/mkq")]',
    ])

    @property
    def home_tab(self) -> List[str]:
        return self._home_tab_base + L("navigation.home_tab")

    _friends_tab_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/mkp")]',
    ])

    @property
    def friends_tab(self) -> List[str]:
        return self._friends_tab_base + L("navigation.friends_tab")

    _create_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/mkn")]',
    ])

    @property
    def create_button(self) -> List[str]:
        return self._create_button_base + L("navigation.create_button")

    _inbox_tab_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/mkr")]',
        '//*[contains(@content-desc, "Messages")]',
    ])

    @property
    def inbox_tab(self) -> List[str]:
        return self._inbox_tab_base + L("navigation.inbox_tab")

    _profile_tab_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/mks")]',
    ])

    @property
    def profile_tab(self) -> List[str]:
        return self._profile_tab_base + L("navigation.profile_tab")

    # === Header Tabs (For You page) ===
    live_tab: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="LIVE"]',
        '//*[@text="LIVE"]',
    ])

    @property
    def explore_tab(self) -> List[str]:
        return L("navigation.explore_tab")

    @property
    def following_tab(self) -> List[str]:
        return L("navigation.following_tab")

    _shop_tab_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Boutique")]',
    ])

    @property
    def shop_tab(self) -> List[str]:
        return self._shop_tab_base + L("navigation.shop_tab")

    for_you_tab: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="For You"]',
        '//*[@text="For You"]',
        '//*[contains(@content-desc, "Pour toi")]',
    ])

    # === Search button (header on For You page) ===
    # Resource-id: irz (from ui_dump_20260111_121059.xml)
    _search_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/irz")]',
    ])

    @property
    def search_button(self) -> List[str]:
        return self._search_button_base + L("navigation.search_button")

    # === Tab selected states (for page detection) ===
    _home_tab_selected_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/mkq")][@selected="true"]',
    ])

    @property
    def home_tab_selected(self) -> List[str]:
        return self._home_tab_selected_base + L("navigation.home_tab_selected")

    _inbox_tab_selected_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/mkr")][@selected="true"]',
    ])

    @property
    def inbox_tab_selected(self) -> List[str]:
        return self._inbox_tab_selected_base + L("navigation.inbox_tab_selected")

    # === Back button ===
    _back_button_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.android.systemui:id/back"]',
    ])

    @property
    def back_button(self) -> List[str]:
        return self._back_button_base + L("navigation.back_button")


NAVIGATION_SELECTORS = NavigationSelectors()
