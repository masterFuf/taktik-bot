"""Sélecteurs UI pour la recherche et découverte TikTok."""

from typing import List
from dataclasses import dataclass, field


@dataclass
class SearchSelectors:
    """Sélecteurs pour la recherche et découverte TikTok.
    
    Basé sur UI dumps:
    - ui_dump_20260111_121059.xml (For You page with search icon)
    - ui_dump_20260111_121110.xml (Search input page)
    - ui_dump_20260111_121127.xml (Search results page)
    
    Resource-IDs identifiés:
    - giv: Search input field (EditText)
    - y61: Search button (to submit search)
    - b9c: Back button (in search page)
    - c87: Clear search field button
    - ksc: Search icon in input field
    - spd: More button (3 dots)
    """
    
    # === Search icon on For You page (header) ===
    search_icon: List[str] = field(default_factory=lambda: [
        '//android.widget.ImageView[@content-desc="Search"]',
        '//*[@content-desc="Search"]',
        '//*[contains(@content-desc, "Rechercher")]',
    ])
    
    # === Search input field ===
    search_input: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/giv"]',
        '//android.widget.EditText[@resource-id="com.zhiliaoapp.musically:id/giv"]',
        '//android.widget.EditText[contains(@hint, "Search")]',
        '//android.widget.EditText[contains(@content-desc, "Search")]',
    ])
    
    # === Search submit button ===
    search_submit_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/y61"][@text="Search"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/y61"]',
        '//android.widget.Button[@text="Search"]',
        '//android.widget.Button[@text="Rechercher"]',
    ])
    
    # === Back button in search page ===
    search_back_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/b9c"]',
        '//android.widget.ImageView[@resource-id="com.zhiliaoapp.musically:id/b9c"]',
    ])
    
    # === Clear search field button ===
    clear_search_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/c87"]',
        '//android.widget.ImageView[@content-desc="Clear search field"]',
    ])
    
    # === More button (3 dots) ===
    more_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/spd"]',
        '//android.widget.ImageView[@content-desc="More"]',
    ])
    
    # Legacy selectors for compatibility
    search_bar: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/giv"]',
        '//android.widget.EditText[contains(@content-desc, "Search")]',
        '//android.widget.EditText[contains(@content-desc, "Rechercher")]',
    ])
    
    search_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/y61"]',
        '//android.widget.Button[contains(@content-desc, "Search")]',
        '//android.widget.Button[contains(@content-desc, "Rechercher")]',
    ])
    
    # === Filtres de recherche (tabs on results page) ===
    top_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Top"]',
    ])
    
    users_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Users"]',
        '//android.widget.TextView[@text="Utilisateurs"]',
    ])
    
    videos_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Videos"]',
        '//android.widget.TextView[@text="Vidéos"]',
    ])
    
    photos_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Photos"]',
    ])
    
    shop_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Shop"]',
        '//android.widget.TextView[@text="Boutique"]',
    ])
    
    sounds_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Sounds"]',
        '//android.widget.TextView[@text="Sons"]',
    ])
    
    hashtags_tab: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Hashtags"]',
    ])
    
    # === Search suggestions (trending) ===
    suggestion_item: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Trending")]',
        '//android.widget.TextView[contains(@text, "Trending")]',
    ])
    
    # === Search results ===
    # User result item container
    user_result_container: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/sh2"]',
        '//android.widget.RelativeLayout[@resource-id="com.zhiliaoapp.musically:id/sh2"]',
    ])
    
    # Username in search results
    user_result_username: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/ye2"]',
        '//android.widget.TextView[@resource-id="com.zhiliaoapp.musically:id/ye2"]',
    ])
    
    # User bio in search results
    user_result_bio: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/x8i"]',
    ])
    
    # User followers count in search results
    user_result_followers: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/xf0"]',
    ])
    
    # Follow button in search results
    user_result_follow_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/rdh"][@text="Follow"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/rdh"]',
        '//android.widget.Button[@text="Follow"]',
        '//android.widget.Button[@text="Following"]',
    ])
    
    # Video thumbnail in search results
    video_thumbnail: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/cover"]',
        '//android.widget.ImageView[@resource-id="com.zhiliaoapp.musically:id/cover"]',
    ])
    
    # Video container in search results (clickable)
    video_result_container: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/sq1"]',
        '//android.widget.FrameLayout[@resource-id="com.zhiliaoapp.musically:id/sq1"]',
    ])
    
    # View all button
    view_all_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/sm6"][@text="View all"]',
        '//android.widget.TextView[@text="View all"]',
    ])
    
    # First search result (generic fallback)
    first_search_result: List[str] = field(default_factory=lambda: [
        '(//androidx.recyclerview.widget.RecyclerView//android.view.ViewGroup)[1]',
    ])


SEARCH_SELECTORS = SearchSelectors()
