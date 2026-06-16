"""Sélecteurs UI pour la boîte de réception TikTok (Messages, notifications, demandes).

i18n : les sections/boutons dépendant de la langue sont déclarés en champs `_xxx_en` /
`_xxx_fr` (+ `_xxx_rids` pour les resource-ids langue-agnostiques) et exposés via une
`@property` qui les combine. `detect_and_optimize()` (ui/language.py) filtre in-place les
champs `_en`/`_fr` de la mauvaise langue ; les properties (non-fields) restent intactes et
combinent ce qui reste. NE JAMAIS hardcoder un texte FR/EN dans un workflow/action : passer
par ces properties.

Resource-IDs (dumps device réel) :
- Inbox : ehp (add people), j6u (search), jlc (activity status), jla (RecyclerView),
  b8h (titres de section : partagé New followers / Activity / System notifications),
  t5a (item conversation), b5h (avatar), z05 (username), l35 (dernier message),
  l3a (timestamp), fa7/lnb/ydj (badge non-lu), s28 (item de notif), ln_ (sous-titre notif).
- Comptes suggérés / nouveaux followers : rdh (Suivre en retour), ew3 (supprimer suggestion).
- Page Nouveaux followers (dump 145912/145920) : o0v (item), o0f (username), nzo (texte
  "a commencé à te suivre"), nzy (avatar), y6h (Tout voir).
- Page Demandes de messages (dump 145940) : nmh (titre), t5a (item), z05 (username),
  l35 (aperçu), l3a (date), ydj (badge), nmt (filtre/plus).
- Demande OUVERTE (dump 152315) : c6b (Accepter), c8q (Supprimer / refuser).
"""

from typing import List
from dataclasses import dataclass, field


@dataclass
class InboxSelectors:
    """Sélecteurs pour la boîte de réception et messages TikTok."""

    # === Header Inbox ===
    add_people_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ehp")]',
        '//android.widget.ImageView[@content-desc="Add people"]',
        '//android.widget.ImageView[@content-desc="Ajouter des personnes"]',
    ])

    inbox_title: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/title")][@text="Inbox"]',
        # NOTE: do NOT use '//*[@text="Inbox"]' — it matches the nav tab label on all pages
    ])

    activity_status: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/jlc")]',
        '//*[contains(@content-desc, "Activity status")]',
        '//*[contains(@content-desc, "Statut d\'activité")]',
    ])

    search_inbox_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/j6u")]',
        '//android.widget.ImageView[@content-desc="Search"]',
        '//android.widget.ImageView[@content-desc="Rechercher"]',
    ])

    # === Liste des messages ===
    message_list: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/jla")]',
        '//androidx.recyclerview.widget.RecyclerView',
    ])

    # === Sections de notification (titre partagé b8h -> texte requis pour distinguer) ===
    section_title: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/b8h")]',
    ])

    _new_followers_section_en: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/b8h")][@text="New followers"]',
        '//*[@text="New followers"]',
    ])
    _new_followers_section_fr: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/b8h")][@text="Nouveaux followers"]',
        '//*[contains(@resource-id, ":id/b8h")][@text="Nouveaux abonnés"]',
        '//*[@text="Nouveaux followers"]',
        '//*[@text="Nouveaux abonnés"]',
    ])

    _activity_section_en: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/b8h")][@text="Activity"]',
        '//*[@text="Activity"]',
    ])
    _activity_section_fr: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/b8h")][@text="Activité"]',
        '//*[@text="Activité"]',
    ])

    _system_notifications_section_en: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/b8h")][@text="System notifications"]',
        '//*[@text="System notifications"]',
    ])
    _system_notifications_section_fr: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/b8h")][@text="Notifications système"]',
        '//*[@text="Notifications système"]',
    ])

    _message_requests_section_en: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Message requests")]',
    ])
    _message_requests_section_fr: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Demandes de messages")]',
    ])

    _suggested_accounts_section_en: List[str] = field(default_factory=lambda: [
        '//*[@text="Suggested accounts"]',
    ])
    _suggested_accounts_section_fr: List[str] = field(default_factory=lambda: [
        '//*[@text="Comptes suggérés"]',
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
        '//*[contains(@resource-id, ":id/ydj")]',
    ])

    # === "Vu" (dernier message lu par nous, pas de réponse) — détection non-répondu ===
    _seen_marker_en: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/l35")][@text="Seen"]',
        '//*[contains(@resource-id, ":id/l35")][starts-with(@text, "Seen")]',
    ])
    _seen_marker_fr: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/l35")][@text="Vu"]',
        '//*[contains(@resource-id, ":id/l35")][starts-with(@text, "Vu")]',
    ])

    # === Stories row ===
    stories_row: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/tsb")]',
    ])

    story_username: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/tsi")]',
        '//*[contains(@resource-id, ":id/jmw")]',
    ])

    # === Notification sections (items) ===
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

    # === Suivre en retour (comptes suggérés / nouveaux followers) ===
    _follow_back_button_rids: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/rdh")]',
    ])
    _follow_back_button_en: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="Follow back"]',
        '//*[@text="Follow back"]',
    ])
    _follow_back_button_fr: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="Suivre en retour"]',
        '//*[@text="Suivre en retour"]',
    ])

    # === Page Nouveaux followers (dédiée) ===
    new_followers_page_item: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/o0v")]',
    ])
    new_followers_page_username: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/o0f")]',
    ])
    new_followers_page_activity: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/nzo")]',
    ])
    new_followers_page_avatar: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/nzy")]',
    ])
    _see_all_rids: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/y6h")]',
    ])
    _see_all_en: List[str] = field(default_factory=lambda: [
        '//*[@text="View all"]',
    ])
    _see_all_fr: List[str] = field(default_factory=lambda: [
        '//*[@text="Tout voir"]',
    ])

    # === Page Demandes de messages (dédiée) — liste ===
    message_request_item: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/t5a")]',
    ])
    message_request_username: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/z05")]',
    ])
    message_request_preview: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/l35")]',
    ])
    message_request_timestamp: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/l3a")]',
    ])
    message_request_unread_badge: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ydj")]',
    ])
    _message_requests_page_title_rids: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/nmh")]',
    ])
    _message_requests_page_title_en: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/nmh")][contains(@text, "Message requests")]',
    ])
    _message_requests_page_title_fr: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/nmh")][contains(@text, "Demandes de messages")]',
    ])

    # === Demande de messages OUVERTE : accepter / refuser ===
    _accept_request_button_rids: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/c6b")]',
    ])
    _accept_request_button_en: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="Accept"]',
        '//*[@text="Accept"]',
    ])
    _accept_request_button_fr: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="Accepter"]',
        '//*[@text="Accepter"]',
    ])
    _decline_request_button_rids: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/c8q")]',
    ])
    _decline_request_button_en: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="Delete"]',
        '//android.widget.Button[@text="Decline"]',
    ])
    _decline_request_button_fr: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="Supprimer"]',
    ])

    # ------------------------------------------------------------------
    # Properties langue-aware (combinent _rids + _en + _fr filtrés)
    # ------------------------------------------------------------------

    @property
    def new_followers_section(self) -> List[str]:
        return self._new_followers_section_en + self._new_followers_section_fr

    @property
    def activity_section(self) -> List[str]:
        return self._activity_section_en + self._activity_section_fr

    @property
    def system_notifications_section(self) -> List[str]:
        return self._system_notifications_section_en + self._system_notifications_section_fr

    @property
    def message_requests_section(self) -> List[str]:
        return self._message_requests_section_en + self._message_requests_section_fr

    @property
    def suggested_accounts_section(self) -> List[str]:
        return self._suggested_accounts_section_en + self._suggested_accounts_section_fr

    @property
    def seen_marker(self) -> List[str]:
        return self._seen_marker_en + self._seen_marker_fr

    @property
    def follow_back_button(self) -> List[str]:
        return self._follow_back_button_rids + self._follow_back_button_en + self._follow_back_button_fr

    @property
    def see_all_button(self) -> List[str]:
        return self._see_all_rids + self._see_all_en + self._see_all_fr

    @property
    def message_requests_page_title(self) -> List[str]:
        return (
            self._message_requests_page_title_en
            + self._message_requests_page_title_fr
            + self._message_requests_page_title_rids
        )

    @property
    def accept_request_button(self) -> List[str]:
        return self._accept_request_button_rids + self._accept_request_button_en + self._accept_request_button_fr

    @property
    def decline_request_button(self) -> List[str]:
        return self._decline_request_button_rids + self._decline_request_button_en + self._decline_request_button_fr

    def section_title_by_text(self, title: str) -> str:
        """Build the notification section title selector for a visible title.

        Préférer les properties langue-aware (new_followers_section, etc.) ; ce helper reste
        pour un titre déjà résolu dans la bonne langue.
        """
        return f'{self.section_title[0]}[@text="{title}"]'

    def conversation_username_by_text(self, name: str) -> str:
        """Build the conversation username selector for an exact visible name."""
        return f'{self.conversation_username[0]}[@text="{name}"]'


INBOX_SELECTORS = InboxSelectors()
