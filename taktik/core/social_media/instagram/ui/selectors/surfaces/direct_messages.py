from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

@dataclass
class DirectMessageSelectors:
    """Sélecteurs pour les messages directs."""
    
    # === Navigation vers DM ===
    # Bouton DM dans la tab bar (depuis le profil ou le feed)
    direct_tab_resource_id: str = "com.instagram.android:id/direct_tab"
    direct_tab: str = '//*[@resource-id="com.instagram.android:id/direct_tab"]'
    direct_tab_content_desc: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Message"]',
        '//*[@content-desc="Envoyer un message"]',
        '//*[@content-desc="Direct"]',
        '//*[@content-desc="Messages"]',
        '//*[@content-desc="Messenger"]'
    ])

    direct_tab_content_descriptions: List[str] = field(default_factory=lambda: [
        "Envoyer un message",
        "Direct",
        "Messages",
    ])
    dm_inbox_button_descriptions: List[str] = field(default_factory=lambda: [
        "Message",
        "Messages",
        "Direct",
        "Messenger",
    ])
    dm_inbox_description_contains: List[str] = field(default_factory=lambda: [
        "Message",
        "Messenger",
        "Inbox",
        "Boîte de réception",
        "Envoyer un message",
    ])
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
    inbox_top_visible_texts: List[str] = field(default_factory=lambda: [
        "Messages",
        "Requests",
        "Demandes",
        "Search or ask Meta AI",
        "Search",
        "Rechercher",
        "Your note",
        "Votre note",
        "Map",
        "Carte",
    ])
    inbox_recommendation_texts: List[str] = field(default_factory=lambda: [
        "Accounts to follow",
        "Suggested for you",
        "See all",
        "Comptes à suivre",
        "Suggestions pour vous",
        "Voir tout",
    ])
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
    new_message_button: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Créer une publicité Envoyer un message"]',
        '//*[contains(@content-desc, "Nouveau message")]',
        '//*[contains(@content-desc, "New message")]',
        '//*[contains(@content-desc, "New Message")]',
        '//*[contains(@content-desc, "Compose")]'
    ])
    
    select_multiple_button: str = '//*[@content-desc="Sélectionner plusieurs messages"]'
    
    # === Navigation dans une conversation ===
    conversation_back_button_resource_id: str = 'com.instagram.android:id/header_left_button'
    conversation_back_descriptions: List[str] = field(default_factory=lambda: [
        "Back",
    ])
    conversation_back_description_contains: List[str] = field(default_factory=lambda: [
        "Retour",
    ])
    
    # === Dans une conversation ===
    edit_text_class_name: str = "android.widget.EditText"
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
    
    send_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_thread_composer_button_send"]',
        '//*[contains(@content-desc, "Envoyer")]',
        '//*[contains(@content-desc, "Send")]',
        '//android.widget.ImageButton[contains(@content-desc, "Envoyer")]',
        '//android.widget.ImageButton[contains(@content-desc, "Send")]'
    ])
    send_button_resource_ids: List[str] = field(default_factory=lambda: [
        "com.instagram.android:id/row_thread_composer_send_button_container",
        "com.instagram.android:id/row_thread_composer_send_button",
        "com.instagram.android:id/send_button",
    ])
    send_button_descriptions: List[str] = field(default_factory=lambda: [
        "Envoyer",
        "Send",
        "Send message",
    ])
    send_button_content_descriptions: List[str] = field(default_factory=lambda: [
        "Send",
        "Envoyer",
    ])
    
    # Liste des messages dans une conversation
    message_list: str = '//*[@resource-id="com.instagram.android:id/message_list"]'
    message_item: str = '//*[@resource-id="com.instagram.android:id/direct_text_message_text_view"]'
    message_item_resource_id: str = 'com.instagram.android:id/direct_text_message_text_view'
    
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
