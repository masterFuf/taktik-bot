"""Sélecteurs UI pour la boîte de réception TikTok."""

from typing import List
from dataclasses import dataclass, field


@dataclass
class InboxSelectors:
    """Sélecteurs pour la boîte de réception et messages TikTok.
    
    Basé sur UI dump: ui_dump_20260107_210126.xml (Inbox page)
    Resource-IDs identifiés:
    - ehp: Add people button
    - j6u: Search button (inbox)
    - jlc: Activity status
    - jla: RecyclerView des messages
    - b8h: Section titles (New followers, Activity, System notifications)
    - t5a: Conversation item container
    - z05: Username in conversation
    - l35: Last message text
    - l3a: Timestamp
    - fa7: Unread badge container
    """
    
    # === Header Inbox ===
    add_people_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ehp")]',
        '//android.widget.ImageView[@content-desc="Add people"]',
    ])
    
    inbox_title: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/title")][@text="Inbox"]',
        # NOTE: do NOT use '//*[@text="Inbox"]' — it matches the nav tab label on all pages
    ])
    
    activity_status: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/jlc")]',
        '//*[contains(@content-desc, "Activity status")]',
    ])
    
    search_inbox_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/j6u")]',
        '//android.widget.ImageView[@content-desc="Search"]',
    ])
    
    # === Liste des messages ===
    message_list: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/jla")]',
        '//androidx.recyclerview.widget.RecyclerView',
    ])
    
    # === Sections de notification ===
    section_title: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/b8h")]',
    ])
    
    new_followers_section: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/b8h")][@text="New followers"]',
        '//*[@text="New followers"]',
    ])
    
    activity_section: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/b8h")][@text="Activity"]',
        '//*[@text="Activity"]',
    ])
    
    system_notifications_section: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/b8h")][@text="System notifications"]',
        '//*[@text="System notifications"]',
    ])
    
    # === Conversations ===
    conversation_item: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/t5a")]',
    ])
    
    conversation_avatar: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/b5h")]',
    ])
    
    conversation_username: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/z05")]',
    ])
    
    conversation_last_message: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/l35")]',
    ])
    
    conversation_timestamp: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/l3a")]',
    ])
    
    unread_badge: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/fa7")]',
        '//*[contains(@resource-id, ":id/lnb")]',
    ])
    
    # === Stories row ===
    stories_row: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/tsb")]',
    ])
    
    story_username: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/tsi")]',
        '//*[contains(@resource-id, ":id/jmw")]',
    ])
    
    # === Notification sections (to skip) ===
    notification_item: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/s28")]',
    ])
    
    notification_subtitle: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ln_")]',
    ])
    
    # === Group chat indicators ===
    group_member_count: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ujj")]',
    ])


INBOX_SELECTORS = InboxSelectors()
