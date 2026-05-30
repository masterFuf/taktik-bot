from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

@dataclass
class NotificationSelectors:
    """Sélecteurs pour le workflow notifications/activité."""
    
    # === Onglet activité ===
    activity_tab: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Activité")]',
        '//*[contains(@content-desc, "Activity")]',
        '//*[contains(@content-desc, "Notifications")]'
    ])
    
    # === Éléments de notification ===
    notification_item: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_news_text"]',
        '//*[@resource-id="com.instagram.android:id/row_news_container"]',
        '//android.widget.LinearLayout[contains(@resource-id, "news")]'
    ])
    
    # === Username dans une notification ===
    notification_username: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_news_text"]//android.widget.TextView[1]',
        '//android.widget.TextView[contains(@text, "@")]'
    ])
    
    # === Texte d'action de notification ===
    notification_action_text: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_news_text"]',
        '//android.widget.TextView[contains(@text, "liked") or contains(@text, "aimé")]',
        '//android.widget.TextView[contains(@text, "started following") or contains(@text, "a commencé")]',
        '//android.widget.TextView[contains(@text, "commented") or contains(@text, "commenté")]'
    ])
    
    # === Section demandes d'abonnement ===
    follow_requests_section: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Follow requests")]',
        '//*[contains(@text, "Demandes d\'abonnement")]'
    ])
    
    # === Détection écran activité ===
    activity_screen_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Activité")]',
        '//*[contains(@text, "Activity")]',
        '//*[contains(@resource-id, "news")]',
        '//*[contains(@resource-id, "activity")]'
    ])

NOTIFICATION_SELECTORS = NotificationSelectors()
