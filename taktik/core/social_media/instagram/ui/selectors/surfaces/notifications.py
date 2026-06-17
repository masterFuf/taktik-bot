from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from ..locales import L

@dataclass
class NotificationSelectors:
    """Sélecteurs pour le workflow notifications/activité."""

    # === Onglet activité ===
    _activity_tab_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Notifications")]'
    ])

    @property
    def activity_tab(self) -> List[str]:
        return self._activity_tab_base + L("notification.activity_tab")

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
    _notification_action_text_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_news_text"]',
    ])

    @property
    def notification_action_text(self) -> List[str]:
        return self._notification_action_text_base + L("notification.notification_action_text")

    # === Section demandes d'abonnement ===
    @property
    def follow_requests_section(self) -> List[str]:
        return L("notification.follow_requests_section")

    # === Détection écran activité ===
    _activity_screen_indicators_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "news")]',
        '//*[contains(@resource-id, "activity")]',
        '//*[contains(@resource-id, "notification_inbox")]'
    ])

    @property
    def activity_screen_indicators(self) -> List[str]:
        return self._activity_screen_indicators_base + L("notification.activity_screen_indicators")

NOTIFICATION_SELECTORS = NotificationSelectors()
