from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from ..locales import L

@dataclass
class UnfollowSelectors:
    """Sélecteurs pour le workflow d'unfollow."""

    # === Bouton Following/Abonné sur un profil (overlay locales/) ===
    @property
    def following_button(self) -> List[str]:
        return L("unfollow.following_button")

    # === Bouton Following dans la liste following (pour simple unfollow) ===
    following_list_button_resource_id: str = 'com.instagram.android:id/follow_list_row_large_follow_button'
    following_list_username_resource_id: str = 'com.instagram.android:id/follow_list_username'
    following_tab_title_resource_id: str = 'com.instagram.android:id/title'
    unfollow_confirm_resource_id: str = 'com.instagram.android:id/primary_button'
    following_tab_text_probe: str = 'following'
    following_button_text: str = 'Following'
    follow_back_button_text: str = 'Follow back'
    unfollow_confirm_text: str = 'Unfollow'
    unified_follow_list_tab_layout_resource_name: str = 'unified_follow_list_tab_layout'
    follow_list_subtitle_resource_name: str = 'follow_list_subtitle'

    def active_resource_id(self, app_id: str, resource_name: str) -> str:
        return f'{app_id}:id/{resource_name}'

    def unified_follow_list_tab_layout_selector(self, app_id: str) -> str:
        resource_id = self.active_resource_id(
            app_id,
            self.unified_follow_list_tab_layout_resource_name,
        )
        return f'//*[@resource-id="{resource_id}"]'

    def unified_followers_tab_selector(self, app_id: str) -> str:
        return (
            self.unified_follow_list_tab_layout_selector(app_id)
            + '//*[contains(@text, "Followers")]'
        )

    def active_follow_list_button_resource_id(self, app_id: str) -> str:
        resource_name = self.following_list_button_resource_id.rsplit(':id/', 1)[-1]
        return self.active_resource_id(app_id, resource_name)

    def active_follow_list_username_resource_id(self, app_id: str) -> str:
        resource_name = self.following_list_username_resource_id.rsplit(':id/', 1)[-1]
        return self.active_resource_id(app_id, resource_name)

    def active_follow_list_subtitle_resource_id(self, app_id: str) -> str:
        return self.active_resource_id(app_id, self.follow_list_subtitle_resource_name)

    def non_followers_category_selectors(self, app_id: str) -> List[str]:
        return [
            '//*[contains(@content-desc, "don\'t follow back")]',
            '//*[contains(@content-desc, "People you don")]',
            (
                f'//*[@resource-id="{self.active_resource_id(app_id, "container")}"]'
                '[contains(@content-desc, "follow")]'
            ),
            (
                f'//*[@resource-id="{self.active_resource_id(app_id, "title")}"]'
                '[contains(@text, "don\'t follow back")]'
            ),
            (
                f'//*[@resource-id="{self.active_resource_id(app_id, "title")}"]'
                '[contains(@text, "follow back")]'
            ),
        ]
    
    # === Confirmation d'unfollow dans la popup (overlay locales/) ===
    @property
    def unfollow_confirm(self) -> List[str]:
        return L("unfollow.unfollow_confirm")

    # === Username dans la liste following ===
    following_list_item: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/follow_list_username"]'
    ])
    
    # === Onglet following/abonnements (overlay locales/) ===
    @property
    def following_tab(self) -> List[str]:
        return L("unfollow.following_tab")

    # === Tri de la liste ===
    _sort_button_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/sorting_entry_row_icon"]',
    ])

    @property
    def sort_button(self) -> List[str]:
        return self._sort_button_base + L("unfollow.sort_button")

    @property
    def sort_option_default(self) -> List[str]:
        return L("unfollow.sort_option_default")

    @property
    def sort_option_latest(self) -> List[str]:
        return L("unfollow.sort_option_latest")

    @property
    def sort_option_earliest(self) -> List[str]:
        return L("unfollow.sort_option_earliest")

    # === Détection "follows you back" (overlay locales/) ===
    @property
    def follows_back_indicators(self) -> List[str]:
        return L("unfollow.follows_back_indicators")

    # === Détection bouton Follow après unfollow (overlay locales/) ===
    @property
    def follow_button_after_unfollow(self) -> List[str]:
        return L("unfollow.follow_button_after_unfollow")

UNFOLLOW_SELECTORS = UnfollowSelectors()
