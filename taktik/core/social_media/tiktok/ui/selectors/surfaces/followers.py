"""Sélecteurs UI pour la liste des followers TikTok."""

from typing import List
from dataclasses import dataclass, field

from ..locales import L


@dataclass
class FollowersSelectors:
    """Sélecteurs pour la liste des followers d'un utilisateur TikTok.

    Basé sur UI dumps:
    - ui_dump_20260111_135605.xml (Search results - Users tab)
    - ui_dump_20260111_135614.xml (User profile page)
    - ui_dump_20260111_135622.xml (Followers list page)

    Resource-IDs identifiés:
    - qh5: @username on profile
    - qfw: Counter value (followers, following, likes)
    - qfv: Counter label (Followers, Following, Likes)
    - yhq: Display name in followers list
    - ygv: Username in followers list
    - rdh: Follow button in followers list
    - s6p: RecyclerView for followers list
    """

    # === Users tab in search results ===
    users_tab: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Users"]',
        '//android.widget.FrameLayout[@content-desc="Users"]',
        '//android.widget.TextView[@text="Users"]',
        '//android.widget.TextView[@text="Utilisateurs"]',
    ])

    # === User item in search results (clickable to go to profile) ===
    user_search_item: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@clickable="true"][.//android.widget.RelativeLayout[contains(@resource-id, ":id/sh2")]]',
        '//android.widget.Button[@clickable="true"][.//android.widget.TextView[contains(@resource-id, ":id/ye2")]]',
        '//android.widget.Button[@clickable="true"][.//android.widget.Button[contains(@resource-id, ":id/rdh")]]',
    ])

    # First user in search results (Users tab)
    first_user_result: List[str] = field(default_factory=lambda: [
        '(//androidx.recyclerview.widget.RecyclerView[contains(@resource-id, ":id/lnp")]//android.widget.Button[@clickable="true"])[1]',
        '(//android.widget.Button[@clickable="true"][.//android.widget.RelativeLayout[contains(@resource-id, ":id/sh2")]])[1]',
        '(//android.widget.Button[@clickable="true"][.//android.widget.TextView[contains(@resource-id, ":id/ye2")]])[1]',
        '(//android.widget.RelativeLayout[contains(@resource-id, ":id/sh2")][@clickable="true"])[1]',
    ])

    # === Profile page elements ===
    profile_username: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qh5")]',
        '//android.widget.Button[contains(@resource-id, ":id/qh5")]',
    ])

    # Followers counter (clickable to open followers list) — langue-dependant (overlay locales/)
    @property
    def followers_counter(self) -> List[str]:
        return L("followers.followers_counter")

    # Following counter — langue-dependant (overlay locales/)
    @property
    def following_counter(self) -> List[str]:
        return L("followers.following_counter")

    # Follow button on profile — langue-dependant (overlay locales/)
    @property
    def profile_follow_button(self) -> List[str]:
        return L("followers.profile_follow_button")

    # === Followers list page ===
    @property
    def followers_tab(self) -> List[str]:
        return L("followers.followers_tab")

    @property
    def following_tab(self) -> List[str]:
        return L("followers.following_tab")

    # RecyclerView containing followers list
    followers_list: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/s6p")]',
        '//androidx.recyclerview.widget.RecyclerView[contains(@resource-id, ":id/s6p")]',
    ])

    # Individual follower item (clickable row)
    follower_item: List[str] = field(default_factory=lambda: [
        '//android.widget.LinearLayout[@clickable="true"][.//android.widget.Button[contains(@resource-id, ":id/rdh")]]',
    ])

    # Display name in followers list
    follower_display_name: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/yhq")]',
        '//android.widget.TextView[contains(@resource-id, ":id/yhq")]',
    ])

    # Username in followers list
    follower_username: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ygv")]',
        '//android.widget.TextView[contains(@resource-id, ":id/ygv")]',
    ])

    # Follow button in followers list — langue-dependant (overlay locales/)
    @property
    def follower_follow_button(self) -> List[str]:
        return L("followers.follower_follow_button")

    # Already following button — langue-dependant (overlay locales/)
    @property
    def follower_following_button(self) -> List[str]:
        return L("followers.follower_following_button")

    # Any follow button (Follow, Following, or Friends)
    follower_any_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/rdh")]',
        '//android.widget.Button[contains(@resource-id, ":id/rdh")]',
    ])

    # Private account notice
    private_notice: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ikr")]',
        '//android.widget.TextView[contains(@text, "can see all followers")]',
    ])

    # === Profile page - Video grid ===
    profile_grid: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/gxd")]',
        '//android.widget.GridView[contains(@resource-id, ":id/gxd")]',
    ])

    profile_post_item: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/e52")][@clickable="true"]',
        '//android.widget.FrameLayout[contains(@resource-id, ":id/e52")][@clickable="true"]',
    ])

    first_post: List[str] = field(default_factory=lambda: [
        '(//*[contains(@resource-id, ":id/e52")][@clickable="true"])[1]',
        '(//android.widget.FrameLayout[contains(@resource-id, ":id/e52")])[1]',
    ])

    post_cover: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/cover")]',
    ])

    post_view_count: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/xxy")]',
    ])

    # langue-dependant (overlay locales/)
    @property
    def profile_videos_tab(self) -> List[str]:
        return L("followers.profile_videos_tab")

    # langue-dependant (overlay locales/)
    @property
    def profile_reposted_tab(self) -> List[str]:
        return L("followers.profile_reposted_tab")

    # === Back button (in-app) ===
    back_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/b9b")]',
        '//*[contains(@resource-id, ":id/b9c")]',
        '//android.widget.ImageView[contains(@resource-id, ":id/b9b")]',
    ])

    # === Followers list page detection === — langue-dependant (overlay locales/)
    @property
    def followers_tab_selected(self) -> List[str]:
        return L("followers.followers_tab_selected")

    # === Unfollow-related === — langue-dependant (overlay locales/)
    @property
    def following_or_friends_button(self) -> List[str]:
        return L("followers.following_or_friends_button")

    @property
    def unfollow_confirm_button(self) -> List[str]:
        return L("followers.unfollow_confirm_button")

    # Following list opener (on profile page) — langue-dependant (overlay locales/)
    @property
    def following_list_opener(self) -> List[str]:
        return L("followers.following_list_opener")


FOLLOWERS_SELECTORS = FollowersSelectors()
