from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from taktik.core.social_media.instagram.ui.selectors.locales import L
from taktik.core.social_media.instagram.ui.selectors.shell.popups import POPUP_SELECTORS


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

    def unified_followers_tab_selectors(self, app_id: str, selected: Optional[bool] = None) -> List[str]:
        return self.unified_tab_selectors(app_id, "followers", selected)

    # === Following tab of the same view: "1 287 suivi(e)s", "48 following" (locales overlay) ===
    @property
    def following_tab_labels(self) -> List[str]:
        return _labels("unfollow.following_tab_labels")

    def unified_following_tab_selectors(self, app_id: str, selected: Optional[bool] = None) -> List[str]:
        return self.unified_tab_selectors(app_id, "following", selected)

    def tab_labels(self, kind: str) -> List[str]:
        """The labels of a tab of the unified list: kind 'following' or 'followers'."""
        return self.following_tab_labels if kind == "following" else self.followers_tab_labels

    def unified_tab_selectors(self, app_id: str, kind: str, selected: Optional[bool] = None) -> List[str]:
        """The title of the `kind` tab; `selected=True` matches it only while it is the open tab
        (the title button carries `selected="true"` on the tab shown)."""
        layout = self.unified_follow_list_tab_layout_selector(app_id)
        state = "" if selected is None else f' and @selected="{"true" if selected else "false"}"'
        return [f'{layout}//*[contains(@text, "{label}"){state}]' for label in self.tab_labels(kind)]

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

    def follow_list_subtitle_selector(self, app_id: str) -> str:
        """Every display name (the line under the username) of the open follow list."""
        return f'//*[@resource-id="{self.active_follow_list_subtitle_resource_id(app_id)}"]'

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

    # The OTHER categories of the followers tab, those that are not the fans (locales overlay):
    # « Least interacted with », « Deactivated accounts ». Instagram may serve them without the fans
    # one (410 in French, 2026-10-24: « Comptes désactivés » alone, then « Tous les followers »).
    @property
    def other_follower_category_labels(self) -> List[str]:
        return _labels("unfollow.other_follower_category_labels")

    # === Head of a follow list (language-neutral, but the categories' labels) ===
    # The rows are the children of the framework's list; the first one is the search box while the
    # list shows its top. When Instagram serves the categories of our followers tab, they come right
    # under the search box, after a spacer and a header (« Catégories »), then a divider, a spacer
    # and a header (« Tous les followers ») above the accounts; on Instagram 447 the sort row
    # (« Trié par Par défaut ») may come there instead of that last header.
    follow_list_resource_id: str = 'android:id/list'
    follow_list_search_resource_name: str = 'row_search_edit_text'
    # The rows that only frame the list's head: spacer, section header, divider.
    follow_list_frame_row_resource_names: tuple = ('gap_binder_group', 'frame_header', 'divider')

    def list_shows_no_fans_category_selector(self, app_id: str) -> str:
        """The first account of the open follow list, read at its top, when nothing above it but its
        search box, its sort row, the rows that frame the head and the categories a locale knows as
        not the fans one: the list shows no fans category.

        A category whose label no locale knows (it could be the fans one, renamed), or any row of an
        unknown kind, above the accounts matches nothing; so does a list scrolled off its top, whose
        first row is no longer the search box, or a head longer than the screen, with no account.
        """
        search = self.active_resource_id(app_id, self.follow_list_search_resource_name)
        sort_row = ' or '.join(f'.{selector}' for selector in self.sort_entry_label)
        frame_row = ' or '.join(f'@resource-id="{self.active_resource_id(app_id, name)}"'
                                for name in self.follow_list_frame_row_resource_names)
        container = self.active_resource_id(app_id, self.category_container_resource_name)
        other_label = ' or '.join(f'contains(@content-desc, "{label}")'
                                  for label in self.other_follower_category_labels) or 'false()'
        other_category = f'@resource-id="{container}" and ({other_label})'
        account = f'.{self.follow_list_username_selector(app_id)}'
        # `preceding-sibling` counts from the nearest row: the last one is the search box.
        return (f'//*[@resource-id="{self.follow_list_resource_id}"][*[1][.//*[@resource-id="{search}"]]]'
                f'/*[{account}][1]'
                f'[not(preceding-sibling::*[position() < last()][not({sort_row} or {frame_row} or ({other_category}))])]')

    # === Unfollow confirmation in the popup (locales overlay) ===
    @property
    def unfollow_confirm(self) -> List[str]:
        return L("unfollow.unfollow_confirm")

    @property
    def unfollow_confirm_labels(self) -> List[str]:
        """The label of the confirm button: the same unfollow labels the state classifier uses."""
        return _labels("profile.follow_state_labels_unfollow")

    def unfollow_confirm_selectors(self, app_id: str) -> List[str]:
        """The dialog's primary button first, scoped by its id AND its label; then the existing
        localized confirmation popup selectors (`popup.unfollow_confirmation_selectors`), for a
        layout where the id changed."""
        button = self.active_resource_id(app_id, self.unfollow_confirm_resource_name)
        scoped = [f'//*[@resource-id="{button}"][contains(@text, "{label}")]'
                  for label in self.unfollow_confirm_labels]
        return scoped + list(POPUP_SELECTORS.unfollow_confirmation_selectors)

    # === Username in the following list ===
    following_list_item: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/follow_list_username"]'
    ])

    # === List sorting ===
    _sort_button_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/sorting_entry_row_icon"]',
    ])

    @property
    def sort_button(self) -> List[str]:
        return self._sort_button_base + L("unfollow.sort_button")

    # The list's sort header ("Trié par Par défaut", "Sorted by Default"): it names the sort the
    # list is in, so a tapped option is confirmed there (language-neutral id).
    sort_entry_label: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/sorting_entry_row_option"]',
    ])

    @property
    def sort_option_default(self) -> List[str]:
        return L("unfollow.sort_option_default")

    @property
    def sort_option_latest(self) -> List[str]:
        return L("unfollow.sort_option_latest")

    @property
    def sort_option_earliest(self) -> List[str]:
        return L("unfollow.sort_option_earliest")

    # === Follow-button detection after an unfollow (locales overlay) ===
    @property
    def follow_button_after_unfollow(self) -> List[str]:
        return L("unfollow.follow_button_after_unfollow")

UNFOLLOW_SELECTORS = UnfollowSelectors()
