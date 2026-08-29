"""UI selectors for the TikTok followers list."""

from typing import List
from dataclasses import dataclass, field

from ..locales import L


@dataclass
class FollowersSelectors:
    """Selectors for the followers list of a TikTok user.

    Based on real UI dumps:
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
    # A2: the readable ids of a search result row. Measured on a real Users tab (46.6.3,
    # 2026-08-29), where EVERY selector above scored zero — all four are 43.1.4 ids, and the
    # workflow died on "Failed to click on target user" with a list of ten results on screen.
    # `tv_username` is a name a developer wrote, and the row is its nearest clickable ancestor:
    # ten rows on the tab, nothing anywhere else across 28 captured screens.
        '//*[contains(@resource-id, ":id/tv_username")]/ancestor::*[@clickable="true"][1]',
    ])

    # First user in search results (Users tab)
    first_user_result: List[str] = field(default_factory=lambda: [
        '(//androidx.recyclerview.widget.RecyclerView[contains(@resource-id, ":id/lnp")]//android.widget.Button[@clickable="true"])[1]',
        '(//android.widget.Button[@clickable="true"][.//android.widget.RelativeLayout[contains(@resource-id, ":id/sh2")]])[1]',
        '(//android.widget.Button[@clickable="true"][.//android.widget.TextView[contains(@resource-id, ":id/ye2")]])[1]',
        '(//android.widget.RelativeLayout[contains(@resource-id, ":id/sh2")][@clickable="true"])[1]',
        # Same anchor as `user_search_item`, taking the first row.
        '(//*[contains(@resource-id, ":id/tv_username")]/ancestor::*[@clickable="true"][1])[1]',
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

    # Following counter — language-dependent (locales overlay)
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
    _followers_list_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/s6p")]',
        '//androidx.recyclerview.widget.RecyclerView[contains(@resource-id, ":id/s6p")]',
    ])

    @property
    def followers_list(self) -> List[str]:
        """The scrollable list itself. `s6p` is 43.1.4 only and reads 0 on every 46.6.3 capture.

        The A2 route is structural but SCOPED to the tab bar: the bare form
        `RecyclerView[@scrollable="true"]` fires on fifteen other screens -- a decoration, not an
        indicator. Framed by the Followers tab it is 6/6 on the lists and 0 on the 39 others.
        """
        return self._followers_list_base + L("followers.followers_list_anchors")

    # Individual follower item (clickable row)
    #: CAVEAT on the first form, measured: it also fires on the inbox, the Friends tab and the
    #: 43.1.4 inbox capture -- a row with a follow button is not only a follower row. It is kept
    #: because it is the ONLY route on 43.1.4 (that version's rows carry no readable name at all),
    #: and every consumer gates on `_is_on_followers_list` first. Do not use it unscoped.
    follower_item: List[str] = field(default_factory=lambda: [
        '//android.widget.LinearLayout[@clickable="true"][.//android.widget.Button[contains(@resource-id, ":id/rdh")]]',
        # A2 for 46.6.3, where `rdh` is gone: the row is the nearest clickable ancestor of the
        # handle. 10, 10, 5 and 10 rows on the four 46.6.3 captures, 0 on the 39 other screens.
        #
        # It COMPLETES the form above rather than replacing it -- `txt_desc` does not exist on
        # 43.1.4, where the row carries no readable name at all. Three purely structural forms
        # were measured and rejected: they fire on eleven to twenty-one other screens (inbox,
        # suggestions, the Users tab, the comment sheet).
        '//*[contains(@resource-id, ":id/txt_desc")]/ancestor::*[@clickable="true"][1]',
    ])

    # Display name in followers list
    _follower_display_name_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/yhq")]',
        '//android.widget.TextView[contains(@resource-id, ":id/yhq")]',
    ])

    @property
    def follower_display_name(self) -> List[str]:
        return self._follower_display_name_base + L("followers.follower_display_name_anchors")

    # Username in followers list
    _follower_username_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ygv")]',
        '//android.widget.TextView[contains(@resource-id, ":id/ygv")]',
    ])

    @property
    def follower_username(self) -> List[str]:
        return self._follower_username_base + L("followers.follower_username_anchors")

    # Follow button in the followers list — language-dependent (locales overlay)
    @property
    def follower_follow_button(self) -> List[str]:
        return L("followers.follower_follow_button")

    # Already-following button — language-dependent (locales overlay)
    @property
    def follower_following_button(self) -> List[str]:
        return L("followers.follower_following_button")

    # Any follow button (Follow, Following, or Friends)
    _follower_any_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/rdh")]',
        '//android.widget.Button[contains(@resource-id, ":id/rdh")]',
    ])

    @property
    def follower_any_button(self) -> List[str]:
        return self._follower_any_button_base + L("followers.follower_any_button_anchors")

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
        # A2. `e52` is 43.1.4 only. On 46.6.3 it reads 0 on a profile full of videos, so the
        # workflow counted zero posts, emitted `no_posts` and left WITHOUT INTERACTING -- on
        # every profile of that version. Measured on @zachking, 2026-08-29.
        #
        # The thumbnail carries a readable id (`cover`) but is not itself clickable; the tap
        # target is its nearest clickable ancestor. 9 on both versions, 0 on the feed.
        '//*[contains(@resource-id, ":id/cover")]/ancestor::*[@clickable="true"][1]',
    ])

    first_post: List[str] = field(default_factory=lambda: [
        '(//*[contains(@resource-id, ":id/e52")][@clickable="true"])[1]',
        '(//android.widget.FrameLayout[contains(@resource-id, ":id/e52")])[1]',
        # Same A2 route as profile_post_item.
        '(//*[contains(@resource-id, ":id/cover")]/ancestor::*[@clickable="true"][1])[1]',
    ])

    post_cover: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/cover")]',
    ])

    _post_view_count_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/xxy")]',
    ])

    @property
    def post_view_count(self) -> List[str]:
        return self._post_view_count_base + L("followers.post_view_count_anchors")

    # language-dependent (locales overlay)
    @property
    def profile_videos_tab(self) -> List[str]:
        return L("followers.profile_videos_tab")

    # language-dependent (locales overlay)
    @property
    def profile_reposted_tab(self) -> List[str]:
        return L("followers.profile_reposted_tab")

    # === Back button (in-app) ===
    back_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/b9b")]',
        '//*[contains(@resource-id, ":id/b9c")]',
        '//android.widget.ImageView[contains(@resource-id, ":id/b9b")]',
    ])

    # === Followers list page detection === — language-dependent (locales overlay)
    @property
    def followers_tab_selected(self) -> List[str]:
        return L("followers.followers_tab_selected")

    # === Unfollow-related === — language-dependent (locales overlay)
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

    # The own account's Following / Followers lists use the SAME row anchors as a visited
    # profile's follower list -- `follower_username` (`txt_desc`), `follower_display_name`
    # (`txt_user_name`) and `follower_any_button` all resolve there. Measured 2026-08-29 on the
    # operated account's own lists, so no separate catalogue: a second spelling of the same
    # three fields is a second thing to keep in sync.

    def row_selectors_for_display_name(self, display_name: str) -> List[str]:
        """The tappable row of ONE named person in a follow list.

        Addressed by display name and not by handle on purpose: this is what the sync uses to
        reach the rows the FOLLOWING list did not name, precisely because their handle is not on
        screen. The name is enough to tap the right row here and now -- it is not enough to
        RECORD anyone, which is why the handle is then read from the profile that opens.

        The name node is not clickable; the row is its nearest clickable ancestor, the same
        climb the post grid and the search results use.
        """
        escaped = str(display_name or "").replace('"', "")
        return [
            f'//*[contains(@resource-id, ":id/txt_user_name")][@text="{escaped}"]'
            '/ancestor::*[@clickable="true"][1]',
        ]


FOLLOWERS_SELECTORS = FollowersSelectors()
