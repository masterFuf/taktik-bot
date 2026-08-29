"""UI selectors for TikTok DM conversations."""

from typing import List
from dataclasses import dataclass, field

from ..locales import L


@dataclass
class ConversationSelectors:
    """Selectors for TikTok DM conversations.
    
    Based on real UI dumps:
    - a one-to-one conversation
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
    
    _conversation_name_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/h4a")]',
    ])

    @property
    def conversation_name(self) -> List[str]:
        return self._conversation_name_base + L("conversation.conversation_name_anchors")
    
    conversation_avatar: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/k9u")]',
        # A2: the header node carrying the correspondent's name, reached from the back button.
        # Resolves exactly one on all four captured conversations, on both versions.
        '//*[@content-desc="Retour" or @content-desc="Back"]/../..//*[@clickable="true"][string-length(@content-desc)>0][not(@content-desc="Retour" or @content-desc="Back" or @content-desc="Plus" or @content-desc="More" or @content-desc="Signaler" or @content-desc="Report")]',
    ])
    
    group_member_count: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/sqz")]',
    ])
    
    report_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/j47")][@content-desc="Report"]',
        # A2. Present on 43.1.4's header; 46.6.3 keeps it behind the overflow.
        '//*[@clickable="true"][@content-desc="Signaler" or @content-desc="Report"]',
    ])
    
    more_options_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/j1_")][@content-desc="More"]',
        # A2: the header's overflow. Scoped to the header on purpose -- a bare clickable "Plus"
        # resolves ten times on a followers list.
        '//*[@content-desc="Retour" or @content-desc="Back"]/../..//*[@clickable="true"][@content-desc="Plus" or @content-desc="More"]',
    ])
    
    # === Profile info (for new conversations) ===
    profile_avatar: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qbd")]',
        # A2: resolves exactly one on all four captured conversations, on both versions, and
        # ZERO on the other 28 captured screens.
        '//android.widget.TextView[starts-with(@text, "@")]/../..//android.widget.ImageView',
    ])
    
    profile_display_name: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qf7")]',
        # A2: resolves exactly one on all four captured conversations, on both versions, and
        # ZERO on the other 28 captured screens.
        '//android.widget.TextView[starts-with(@text, "@")]/../android.widget.TextView[1]',
    ])
    
    profile_username: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qgb")]//android.widget.TextView[contains(@text, "@")]',
        # A2: resolves exactly one on all four captured conversations, on both versions, and
        # ZERO on the other 28 captured screens.
        # The '@' prefix is the handle's own
        # punctuation, so this holds in any language.
        '//android.widget.TextView[starts-with(@text, "@")]',
    ])
    
    profile_stats: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qgb")]//android.widget.TextView[contains(@text, "following")]',
        # A2: the profile card's counts line ("36 suivis · 105 followers"), reached from the
        # handle. One hit on all four captured conversations, none on the other 28 screens.
        '//android.widget.TextView[starts-with(@text, "@")]/../android.widget.TextView[contains(@text, "·")]',
    ])
    
    # === Messages list ===
    messages_list: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/r_k")]',
        # A2. Like every field on this surface it is only meaningful once the caller knows it
        # is IN a conversation: on its own the expression also matches other screens.
        '//*[@scrollable="true"]',
    ])
    
    message_item: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/tow")]',
        # A2. Like every field on this surface it is only meaningful once the caller knows it
        # is IN a conversation: on its own the expression also matches other screens.
        '//*[@focusable="true"][string-length(@text)>0][not(@content-desc) or @content-desc=""][not(self::android.widget.EditText)][not(self::android.widget.Button)]/../..',
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
        # A2. Like every field on this surface it is only meaningful once the caller knows it
        # is IN a conversation: on its own the expression also matches other screens.
        '//*[@focusable="true"][string-length(@text)>0][not(@content-desc) or @content-desc=""][not(self::android.widget.EditText)][not(self::android.widget.Button)]/..',
    ])
    
    _message_text_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/jay")]',
    ])

    @property
    def message_text(self) -> List[str]:
        """Message bubbles. The id below is 43.1.4 only.

        Measured on device 2026-08-29: 46.6.3 names the same node `koy`, so the id-only
        selector read ZERO messages there — `get_messages` returned an empty conversation on a
        thread that plainly had two. Neither version offers a readable id, and the class is
        readable on 43.1.4 (`im.messagelist.api.ui.IMTuxTextLayoutView`) yet obfuscated to
        `X.1K8h` on 46.6.3, so the anchor rides on what both share: a focusable text node with
        no content-desc, which is neither the composer nor a button.
        """
        return self._message_text_base + L("conversation.message_text_anchors")
    
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
        # A2: the DIRECT parent of the reactions. An `.//` form matched every ancestor, fifteen of them.
        '//*[*[@content-desc="Heart"]]',
    ])
    
    reaction_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/uc")]',
        '//*[contains(@resource-id, ":id/ug")]',
        # A2: a reaction button IS one of the three reactions, and their content-descs are
        # identical across versions -- measured, one hit each on both.
        '//*[@content-desc="Heart" or @content-desc="Lol" or @content-desc="ThumbsUp"]',
    ])
    
    reaction_heart: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ug")][@content-desc="Heart"]',
        # A2: the reaction descs are IDENTICAL across versions; only the ids move.
        '//*[@content-desc="Heart"]',
    ])
    
    reaction_lol: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ug")][@content-desc="Lol"]',
        # A2, see reaction_heart.
        '//*[@content-desc="Lol"]',
    ])
    
    reaction_thumbsup: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ug")][@content-desc="ThumbsUp"]',
        # A2, see reaction_heart.
        '//*[@content-desc="ThumbsUp"]',
    ])
    
    # === Message input ===
    message_input_container: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/yi7")]',
        '//*[contains(@resource-id, ":id/fwt")]',
        '//*[contains(@resource-id, ":id/jt2")]',
        # A2. Like every field on this surface it is only meaningful once the caller knows it
        # is IN a conversation: on its own the expression also matches other screens.
        '//android.widget.EditText/..',
    ])
    
    _message_input_field_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/jt3")]//android.widget.EditText',
        '//android.widget.EditText[@hint="Message..."]',
        '//android.widget.EditText[contains(@hint, "Message")]',
    ])

    @property
    def message_input_field(self) -> List[str]:
        return self._message_input_field_base + L("conversation.message_input_field_anchors")
    
    emoji_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ja2")][@content-desc="Open stickers, gifs and emojis"]',
        '//*[contains(@resource-id, ":id/ja2")]',
        # A2.
        '//*[@clickable="true"][contains(@content-desc, "stickers")]',
    ])
    
    voice_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/jtf")]',
        '//*[contains(@resource-id, ":id/c8f")]',
        # A2.
        '//*[contains(@content-desc, "Message vocal") or contains(@content-desc, "Voice message")]',
    ])
    
    _send_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/jt8")]',
        '//android.widget.Button[@content-desc="Send"]',
    ])

    @property
    def send_button(self) -> List[str]:
        return self._send_button_base + L("conversation.send_button_anchors")
    
    # === Sticker suggestion (new conversation) ===
    sticker_suggestion: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/q12")]',
        '//*[contains(@resource-id, ":id/q14")]',
    ])
    
    @property
    def close_interstitial(self) -> List[str]:
        """Dismiss whatever TikTok raised ON TOP of a conversation.

        Broader than the sticker popup it started as, because the sticker popup is not the only
        one: opening a conversation can raise a MODAL bottom sheet (read receipts) that replaces
        the entire hierarchy -- back button, header and composer all gone. `is_in_conversation`
        then reads absent and the open is reported as a failure it was not.

        The sheet anchors are scoped to the sheet container on purpose. A bare clickable
        "Fermer" was measured against 25 captured screens and fires on the comments sheet, the
        followers list and search, where closing would be wrong.
        """
        return L("conversation.close_interstitial")

    @property
    def close_sticker_suggestion(self) -> List[str]:
        # Kept for its callers; the sticker popup is one interstitial among several, and its own
        # locale entry was EMPTY -- so `close_sticker_suggestions=True` closed nothing at all.
        return self.close_interstitial
    
    # === Games/Cards buttons ===
    games_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/v1")][@text="Games"]',
    ])
    
    cards_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/v1")][@text="Cards"]',
        # A2: the label is the same node on both versions, only the id moves.
        '//*[@text="Cartes" or @text="Cards"]',
    ])


CONVERSATION_SELECTORS = ConversationSelectors()
