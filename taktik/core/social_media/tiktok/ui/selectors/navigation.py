"""Sélecteurs UI pour la navigation principale TikTok."""

from typing import List
from dataclasses import dataclass, field


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
        '//*[@resource-id="com.zhiliaoapp.musically:id/mky"]',
    ])
    
    home_tab: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/mkq"]',
        '//android.widget.FrameLayout[@content-desc="Home"]',
        '//android.widget.FrameLayout[contains(@content-desc, "Accueil")]',
    ])
    
    friends_tab: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/mkp"]',
        '//android.widget.FrameLayout[@content-desc="Friends"]',
        '//android.widget.FrameLayout[contains(@content-desc, "Amis")]',
    ])
    
    create_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/mkn"]',
        '//android.widget.Button[@content-desc="Create"]',
        '//android.widget.Button[contains(@content-desc, "Créer")]',
    ])
    
    inbox_tab: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/mkr"]',
        '//android.widget.FrameLayout[@content-desc="Inbox"]',
        '//android.widget.FrameLayout[contains(@content-desc, "Boîte de réception")]',
        '//*[@content-desc="Inbox"]',
        '//*[contains(@content-desc, "Inbox")]',
        '//*[contains(@content-desc, "Messages")]',
    ])
    
    profile_tab: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/mks"]',
        '//android.widget.FrameLayout[@content-desc="Profile"]',
        '//android.widget.FrameLayout[contains(@content-desc, "Profil")]',
    ])
    
    # === Header Tabs (For You page) ===
    live_tab: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="LIVE"]',
        '//*[@text="LIVE"]',
    ])
    
    explore_tab: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Explore"]',
        '//*[@text="Explore"]',
        '//*[contains(@content-desc, "Explorer")]',
    ])
    
    following_tab: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Following"]',
        '//*[@text="Following"]',
        '//*[contains(@content-desc, "Abonnements")]',
    ])
    
    shop_tab: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Shop"]',
        '//*[@text="Shop"]',
        '//*[contains(@content-desc, "Boutique")]',
    ])
    
    for_you_tab: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="For You"]',
        '//*[@text="For You"]',
        '//*[contains(@content-desc, "Pour toi")]',
    ])
    
    # === Search button (header on For You page) ===
    # Resource-id: irz (from ui_dump_20260111_121059.xml)
    search_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/irz"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/irz"][@content-desc="Search"]',
        '//android.widget.ImageView[@content-desc="Search"]',
        '//*[@content-desc="Search"][@clickable="true"]',
        '//*[contains(@content-desc, "Rechercher")][@clickable="true"]',
    ])
    
    # === Tab selected states (for page detection) ===
    home_tab_selected: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/mkq"][@selected="true"]',
        '//android.widget.FrameLayout[@content-desc="Home"][@selected="true"]',
    ])
    
    inbox_tab_selected: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/mkr"][@selected="true"]',
        '//android.widget.FrameLayout[@content-desc="Inbox"][@selected="true"]',
    ])
    
    # === Back button ===
    back_button: List[str] = field(default_factory=lambda: [
        '//android.widget.ImageButton[@content-desc="Back"]',
        '//android.widget.ImageButton[@content-desc="Retour"]',
        '//android.widget.ImageView[@content-desc="Back"]',
        '//*[@resource-id="com.android.systemui:id/back"]',
    ])


NAVIGATION_SELECTORS = NavigationSelectors()
