"""Sélecteurs UI pour les conversations DM TikTok."""

from typing import List
from dataclasses import dataclass, field


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
    back_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/lep"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/nmy"][@content-desc="Back"]',
        '//android.widget.ImageView[@content-desc="Back"]',
    ])
    
    conversation_name: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/h4a"]',
    ])
    
    conversation_avatar: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/k9u"]',
    ])
    
    group_member_count: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/sqz"]',
    ])
    
    report_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/j47"][@content-desc="Report"]',
    ])
    
    more_options_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/j1_"][@content-desc="More"]',
    ])
    
    # === Profile info (for new conversations) ===
    profile_avatar: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/qbd"]',
    ])
    
    profile_display_name: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/qf7"]',
    ])
    
    profile_username: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/qgb"]//android.widget.TextView[contains(@text, "@")]',
    ])
    
    profile_stats: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/qgb"]//android.widget.TextView[contains(@text, "following")]',
    ])
    
    # === Messages list ===
    messages_list: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/r_k"]',
    ])
    
    message_item: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/tow"]',
    ])
    
    message_sender: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/z05"]',
    ])
    
    message_sender_avatar: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/b71"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/b5p"]',
    ])
    
    message_content_container: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/e7j"]',
    ])
    
    message_text: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/jay"]',
    ])
    
    message_sticker: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/p10"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/e95"][@content-desc="Stickers"]',
    ])
    
    message_gif: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/e7j"][@content-desc="GIF"]',
    ])
    
    # === Date separators ===
    date_separator: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/l9k"]',
    ])
    
    date_text: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/n9t"]',
    ])
    
    # === Reply button (for specific message) ===
    reply_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/rh_"][@text="Reply"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/j8j"]',
    ])
    
    # === Quick reactions bar ===
    reactions_bar: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/ue"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/ur"]',
    ])
    
    reaction_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/uc"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/ug"]',
    ])
    
    reaction_heart: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/ug"][@content-desc="Heart"]',
    ])
    
    reaction_lol: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/ug"][@content-desc="Lol"]',
    ])
    
    reaction_thumbsup: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/ug"][@content-desc="ThumbsUp"]',
    ])
    
    # === Message input ===
    message_input_container: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/yi7"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/fwt"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/jt2"]',
    ])
    
    message_input_field: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/jt3"]//android.widget.EditText',
        '//android.widget.EditText[@hint="Message..."]',
        '//android.widget.EditText[contains(@hint, "Message")]',
    ])
    
    emoji_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/ja2"][@content-desc="Open stickers, gifs and emojis"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/ja2"]',
    ])
    
    voice_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/jtf"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/c8f"]',
    ])
    
    send_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/jt8"]',
        '//android.widget.Button[@content-desc="Send"]',
    ])
    
    # === Sticker suggestion (new conversation) ===
    sticker_suggestion: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/q12"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/q14"]',
    ])
    
    close_sticker_suggestion: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/dgd"][@content-desc="Close"]',
    ])
    
    # === Games/Cards buttons ===
    games_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/v1"][@text="Games"]',
    ])
    
    cards_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/v1"][@text="Cards"]',
    ])


CONVERSATION_SELECTORS = ConversationSelectors()
