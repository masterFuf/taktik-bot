"""Sélecteurs UI pour les conversations DM TikTok."""

from typing import List
from dataclasses import dataclass, field

from ..locales import L


@dataclass
class ConversationSelectors:
    """Sélecteurs pour les conversations DM TikTok.
    
    Basé sur UI dumps:
    - ui_dump_20260107_231514.xml (conversation simple avec @lobinho)
    - ui_dump_20260107_231534.xml (conversation de groupe "Hyper Shadic & FNF Crews")
    
    Resource-IDs identifiés:
    - lep/nmy: Back button
    - h4a: Username/Group name in header
    - k9u: Avatar in header
    - sqz: Member count for groups
    - j47: Report button
    - j1_: More options button
    - r_k: Messages RecyclerView
    - tow: Message item container
    - z05: Sender username
    - e7j: Message content container (text, sticker, GIF)
    - jay: Text message content
    - p10: Sticker/GIF image
    - l9k: Date separator
    - n9t: Date text
    - jt3: Message input container
    - ja2: Emoji/sticker button
    - rh_: Reply button (for replying to specific message)
    """
    
    # === Header ===
    _back_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/lep")]',
    ])

    @property
    def back_button(self) -> List[str]:
        return self._back_button_base + L("conversation.back_button")
    
    conversation_name: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/h4a")]',
    ])
    
    conversation_avatar: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/k9u")]',
    ])
    
    group_member_count: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/sqz")]',
    ])
    
    report_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/j47")][@content-desc="Report"]',
    ])
    
    more_options_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/j1_")][@content-desc="More"]',
    ])
    
    # === Profile info (for new conversations) ===
    profile_avatar: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qbd")]',
    ])
    
    profile_display_name: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qf7")]',
    ])
    
    profile_username: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qgb")]//android.widget.TextView[contains(@text, "@")]',
    ])
    
    profile_stats: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qgb")]//android.widget.TextView[contains(@text, "following")]',
    ])
    
    # === Messages list ===
    messages_list: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/r_k")]',
    ])
    
    message_item: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/tow")]',
    ])
    
    message_sender: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/z05")]',
    ])
    
    message_sender_avatar: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/b71")]',
        '//*[contains(@resource-id, ":id/b5p")]',
    ])
    
    message_content_container: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/e7j")]',
    ])
    
    message_text: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/jay")]',
    ])
    
    message_sticker: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/p10")]',
        '//*[contains(@resource-id, ":id/e95")][@content-desc="Stickers"]',
    ])
    
    message_gif: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/e7j")][@content-desc="GIF"]',
    ])
    
    # === Date separators ===
    date_separator: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/l9k")]',
    ])
    
    date_text: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/n9t")]',
    ])
    
    # === Reply button (for specific message) ===
    _reply_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/j8j")]',
    ])

    @property
    def reply_button(self) -> List[str]:
        return self._reply_button_base + L("conversation.reply_button")
    
    # === Quick reactions bar ===
    reactions_bar: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ue")]',
        '//*[contains(@resource-id, ":id/ur")]',
    ])
    
    reaction_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/uc")]',
        '//*[contains(@resource-id, ":id/ug")]',
    ])
    
    reaction_heart: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ug")][@content-desc="Heart"]',
    ])
    
    reaction_lol: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ug")][@content-desc="Lol"]',
    ])
    
    reaction_thumbsup: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ug")][@content-desc="ThumbsUp"]',
    ])
    
    # === Message input ===
    message_input_container: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/yi7")]',
        '//*[contains(@resource-id, ":id/fwt")]',
        '//*[contains(@resource-id, ":id/jt2")]',
    ])
    
    message_input_field: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/jt3")]//android.widget.EditText',
        '//android.widget.EditText[@hint="Message..."]',
        '//android.widget.EditText[contains(@hint, "Message")]',
    ])
    
    emoji_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ja2")][@content-desc="Open stickers, gifs and emojis"]',
        '//*[contains(@resource-id, ":id/ja2")]',
    ])
    
    voice_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/jtf")]',
        '//*[contains(@resource-id, ":id/c8f")]',
    ])
    
    send_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/jt8")]',
        '//android.widget.Button[@content-desc="Send"]',
    ])
    
    # === Sticker suggestion (new conversation) ===
    sticker_suggestion: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/q12")]',
        '//*[contains(@resource-id, ":id/q14")]',
    ])
    
    @property
    def close_sticker_suggestion(self) -> List[str]:
        return L("conversation.close_sticker_suggestion")
    
    # === Games/Cards buttons ===
    games_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/v1")][@text="Games"]',
    ])
    
    cards_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/v1")][@text="Cards"]',
    ])


CONVERSATION_SELECTORS = ConversationSelectors()
