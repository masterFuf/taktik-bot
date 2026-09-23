from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from ..locales import L


def _labels(key: str) -> List[str]:
    """The non-empty labels of a locale key (a label is a bare visible string, not an xpath)."""
    return [label for label in L(key) if label and label.strip()]


@dataclass
class UnfollowSelectors:
    """Selectors for the unfollow workflow.

    No visible text is written here. Until 2026-09-24 the list path looked for the literal
    strings 'Following', 'Follow back', 'Unfollow' and 'Followers': on a phone in French it found
    no button at all and spent its session scrolling. Every label now comes from the locale layer
    (`L(...)`), and the row buttons are read through the shared state classifier
    (`classify_follow_state`, the labels `profile.follow_state_labels_*`), so the list and the
    profile header agree on what a button says, in every language.
    """

    # === Following button on a profile (locales overlay) ===
    @property
    def following_button(self) -> List[str]:
        return L("unfollow.following_button")

    # === Language-neutral resource ids of the follow lists ===
    following_list_button_resource_id: str = 'com.instagram.android:id/follow_list_row_large_follow_button'
    following_list_username_resource_id: str = 'com.instagram.android:id/follow_list_username'
    unfollow_confirm_resource_name: str = 'primary_button'
    unified_follow_list_tab_layout_resource_name: str = 'unified_follow_list_tab_layout'
    follow_list_subtitle_resource_name: str = 'follow_list_subtitle'
    category_container_resource_name: str = 'container'
    category_title_resource_name: str = 'title'

    def active_resource_id(self, app_id: str, resource_name: str) -> str:
        return f'{app_id}:id/{resource_name}'

    def unified_follow_list_tab_layout_selector(self, app_id: str) -> str:
        resource_id = self.active_resource_id(
            app_id,
            self.unified_follow_list_tab_layout_resource_name,
        )
        return f'//*[@resource-id="{resource_id}"]'

    # === Followers tab of the unified follow-list view (locales overlay) ===
    # Its title carries the count and a label: "673 followers" on Instagram 447 in French and in
    # English. The third tab, "abonnements" in French, is the paid SUBSCRIPTIONS list, not the
    # following list: never use that word to find either.
    @property
    def followers_tab_labels(self) -> List[str]:
        return _labels("unfollow.followers_tab_labels")

    def unified_followers_tab_selectors(self, app_id: str) -> List[str]:
        layout = self.unified_follow_list_tab_layout_selector(app_id)
        return [f'{layout}//*[contains(@text, "{label}")]' for label in self.followers_tab_labels]

    def active_follow_list_button_resource_id(self, app_id: str) -> str:
        resource_name = self.following_list_button_resource_id.rsplit(':id/', 1)[-1]
        return self.active_resource_id(app_id, resource_name)

    def active_follow_list_username_resource_id(self, app_id: str) -> str:
        resource_name = self.following_list_username_resource_id.rsplit(':id/', 1)[-1]
        return self.active_resource_id(app_id, resource_name)

    def active_follow_list_subtitle_resource_id(self, app_id: str) -> str:
        return self.active_resource_id(app_id, self.follow_list_subtitle_resource_name)

    def follow_list_username_selector(self, app_id: str) -> str:
        """Every username of the open follow list (language-neutral)."""
        return f'//*[@resource-id="{self.active_follow_list_username_resource_id(app_id)}"]'

    def follow_list_row_button_selector(self, app_id: str) -> str:
        """Every row action button of the open follow list (language-neutral): its text is then
        read through the shared state classifier."""
        return f'//*[@resource-id="{self.active_follow_list_button_resource_id(app_id)}"]'

    # === "Followers you don't follow back" category of the followers tab (locales overlay) ===
    # These are FANS: people who follow you and whom you do not follow. The category says
    # nothing about the accounts you follow.
    @property
    def fans_category_labels(self) -> List[str]:
        return _labels("unfollow.fans_category_labels")

    def fans_category_selectors(self, app_id: str) -> List[str]:
        container = self.active_resource_id(app_id, self.category_container_resource_name)
        title = self.active_resource_id(app_id, self.category_title_resource_name)
        selectors: List[str] = []
        for label in self.fans_category_labels:
            selectors.append(f'//*[@resource-id="{container}"][contains(@content-desc, "{label}")]')
            selectors.append(f'//*[@resource-id="{title}"][contains(@text, "{label}")]')
        return selectors

    # === Unfollow confirmation in the popup (locales overlay) ===
    @property
    def unfollow_confirm(self) -> List[str]:
        return L("unfollow.unfollow_confirm")

    @property
    def unfollow_confirm_labels(self) -> List[str]:
        """The label of the confirm button: the same unfollow labels the state classifier uses."""
        return _labels("profile.follow_state_labels_unfollow")

    def unfollow_confirm_selectors(self, app_id: str) -> List[str]:
        """The dialog's primary button first, scoped by its id AND its label; then any button
        carrying the label, for a layout where the id changed."""
        button = self.active_resource_id(app_id, self.unfollow_confirm_resource_name)
        scoped = [f'//*[@resource-id="{button}"][contains(@text, "{label}")]'
                  for label in self.unfollow_confirm_labels]
        loose = [f'//android.widget.Button[contains(@text, "{label}")]'
                 for label in self.unfollow_confirm_labels]
        return scoped + loose

    # === Username in the following list ===
    following_list_item: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/follow_list_username"]'
    ])

    # === Onglet following/abonnements (overlay locales/) ===
    @property
    def following_tab(self) -> List[str]:
        return L("unfollow.following_tab")

    # === List sorting ===
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

    # === Follow-button detection after an unfollow (locales overlay) ===
    @property
    def follow_button_after_unfollow(self) -> List[str]:
        return L("unfollow.follow_button_after_unfollow")

UNFOLLOW_SELECTORS = UnfollowSelectors()
