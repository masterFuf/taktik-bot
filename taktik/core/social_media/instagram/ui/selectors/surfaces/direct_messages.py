from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from taktik.core.social_media.instagram.ui.selectors.locales import L

@dataclass
class DirectMessageSelectors:
    """Selectors for direct messages."""
    
    # === Navigation to DM ===
    # DM button in the tab bar (from the profile or the feed)
    direct_tab_resource_id: str = "com.instagram.android:id/direct_tab"
    direct_tab: str = '//*[@resource-id="com.instagram.android:id/direct_tab"]'
    _direct_tab_content_desc_base: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Message"]',
        '//*[@content-desc="Direct"]',
        '//*[@content-desc="Messages"]',
        '//*[@content-desc="Messenger"]'
    ])

    @property
    def direct_tab_content_desc(self) -> List[str]:
        return self._direct_tab_content_desc_base + L("direct_message.direct_tab_content_desc")

    _direct_tab_content_descriptions_base: List[str] = field(default_factory=lambda: [
        "Direct",
        "Messages",
    ])

    @property
    def direct_tab_content_descriptions(self) -> List[str]:
        return self._direct_tab_content_descriptions_base + L("direct_message.direct_tab_content_descriptions")
    dm_inbox_button_descriptions: List[str] = field(default_factory=lambda: [
        "Message",
        "Messages",
        "Direct",
        "Messenger",
    ])
    _dm_inbox_description_contains_base: List[str] = field(default_factory=lambda: [
        "Message",
        "Messenger",
        "Inbox",
        "Boîte de réception",
    ])

    @property
    def dm_inbox_description_contains(self) -> List[str]:
        return self._dm_inbox_description_contains_base + L("direct_message.dm_inbox_description_contains")
    action_bar_inbox_button_resource_id: str = "com.instagram.android:id/action_bar_inbox_button"

    # The DM entry found by its description, and only inside the tab bar: a conversation's voice
    # button (« Message vocal, appuyez longuement pour enregistrer », 447, Pixel 6a, 2026-10-24),
    # the status bar's « Notification Messages : » icon (410, Pixel 6 Pro) and a profile's
    # « Envoyer un message » button hold the same words, and were tapped for it.
    tab_bar: str = '//*[@resource-id="com.instagram.android:id/tab_bar"]'

    @property
    def direct_tab_by_description(self) -> List[str]:
        exact = [f'{self.tab_bar}//*[@content-desc="{label}"]'
                 for label in self.dm_inbox_button_descriptions + self.direct_tab_content_descriptions]
        written = [f'{self.tab_bar}{xpath}' for xpath in self.direct_tab_content_desc if xpath.startswith("//")]
        contained = [f'{self.tab_bar}//*[contains(@content-desc, "{label}")]'
                     for label in self.dm_inbox_description_contains]
        return list(dict.fromkeys(exact + written + contained))
    
    # Unread badge on the DM tab
    dm_notification_badge: str = '//*[@resource-id="com.instagram.android:id/direct_tab"]//*[@resource-id="com.instagram.android:id/notification"]'
    
    # === Inbox (conversation list) ===
    inbox_thread_list_resource_id: str = "com.instagram.android:id/inbox_refreshable_thread_list_recyclerview"
    inbox_thread_list: str = '//*[@resource-id="com.instagram.android:id/inbox_refreshable_thread_list_recyclerview"]'
    # What only the DM inbox shows, either one proving it: its own action bar and its thread list
    # (410: ig410_en_dm_inbox.xml, and ig410_fr_dm_inbox_pills.xml on a Pixel 6 Pro, Android 17,
    # 2026-10-24). The thread list also stands on the message-requests screen.
    inbox_screen_markers: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/direct_inbox_action_bar"]',
        '//*[@resource-id="com.instagram.android:id/inbox_refreshable_thread_list_recyclerview"]',
    ])
    inbox_header_text_resource_id: str = "com.instagram.android:id/header_text"
    # The older header entry to the message requests ("Requests" / "Demandes" button).
    inbox_header_action_button_resource_id: str = "com.instagram.android:id/header_action_button"
    inbox_header_action_button: str = '//*[@resource-id="com.instagram.android:id/header_action_button"]'

    # The pills of an inbox laid out with pills (the layout is served per account, same 410 APK:
    # Tout / Principal / Général / Invitations, ig410_fr_dm_inbox_pills.xml; All / Primary /
    # General / Requests, ig410_en_dm_inbox.xml): a clickable pill holding an
    # `inbox_header_pill_text`, its label at the start of its content-desc, the labels in the
    # locales. The one on display is `selected`.
    _header_pill_template: str = (
        '//*[@clickable="true"][starts-with(@content-desc, "{label}")]'
        '[.//*[@resource-id="com.instagram.android:id/inbox_header_pill_text"]]'
    )

    @property
    def requests_pill(self) -> List[str]:
        return [self._header_pill_template.format(label=label)
                for label in L("direct_message.requests_pill_labels")]

    @property
    def requests_pill_selected(self) -> List[str]:
        """The requests pill once chosen: a pill shows it is the one on display by `selected`
        (the "Tout" / "All" pill of both inbox captures)."""
        return [f'{xpath}[@selected="true"]' for xpath in self.requests_pill]

    @property
    def primary_pill(self) -> List[str]:
        """The pill of the main conversations (« Principal », « Primary »)."""
        return [self._header_pill_template.format(label=label)
                for label in L("direct_message.primary_pill_labels")]

    @property
    def primary_pill_selected(self) -> List[str]:
        return [f'{xpath}[@selected="true"]' for xpath in self.primary_pill]
    inbox_header_messages_text: str = "Messages"
    inbox_header_requests_text: str = "Requests"
    # Title of the message-requests sub-screen (action bar). Used to confirm we left the
    # primary inbox (the thread-list recyclerview exists on BOTH screens). Case-robust
    # substrings cover EN "Message requests", FR "Demandes de messages" / "Invitations".
    action_bar_title_resource_id: str = "com.instagram.android:id/action_bar_title"
    requests_title_fragments: List[str] = field(default_factory=lambda: ["equest", "emande", "nvitation"])
    _inbox_top_visible_texts_base: List[str] = field(default_factory=lambda: [
        "Messages",
        "Requests",
        "Demandes",
        "Your note",
        "Votre note",
        "Map",
        "Carte",
    ])

    @property
    def inbox_top_visible_texts(self) -> List[str]:
        return self._inbox_top_visible_texts_base + L("direct_message.inbox_top_visible_texts")

    _inbox_recommendation_texts_base: List[str] = field(default_factory=lambda: [
        "Accounts to follow",
        "See all",
        "Comptes à suivre",
        "Voir tout",
    ])

    @property
    def inbox_recommendation_texts(self) -> List[str]:
        return self._inbox_recommendation_texts_base + L("direct_message.inbox_recommendation_texts")

    @property
    def presence_prefixes(self) -> List[str]:
        """Bare LABELS that open a thread row when the contact is online, instead of the
        username. Used to reject a presence status read as a conversation name."""
        return L("direct_message.presence_prefixes")
    text_view_class_name: str = "android.widget.TextView"
    image_view_class_name: str = "android.widget.ImageView"
    bottom_tab_resource_ids: List[str] = field(default_factory=lambda: [
        "com.instagram.android:id/feed_tab",
        "com.instagram.android:id/search_tab",
        "com.instagram.android:id/clips_tab",
        "com.instagram.android:id/profile_tab",
    ])
    
    # Container of one conversation in the list
    thread_container_resource_id: str = "com.instagram.android:id/row_inbox_container"
    thread_container: str = '//*[@resource-id="com.instagram.android:id/row_inbox_container"]'
    
    # Elements of one conversation
    thread_username_resource_id: str = 'com.instagram.android:id/row_inbox_username'
    thread_username: str = '//*[@resource-id="com.instagram.android:id/row_inbox_username"]'
    thread_digest: str = '//*[@resource-id="com.instagram.android:id/row_inbox_digest"]'
    thread_timestamp: str = '//*[@resource-id="com.instagram.android:id/row_inbox_timestamp"]'
    thread_avatar: str = '//*[@resource-id="com.instagram.android:id/avatar_container"]'
    
    # Indicateur de message non lu (point bleu)
    unread_indicator: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "non lu")]',
        '//*[contains(@content-desc, "unread")]'
    ])
    # The same words, read in a thread row's own content-desc (lowercased). No reader since the
    # CLI auto-reply went; kept for an unread-thread scan in the DM inbox runtime.
    unread_thread_desc_fragments: List[str] = field(default_factory=lambda: ["non lu", "unread"])

    # Prefixes IG puts before an inbox row preview when the LAST message is OURS
    # (content-desc: "username, Sent 49m ago" / "username, Envoye il y a 49 min").
    # Used to sort out "already answered" without opening the thread. EN+FR base;
    _outgoing_digest_prefixes_base: List[str] = field(default_factory=lambda: ["Sent", "Envoyé"])

    @property
    def outgoing_digest_prefixes(self) -> List[str]:
        return self._outgoing_digest_prefixes_base + L("direct_message.outgoing_digest_prefixes")
    
    # === Barre de recherche DM ===
    search_bar: str = '//*[@resource-id="com.instagram.android:id/search_row"]'
    search_edit_text: str = '//*[@resource-id="com.instagram.android:id/search_edit_text"]'
    search_glyph: str = '//*[@resource-id="com.instagram.android:id/search_bar_glyph"]'
    
    # === Filtres de conversation ===
    filter_principal: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Principal")]',
        '//*[contains(@text, "Primary")]'
    ])
    primary_tab_text_contains: List[str] = field(default_factory=lambda: [
        "Primary",
    ])
    filter_demandes: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Demandes")]',
        '//*[contains(@text, "Requests")]'
    ])
    filter_general: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Général")]',
        '//*[contains(@text, "General")]'
    ])
    
    # === Inbox actions ===
    _new_message_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Nouveau message")]',
        '//*[contains(@content-desc, "New message")]',
        '//*[contains(@content-desc, "New Message")]',
        '//*[contains(@content-desc, "Compose")]'
    ])

    @property
    def new_message_button(self) -> List[str]:
        return self._new_message_button_base + L("direct_message.new_message_button")

    # === New message: the recipient picker the inbox's "Nouveau message" button opens ===
    # Instagram 447, Pixel 6a, 2026-10-24 (captures r16 of the phone session): action bar
    # `direct_recipient_picker_action_bar` titled "Nouveau message", a "À :" field whose
    # `search_edit_text` takes the handle, then `recipients_list` rows. The results come 4 to 7 s
    # after the typing, under an invitation row ("Vous cherchez quelqu'un ?", an "Inviter" button
    # never to tap), whose name is no handle. Not captured in 410 yet: same ids expected
    # (`search_edit_text` is the 410 inbox's, `row_user_primary_name` the 410 likers sheet's).
    new_message_screen: str = '//*[@resource-id="com.instagram.android:id/direct_recipient_picker_action_bar"]'
    new_message_search_field: str = (
        '//*[@resource-id="com.instagram.android:id/recipients_container"]'
        '//*[@resource-id="com.instagram.android:id/search_edit_text"]'
    )

    def new_message_recipient_row(self, username: str) -> str:
        """The picker's row of exactly this handle (never the invitation row above it).

        The handle is the row's first line for an account without a display name, its second line
        under the display name otherwise (447, Pixel 6a, 2026-10-24: « Prénom Nom » then the
        handle, under « Plus sur Instagram »). Equality, never a prefix: another account's handle
        may start the same way."""
        return (
            '//*[@resource-id="com.instagram.android:id/recipients_list"]'
            '//*[@resource-id="com.instagram.android:id/user_row_background"]'
            f'[.//*[@resource-id="com.instagram.android:id/row_user_primary_name"][@text="{username}"]'
            f' or .//*[@resource-id="com.instagram.android:id/row_user_secondary_name"][@text="{username}"]]'
        )
    
    select_multiple_button: str = '//*[@content-desc="Sélectionner plusieurs messages"]'
    
    # === Navigation inside a conversation ===
    conversation_back_button_resource_id: str = 'com.instagram.android:id/header_left_button'
    @property
    def conversation_back_descriptions(self) -> List[str]:
        return L("direct_message.conversation_back_descriptions")

    @property
    def conversation_back_description_contains(self) -> List[str]:
        return L("direct_message.conversation_back_description_contains")
    conversation_header_title_resource_id: str = "com.instagram.android:id/header_title"
    conversation_header_subtitle_resource_id: str = "com.instagram.android:id/header_subtitle"
    conversation_group_member_pattern: str = r"\d+\.?\d*k?\s*(membres|members)"
    conversation_group_member_keywords: List[str] = field(default_factory=lambda: [
        "membres",
        "members",
    ])
    
    # === Inside a conversation ===
    edit_text_class_name: str = "android.widget.EditText"
    composer_edittext_resource_id: str = "com.instagram.android:id/row_thread_composer_edittext"
    message_input_resource_ids: List[str] = field(default_factory=lambda: [
        "com.instagram.android:id/row_thread_composer_edittext",
        "com.instagram.android:id/message_content",
    ])
    message_input_text_contains: List[str] = field(default_factory=lambda: [
        "Message",
    ])
    message_input: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_thread_composer_edittext"]',
        '//android.widget.EditText[contains(@hint, "Message")]',
        '//android.widget.EditText[contains(@text, "Message")]',
        '//android.widget.EditText[@clickable="true"]'
    ])
    
    _send_button_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_thread_composer_button_send"]',
    ])

    @property
    def send_button(self) -> List[str]:
        return self._send_button_base + L("direct_message.send_button")
    send_button_resource_ids: List[str] = field(default_factory=lambda: [
        "com.instagram.android:id/row_thread_composer_send_button_container",
        "com.instagram.android:id/row_thread_composer_send_button",
        "com.instagram.android:id/send_button",
    ])
    @property
    def send_button_descriptions(self) -> List[str]:
        return L("direct_message.send_button_descriptions")

    @property
    def send_button_content_descriptions(self) -> List[str]:
        return L("direct_message.send_button_content_descriptions")
    
    # Message list inside a conversation
    message_list: str = '//*[@resource-id="com.instagram.android:id/message_list"]'
    message_item: str = '//*[@resource-id="com.instagram.android:id/direct_text_message_text_view"]'
    message_item_resource_id: str = 'com.instagram.android:id/direct_text_message_text_view'
    # A bubble of ours waiting to be sent (no network, Pixel 6 Pro, 410, 2026-10-24): an icon at its
    # side in its `message_content`, described « Envoi… » / « Sending… » (locales); gone once the
    # bubble is sent.
    message_container_resource_id: str = 'com.instagram.android:id/message_content'
    message_status_icon_resource_id: str = 'com.instagram.android:id/action_icon'

    @property
    def pending_send_descriptions(self) -> List[str]:
        return L("direct_message.pending_send_descriptions")

    # --- Compose thread (IG 442+): a message text has NO resource-id any more ---
    # `direct_text_message_text_view` disappeared when the thread moved to Jetpack Compose,
    # so the bubble text is a BARE TextView inside `message_list`. Everything that is NOT a
    # message in that list keeps an id (the context header `thread_context_item_*`, the
    # partner name, the CTA buttons), which makes "no id" the usable signature of content.
    #
    # `@resource-id=""` and not `not(@resource-id)`: uiautomator2 always emits the attribute,
    # empty when absent — the `not()` form matches nothing (verified live: 0 vs 3).
    #
    # Three kinds of node come back and the reader tells them apart by GEOMETRY, which is
    # language-independent: the date separator is full-width, a reaction chip is tiny, a
    # message is neither. Only the leftover UI hints need the localized list below.
    message_list_bare_text: str = (
        '//*[@resource-id="com.instagram.android:id/message_list"]'
        '//android.widget.TextView[@resource-id=""]'
    )

    # A reaction chip (the ❤ dropped on a bubble) is a tiny bare TextView sitting just under
    # its message. Measured on a real 442 thread: 47x47 px on a 1080 screen, ~4%.
    reaction_max_width_ratio: float = 0.12
    # Vertical gap between a bubble's bottom and its reaction chip (31 px measured).
    reaction_max_gap_px: int = 120

    @property
    def message_system_text_fragments(self) -> List[str]:
        """Lowercased fragments of the UI hints IG renders INSIDE the message list.

        Geometry cannot separate these from a real bubble (a "Add to your story" CTA has the
        shape of a short message), so they are matched by text — the one place a localized
        list is unavoidable. Kept as fragments, matched case-insensitively.
        """
        return L("direct_message.message_system_text_fragments")
    reel_share_item_resource_id: str = "com.instagram.android:id/reel_share_item_view"
    reel_author_title_resource_id: str = "com.instagram.android:id/title_text"
    invite_sent_text_contains: List[str] = field(default_factory=lambda: [
        "Invite sent",
        "invite is accepted",
    ])

    @property
    def invite_sent_indicators(self) -> List[str]:
        """The conversation of a message request already sent: one of its texts on screen."""
        return [f'//*[contains(@text, "{text}")]' for text in self.invite_sent_text_contains]
    
    # === Notes (circular stories at the top of the DM screen) ===
    notes_recycler: str = '//*[@resource-id="com.instagram.android:id/cf_hub_recycler_view"]'
    note_root: str = '//*[@resource-id="com.instagram.android:id/pog_root_view"]'
    note_bubble_text: str = '//*[@resource-id="com.instagram.android:id/pog_bubble_text"]'
    note_name: str = '//*[@resource-id="com.instagram.android:id/pog_name"]'
    add_note_button: str = '//*[@content-desc="Ajouter une note"]'
    
    # === Inbox action bar ===
    inbox_action_bar_resource_id: str = "com.instagram.android:id/action_bar_container"
    inbox_action_bar: str = '//*[@resource-id="com.instagram.android:id/action_bar_container"]'
    inbox_title: str = '//*[@resource-id="com.instagram.android:id/igds_action_bar_title"]'
    # Holds the logged-in account username (the "username v" switcher at the top of the inbox).
    inbox_title_resource_id: str = "com.instagram.android:id/igds_action_bar_title"
    instagram_open_probe_resource_ids: List[str] = field(default_factory=lambda: [
        "com.instagram.android:id/action_bar_container",
        "com.instagram.android:id/tab_bar",
        "com.instagram.android:id/bottom_navigation",
    ])
    
    # === Legacy selectors (compatibilité) ===
    search_recipient: str = '//android.widget.EditText[contains(@text, "Rechercher") or contains(@text, "Search")]'
    thread_list: str = '//*[@resource-id="com.instagram.android:id/inbox_refreshable_thread_list_recyclerview"]'
    thread_item: str = '//*[@resource-id="com.instagram.android:id/row_inbox_container"]'

    @property
    def text_view_class_selector(self) -> Dict[str, str]:
        return {"className": self.text_view_class_name}

    def thread_selector_for_username(self, username: str) -> Dict[str, str]:
        return {"textContains": username}

    def send_button_selector_for_description(self, description: str) -> Dict[str, str]:
        return {"contentDescription": description}

DM_SELECTORS = DirectMessageSelectors()
