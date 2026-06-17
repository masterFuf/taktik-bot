"""Sélecteurs UI pour la boîte de réception TikTok (Messages, notifications, demandes).

i18n (modèle overlay) : les sélecteurs langue-neutres (resource-id / classe / position)
vivent ici comme champs ; les fragments dépendant de la langue (`@text` / `@content-desc`)
vivent dans `ui/selectors/locales/<lang>.py` et sont injectés via `L("inbox.<champ>")` selon
la locale active (cf. `ui/language.detect_and_optimize`). Les champs langue-dépendants sont
donc exposés en `@property` = base neutre (resource-id) + fragments de la locale active. NE
JAMAIS hardcoder un texte FR/EN dans un workflow/action : passer par ces properties.

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

from ..locales import L


@dataclass
class InboxSelectors:
    """Sélecteurs pour la boîte de réception et messages TikTok."""

    # === Header Inbox ===
    _add_people_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ehp")]',
    ])

    @property
    def add_people_button(self) -> List[str]:
        return self._add_people_button_base + L("inbox.add_people_button")

    @property
    def inbox_title(self) -> List[str]:
        # NOTE: do NOT use '//*[@text="Inbox"]' — it matches the nav tab label on all pages
        return L("inbox.inbox_title")

    _activity_status_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/jlc")]',
    ])

    @property
    def activity_status(self) -> List[str]:
        return self._activity_status_base + L("inbox.activity_status")

    _search_inbox_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/j6u")]',
    ])

    @property
    def search_inbox_button(self) -> List[str]:
        return self._search_inbox_button_base + L("inbox.search_inbox_button")

    # === Liste des messages ===
    message_list: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/jla")]',
        '//androidx.recyclerview.widget.RecyclerView',
    ])

    # === Sections de notification (titre partagé b8h -> texte requis pour distinguer) ===
    section_title: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/b8h")]',
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
    _follow_back_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/rdh")]',
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
    _see_all_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/y6h")]',
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
    _message_requests_page_title_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/nmh")]',
    ])

    # === Demande de messages OUVERTE : accepter / refuser ===
    _accept_request_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/c6b")]',
    ])
    _decline_request_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/c8q")]',
    ])

    # ------------------------------------------------------------------
    # Properties langue-aware (base neutre + fragments localisés via L())
    # ------------------------------------------------------------------

    @property
    def new_followers_section(self) -> List[str]:
        return L("inbox.new_followers_section")

    @property
    def activity_section(self) -> List[str]:
        return L("inbox.activity_section")

    @property
    def system_notifications_section(self) -> List[str]:
        return L("inbox.system_notifications_section")

    @property
    def message_requests_section(self) -> List[str]:
        return L("inbox.message_requests_section")

    @property
    def suggested_accounts_section(self) -> List[str]:
        return L("inbox.suggested_accounts_section")

    @property
    def seen_marker(self) -> List[str]:
        return L("inbox.seen_marker")

    @property
    def follow_back_button(self) -> List[str]:
        return self._follow_back_button_base + L("inbox.follow_back_button")

    @property
    def see_all_button(self) -> List[str]:
        return self._see_all_base + L("inbox.see_all_button")

    @property
    def message_requests_page_title(self) -> List[str]:
        return self._message_requests_page_title_base + L("inbox.message_requests_page_title")

    @property
    def accept_request_button(self) -> List[str]:
        return self._accept_request_button_base + L("inbox.accept_request_button")

    @property
    def decline_request_button(self) -> List[str]:
        return self._decline_request_button_base + L("inbox.decline_request_button")

    def section_title_by_text(self, title: str) -> str:
        """Build the notification section title selector for a visible title.

        Préférer les properties langue-aware (new_followers_section, etc.) ; ce helper reste
        pour un titre déjà résolu dans la bonne langue.
        """
        return f'{self.section_title[0]}[@text="{title}"]'

    @property
    def we_sent_last_markers(self) -> List[str]:
        """Préfixes de l'aperçu (l35) indiquant que NOUS avons parlé en dernier → conversation
        considérée comme répondue de notre côté (détection « non-répondu », phase 2).

        Combiné FR+EN volontairement (property, donc non filtré par detect_and_optimize) : robuste
        quelle que soit la langue détectée. Capturé sur device : « Envoyé il y a 5 j », « Vu ».
        """
        return ['Envoyé', 'Sent', 'Vu', 'Seen']

    @property
    def activity_title_markers(self) -> List[str]:
        """Sous-chaînes (minuscules) du titre `b8h` de la section Activité (FR+EN, phase 4)."""
        return ['activité', 'activity']

    @property
    def system_title_markers(self) -> List[str]:
        """Sous-chaînes (minuscules) du titre `b8h` des Notifications système (FR+EN, phase 4)."""
        return ['système', 'system']

    @property
    def new_followers_title_markers(self) -> List[str]:
        """Sous-chaînes (minuscules) du titre `b8h` des Nouveaux followers (FR+EN) — exclu de la
        phase 4 (a sa propre phase 1)."""
        return ['nouveaux followers', 'nouveaux abonnés', 'new followers']

    @property
    def message_requests_row_markers(self) -> List[str]:
        """Sous-chaînes (minuscules) identifiant la ligne « Demandes de messages » dans la liste
        des conversations (réutilise l'item t5a/z05) — à exclure des conversations (relève de la
        phase 3). Capturé : z05="Demandes de messages" / l35="Tu as reçu N demandes"."""
        return ['demande', 'request']

    def conversation_username_by_text(self, name: str) -> str:
        """Build the conversation username selector for an exact visible name."""
        return f'{self.conversation_username[0]}[@text="{name}"]'

    def new_followers_username_by_text(self, name: str) -> str:
        """Build the new-follower username selector for a visible name (page dédiée).

        `contains` (pas `=`) car TikTok entoure le username de marques bidi invisibles
        (LRM/FSI/PDI : ‎⁨…⁩) — un match exact échouerait ; `name` doit être
        nettoyé de ces marques (cf. DMActions._clean_username).
        """
        return f'//*[contains(@resource-id, ":id/o0f")][contains(@text, "{name}")]'

    def message_request_by_username(self, name: str) -> str:
        """Build the message-request item (t5a) selector for a visible username (page demandes).

        `contains` car le username (z05) est entouré de marques bidi invisibles (cf.
        DMActions._clean_username) ; on remonte à l'item t5a cliquable contenant ce username.
        """
        return (
            '//*[contains(@resource-id, ":id/t5a")]'
            f'[.//*[contains(@resource-id, ":id/z05")][contains(@text, "{name}")]]'
        )

    def follow_back_for_username(self, name: str) -> str:
        """Build the 'Suivre en retour' button scoped to the new-follower item of `name`.

        Sélecteur dynamique (composé des resource-ids centralisés o0v/o0f/rdh) : le bouton rdh
        de l'item (o0v) dont le username (o0f) contient `name`. `contains` car le texte o0f est
        entouré de marques bidi invisibles (‎⁨…⁩) — `name` doit être nettoyé de
        ces marques au préalable (DMActions._clean_username). Évite de taper le mauvais bouton.
        """
        return (
            '//*[contains(@resource-id, ":id/o0v")]'
            f'[.//*[contains(@resource-id, ":id/o0f")][contains(@text, "{name}")]]'
            '//*[contains(@resource-id, ":id/rdh")]'
        )


INBOX_SELECTORS = InboxSelectors()
