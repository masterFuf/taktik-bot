"""Sélecteurs UI pour la liste des followers TikTok."""

from typing import List
from dataclasses import dataclass, field


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
        '//android.widget.Button[@clickable="true"][.//android.widget.RelativeLayout[@resource-id="com.zhiliaoapp.musically:id/sh2"]]',
        '//android.widget.Button[@clickable="true"][.//android.widget.TextView[@resource-id="com.zhiliaoapp.musically:id/ye2"]]',
        '//android.widget.Button[@clickable="true"][.//android.widget.Button[@resource-id="com.zhiliaoapp.musically:id/rdh"]]',
    ])
    
    # First user in search results (Users tab)
    first_user_result: List[str] = field(default_factory=lambda: [
        '(//androidx.recyclerview.widget.RecyclerView[@resource-id="com.zhiliaoapp.musically:id/lnp"]//android.widget.Button[@clickable="true"])[1]',
        '(//android.widget.Button[@clickable="true"][.//android.widget.RelativeLayout[@resource-id="com.zhiliaoapp.musically:id/sh2"]])[1]',
        '(//android.widget.Button[@clickable="true"][.//android.widget.TextView[@resource-id="com.zhiliaoapp.musically:id/ye2"]])[1]',
        '(//android.widget.RelativeLayout[@resource-id="com.zhiliaoapp.musically:id/sh2"][@clickable="true"])[1]',
    ])
    
    # === Profile page elements ===
    profile_username: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/qh5"]',
        '//android.widget.Button[@resource-id="com.zhiliaoapp.musically:id/qh5"]',
    ])
    
    # Followers counter (clickable to open followers list)
    followers_counter: List[str] = field(default_factory=lambda: [
        '//android.view.ViewGroup[@clickable="true"][.//android.widget.TextView[@text="Followers"]]',
        '//android.view.ViewGroup[@clickable="true"][.//android.widget.TextView[@resource-id="com.zhiliaoapp.musically:id/qfv"][@text="Followers"]]',
        '//*[.//android.widget.TextView[@text="Followers"]][@clickable="true"]',
    ])
    
    # Following counter
    following_counter: List[str] = field(default_factory=lambda: [
        '//android.widget.LinearLayout[@clickable="true"][.//android.widget.TextView[@text="Following"]]',
        '//*[.//android.widget.TextView[@text="Following"]][@clickable="true"]',
    ])
    
    # Follow button on profile
    profile_follow_button: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@resource-id="com.zhiliaoapp.musically:id/eme"][@text="Follow"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/eme"][@text="Follow"]',
    ])
    
    # === Followers list page ===
    followers_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "Followers")]',
        '//*[contains(@text, "Followers")][@clickable="true"]',
    ])
    
    following_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "Following")][@selected="false"]',
    ])
    
    # RecyclerView containing followers list
    followers_list: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/s6p"]',
        '//androidx.recyclerview.widget.RecyclerView[@resource-id="com.zhiliaoapp.musically:id/s6p"]',
    ])
    
    # Individual follower item (clickable row)
    follower_item: List[str] = field(default_factory=lambda: [
        '//android.widget.LinearLayout[@clickable="true"][.//android.widget.Button[@resource-id="com.zhiliaoapp.musically:id/rdh"]]',
    ])
    
    # Display name in followers list
    follower_display_name: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/yhq"]',
        '//android.widget.TextView[@resource-id="com.zhiliaoapp.musically:id/yhq"]',
    ])
    
    # Username in followers list
    follower_username: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/ygv"]',
        '//android.widget.TextView[@resource-id="com.zhiliaoapp.musically:id/ygv"]',
    ])
    
    # Follow button in followers list
    follower_follow_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/rdh"][@text="Follow"]',
        '//android.widget.Button[@resource-id="com.zhiliaoapp.musically:id/rdh"][@text="Follow"]',
    ])
    
    # Already following button
    follower_following_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/rdh"][@text="Following"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/rdh"][@text="Friends"]',
    ])
    
    # Any follow button (Follow, Following, or Friends)
    follower_any_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/rdh"]',
        '//android.widget.Button[@resource-id="com.zhiliaoapp.musically:id/rdh"]',
    ])
    
    # Private account notice
    private_notice: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/ikr"]',
        '//android.widget.TextView[contains(@text, "can see all followers")]',
    ])
    
    # === Profile page - Video grid ===
    profile_grid: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/gxd"]',
        '//android.widget.GridView[@resource-id="com.zhiliaoapp.musically:id/gxd"]',
    ])
    
    profile_post_item: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/e52"][@clickable="true"]',
        '//android.widget.FrameLayout[@resource-id="com.zhiliaoapp.musically:id/e52"][@clickable="true"]',
    ])
    
    first_post: List[str] = field(default_factory=lambda: [
        '(//*[@resource-id="com.zhiliaoapp.musically:id/e52"][@clickable="true"])[1]',
        '(//android.widget.FrameLayout[@resource-id="com.zhiliaoapp.musically:id/e52"])[1]',
    ])
    
    post_cover: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/cover"]',
    ])
    
    post_view_count: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/xxy"]',
    ])
    
    profile_videos_tab: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Videos"]',
        '//android.widget.RelativeLayout[@content-desc="Videos"]',
    ])
    
    profile_reposted_tab: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Reposted videos"]',
        '//android.widget.RelativeLayout[@content-desc="Reposted videos"]',
    ])
    
    # === Back button (in-app) ===
    back_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/b9b"]',
        '//android.widget.ImageView[@resource-id="com.zhiliaoapp.musically:id/b9b"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/b9c"]',
    ])
    
    # === Followers list page detection ===
    followers_tab_selected: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Followers")][@selected="true"]',
    ])
    
    # === Unfollow-related ===
    following_or_friends_button: List[str] = field(default_factory=lambda: [
        '//*[@text="Following" or @text="Friends"][@clickable="true"]',
    ])
    
    unfollow_confirm_button: List[str] = field(default_factory=lambda: [
        '//*[@text="Unfollow"][@clickable="true"]',
        '//*[contains(@text, "Unfollow")][@clickable="true"]',
    ])
    
    # Following list opener (on profile page)
    following_list_opener: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Following")]',
        '//*[contains(@text, "Following")]',
        '//android.widget.TextView[contains(@text, "Following")]',
    ])


FOLLOWERS_SELECTORS = FollowersSelectors()
