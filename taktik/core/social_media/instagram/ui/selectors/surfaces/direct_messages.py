from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from ..locales import L

@dataclass
class DirectMessageSelectors:
    """Sélecteurs pour les messages directs."""
    
    # === Navigation vers DM ===
    # Bouton DM dans la tab bar (depuis le profil ou le feed)
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
    
    # Badge de notification sur l'onglet DM
    dm_notification_badge: str = '//*[@resource-id="com.instagram.android:id/direct_tab"]//*[@resource-id="com.instagram.android:id/notification"]'
    
    # === Inbox (Liste des conversations) ===
    inbox_thread_list_resource_id: str = "com.instagram.android:id/inbox_refreshable_thread_list_recyclerview"
    inbox_thread_list: str = '//*[@resource-id="com.instagram.android:id/inbox_refreshable_thread_list_recyclerview"]'
    inbox_header_text_resource_id: str = "com.instagram.android:id/header_text"
    inbox_header_action_button_resource_id: str = "com.instagram.android:id/header_action_button"
    inbox_header_messages_text: str = "Messages"
    inbox_header_requests_text: str = "Requests"
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
    text_view_class_name: str = "android.widget.TextView"
    image_view_class_name: str = "android.widget.ImageView"
    bottom_tab_resource_ids: List[str] = field(default_factory=lambda: [
        "com.instagram.android:id/feed_tab",
        "com.instagram.android:id/search_tab",
        "com.instagram.android:id/clips_tab",
        "com.instagram.android:id/profile_tab",
    ])
    
    # Conteneur d'une conversation dans la liste
    thread_container_resource_id: str = "com.instagram.android:id/row_inbox_container"
    thread_container: str = '//*[@resource-id="com.instagram.android:id/row_inbox_container"]'
    
    # Éléments d'une conversation
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
    
    # === Actions dans l'inbox ===
    _new_message_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Nouveau message")]',
        '//*[contains(@content-desc, "New message")]',
        '//*[contains(@content-desc, "New Message")]',
        '//*[contains(@content-desc, "Compose")]'
    ])

    @property
    def new_message_button(self) -> List[str]:
        return self._new_message_button_base + L("direct_message.new_message_button")
    
    select_multiple_button: str = '//*[@content-desc="Sélectionner plusieurs messages"]'
    
    # === Navigation dans une conversation ===
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
    
    # === Dans une conversation ===
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
    
    # Liste des messages dans une conversation
    message_list: str = '//*[@resource-id="com.instagram.android:id/message_list"]'
    message_item: str = '//*[@resource-id="com.instagram.android:id/direct_text_message_text_view"]'
    message_item_resource_id: str = 'com.instagram.android:id/direct_text_message_text_view'
    reel_share_item_resource_id: str = "com.instagram.android:id/reel_share_item_view"
    reel_author_title_resource_id: str = "com.instagram.android:id/title_text"
    invite_sent_text_contains: List[str] = field(default_factory=lambda: [
        "Invite sent",
        "invite is accepted",
    ])
    
    # === Notes (Stories circulaires en haut des DM) ===
    notes_recycler: str = '//*[@resource-id="com.instagram.android:id/cf_hub_recycler_view"]'
    note_root: str = '//*[@resource-id="com.instagram.android:id/pog_root_view"]'
    note_bubble_text: str = '//*[@resource-id="com.instagram.android:id/pog_bubble_text"]'
    note_name: str = '//*[@resource-id="com.instagram.android:id/pog_name"]'
    add_note_button: str = '//*[@content-desc="Ajouter une note"]'
    
    # === Action bar dans l'inbox ===
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
    def message_input_class_selector(self) -> Dict[str, str]:
        return {"className": self.edit_text_class_name}

    @property
    def text_view_class_selector(self) -> Dict[str, str]:
        return {"className": self.text_view_class_name}

    def thread_selector_for_username(self, username: str) -> Dict[str, str]:
        return {"textContains": username}

    def account_result_selector_for_username(self, username: str) -> Dict[str, str]:
        return {"textContains": username, "className": self.text_view_class_name}

    def send_button_selector_for_description(self, description: str) -> Dict[str, str]:
        return {"contentDescription": description}

DM_SELECTORS = DirectMessageSelectors()
