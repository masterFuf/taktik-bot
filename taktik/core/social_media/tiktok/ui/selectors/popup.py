"""Sélecteurs UI pour les popups et modales TikTok."""

from typing import List
from dataclasses import dataclass, field


@dataclass
class PopupSelectors:
    """Sélecteurs pour les popups et modales TikTok."""
    
    # === Boutons de fermeture ===
    close_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/dga"][@content-desc="Close"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/jyh"][@content-desc="Close"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/fac"]',
        '//android.widget.ImageView[@content-desc="Close"]',
        '//android.widget.ImageButton[@content-desc="Close"]',
        '//android.widget.ImageButton[@content-desc="Fermer"]',
        '//android.widget.Button[@content-desc="Close"]',
    ])
    
    # === Popup "Follow your friends" ===
    follow_friends_popup: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/w4h"]',
        '//*[contains(@text, "Follow your friends")]',
        '//*[contains(@text, "Suivez vos amis")]',
    ])
    
    follow_friends_close: List[str] = field(default_factory=lambda: [
        '//android.widget.ImageView[@resource-id="com.zhiliaoapp.musically:id/dga"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/dga"]',
        '//android.widget.ImageView[@content-desc="Close"][@clickable="true"]',
    ])
    
    dismiss_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/ny9"]',
        '//android.widget.Button[@content-desc="Dismiss"]',
        '//android.widget.Button[@text="Not now"]',
        '//android.widget.Button[contains(@text, "Not now")]',
        '//android.widget.Button[contains(@text, "Pas maintenant")]',
        '//android.widget.Button[contains(@text, "Skip")]',
    ])
    
    # === Popup "Create shared collections" ===
    collections_popup: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/jzb"]',
        '//*[contains(@text, "Create shared collections")]',
        '//*[contains(@text, "collections with a friend")]',
    ])
    
    collections_not_now: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/ny9"][@text="Not now"]',
        '//android.widget.Button[@text="Not now"]',
    ])
    
    collections_close: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/jyh"][@content-desc="Close"]',
    ])
    
    # === Popups spécifiques ===
    age_verification_popup: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "age")]',
        '//*[contains(@text, "âge")]',
        '//*[contains(@text, "birthday")]',
    ])
    
    notification_popup: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "notification")]',
        '//*[contains(@text, "Allow")]',
        '//*[contains(@text, "Autoriser")]',
    ])
    
    # === Bannières promotionnelles (comme "Hatch a Streak Pet") ===
    promo_banner: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/faf"]',
    ])
    
    promo_close_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/fad"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/fac"][@content-desc="Close"]',
    ])
    
    # === Notification banner (messages from users) ===
    notification_banner: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "sent you new messages")]',
        '//*[contains(@text, "sent you a message")]',
        '//*[contains(@text, "vous a envoyé")]',
        '//*[contains(@text, "Reply")][@clickable="true"]',
        '//*[contains(@text, "Répondre")][@clickable="true"]',
    ])
    
    # === Inbox page detection ===
    inbox_page_indicator: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/title"][@text="Inbox"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/jld"]',
        '//*[@text="New followers"]',
        '//*[@text="Activity"]',
        '//*[@text="System notifications"]',
    ])
    
    # === Link email popup ===
    link_email_popup: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/w4m"][@text="Link email"]',
        '//*[@text="Link email"]',
        '//*[contains(@text, "linking your Android email")]',
    ])
    
    link_email_not_now: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="Not now"]',
        '//*[@text="Not now"][@clickable="true"]',
        '//*[@text="Pas maintenant"][@clickable="true"]',
    ])
    
    invite_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/fab"]',
        '//android.widget.Button[@text="Invite"]',
    ])
    
    # === Suggestion Page (Follow back / Not interested) ===
    suggestion_page_indicator: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/y_k"][@text="Swipe up to skip"]',
        '//*[@text="Swipe up to skip"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/bjl"]',
    ])
    
    suggestion_not_interested: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/bjl"][@text="Not interested"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/bjl"]',
        '//android.widget.Button[@text="Not interested"]',
    ])
    
    suggestion_follow_back: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/bjk"][@text="Follow back"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/bjk"][@text="Follow"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/bjk"]',
        '//android.widget.Button[@text="Follow back"]',
        '//android.widget.Button[@text="Follow"]',
    ])
    
    suggestion_close: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/bjr"][@content-desc="Close"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/bjr"]',
    ])
    
    # === Comments Section (opened accidentally during scroll) ===
    comments_section_indicator: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/qx0"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/qx_"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/qx1"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/jt3"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/ja2"][@content-desc="Open stickers, gifs and emojis"]',
        '//android.widget.EditText[@focused="true"][contains(@hint, "Message")]',
    ])
    
    comments_close_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/dqh"][@content-desc="Close"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/dqh"]',
        '//android.widget.ImageView[@content-desc="Close"]',
    ])
    
    # Comment input area on video
    comment_input_area: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.zhiliaoapp.musically:id/xi_"][@text="Comment..."]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/dzd"]',
    ])
    
    # Keyboard/EditText detection
    keyboard_indicator: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[@focused="true"]',
        '//*[@resource-id="com.zhiliaoapp.musically:id/jt3"]//android.widget.EditText',
    ])
    
    # === Android System Popups ===
    system_deny_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.android.packageinstaller:id/permission_deny_button"]',
        '//*[@resource-id="com.android.permissioncontroller:id/permission_deny_button"]',
        '//*[@resource-id="com.google.android.permissioncontroller:id/permission_deny_button"]',
        '//*[@text="REFUSER"][@clickable="true"]',
        '//*[@text="Refuser"][@clickable="true"]',
        '//*[@text="Ne pas autoriser"][@clickable="true"]',
        '//*[@text="Non"][@clickable="true"]',
        '//*[@text="DENY"][@clickable="true"]',
        '//*[@text="Deny"][@clickable="true"]',
        "//*[@text=\"Don't allow\"][@clickable=\"true\"]",
        "//*[@text=\"DON'T ALLOW\"][@clickable=\"true\"]",
        '//*[@text="No"][@clickable="true"]',
        '//*[@text="NO"][@clickable="true"]',
    ])
    
    system_input_method_popup: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="android:id/alertTitle"][contains(@text, "saisie")]',
        '//*[@resource-id="android:id/alertTitle"][contains(@text, "input")]',
        '//*[@resource-id="android:id/alertTitle"][contains(@text, "keyboard")]',
        '//*[@resource-id="android:id/alertTitle"][contains(@text, "Keyboard")]',
        '//*[@resource-id="android:id/select_dialog_listview"]',
    ])
    
    system_dialog: List[str] = field(default_factory=lambda: [
        '//*[@package="android"][@resource-id="android:id/parentPanel"]',
    ])


POPUP_SELECTORS = PopupSelectors()
