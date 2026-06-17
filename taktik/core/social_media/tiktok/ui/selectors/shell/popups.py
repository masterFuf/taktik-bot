"""Sélecteurs UI pour les popups et modales TikTok."""

from typing import List
from dataclasses import dataclass, field

from ..locales import L


@dataclass
class PopupSelectors:
    """Sélecteurs pour les popups et modales TikTok."""
    
    # === Boutons de fermeture ===
    _close_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/fac")]',
    ])

    @property
    def close_button(self) -> List[str]:
        return self._close_button_base + L("popup.close_button")

    # === Popup "Follow your friends" ===
    _follow_friends_popup_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/w4h")]',
    ])

    @property
    def follow_friends_popup(self) -> List[str]:
        return self._follow_friends_popup_base + L("popup.follow_friends_popup")

    _follow_friends_close_base: List[str] = field(default_factory=lambda: [
        '//android.widget.ImageView[contains(@resource-id, ":id/dga")]',
        '//*[contains(@resource-id, ":id/dga")]',
    ])

    @property
    def follow_friends_close(self) -> List[str]:
        return self._follow_friends_close_base + L("popup.follow_friends_close")

    follow_friends_close_description: str = "Close"

    _dismiss_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ny9")]',
        '//android.widget.Button[@content-desc="Dismiss"]',
    ])

    @property
    def dismiss_button(self) -> List[str]:
        return self._dismiss_button_base + L("popup.dismiss_button")

    # === Popup "Create shared collections" ===
    _collections_popup_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/jzb")]',
        '//*[contains(@text, "collections with a friend")]',
    ])

    @property
    def collections_popup(self) -> List[str]:
        return self._collections_popup_base + L("popup.collections_popup")

    @property
    def collections_not_now(self) -> List[str]:
        return L("popup.collections_not_now")

    @property
    def collections_close(self) -> List[str]:
        return L("popup.collections_close")

    # === Popups spécifiques ===
    _age_verification_popup_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "age")]',
    ])

    @property
    def age_verification_popup(self) -> List[str]:
        return self._age_verification_popup_base + L("popup.age_verification_popup")

    _notification_popup_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "notification")]',
    ])

    @property
    def notification_popup(self) -> List[str]:
        return self._notification_popup_base + L("popup.notification_popup")

    # === Bannières promotionnelles (comme "Hatch a Streak Pet") ===
    promo_banner: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/faf")]',
    ])

    _promo_close_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/fad")]',
    ])

    @property
    def promo_close_button(self) -> List[str]:
        return self._promo_close_button_base + L("popup.promo_close_button")

    # === Notification banner (messages from users) ===
    _notification_banner_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "sent you new messages")]',
        '//*[contains(@text, "sent you a message")]',
        '//*[contains(@text, "vous a envoyé")]',
    ])

    @property
    def notification_banner(self) -> List[str]:
        return self._notification_banner_base + L("popup.notification_banner")

    # === Inbox page detection ===
    _inbox_page_indicator_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/jld")]',
    ])

    @property
    def inbox_page_indicator(self) -> List[str]:
        return self._inbox_page_indicator_base + L("popup.inbox_page_indicator")

    # === Link email popup ===
    link_email_popup: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/w4m")][@text="Link email"]',
        '//*[@text="Link email"]',
        '//*[contains(@text, "linking your Android email")]',
    ])
    
    @property
    def link_email_not_now(self) -> List[str]:
        return L("popup.link_email_not_now")

    # === GDPR / EEA data transfer modal ===
    gdpr_popup: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/w4m")][contains(@text, "EEE")]',
        '//*[contains(@resource-id, ":id/w4m")][contains(@text, "EEA")]',
        '//*[contains(@text, "transferts de données des utilisateurs de l’EEE vers la Chine")]',
        '//*[contains(@text, "transferts de données des utilisateurs de l\'EEE vers la Chine")]',
        '//*[contains(@text, "transfers of EEA User Data to China")]',
    ])

    gdpr_got_it_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="J\'ai compris"]',
        '//android.widget.Button[contains(@text, "J\'ai compris")]',
        '//android.widget.Button[@text="Got it"]',
        '//android.widget.Button[contains(@text, "Got it")]',
    ])
    
    invite_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/fab")]',
        '//android.widget.Button[@text="Invite"]',
    ])
    
    # === Suggestion Page (Follow back / Not interested) ===
    suggestion_page_indicator: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/y_k")][@text="Swipe up to skip"]',
        '//*[@text="Swipe up to skip"]',
        '//*[contains(@resource-id, ":id/bjl")]',
    ])
    
    @property
    def suggestion_not_interested(self) -> List[str]:
        return L("popup.suggestion_not_interested")

    _suggestion_follow_back_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/bjk")]',
    ])

    @property
    def suggestion_follow_back(self) -> List[str]:
        return self._suggestion_follow_back_base + L("popup.suggestion_follow_back")

    _suggestion_close_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/bjr")]',
    ])

    @property
    def suggestion_close(self) -> List[str]:
        return self._suggestion_close_base + L("popup.suggestion_close")
    
    # === Comments Section (opened accidentally during scroll) ===
    comments_section_indicator: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/qx0")]',
        '//*[contains(@resource-id, ":id/qx_")]',
        '//*[contains(@resource-id, ":id/qx1")]',
        '//*[contains(@resource-id, ":id/jt3")]',
        '//*[contains(@resource-id, ":id/ja2")][@content-desc="Open stickers, gifs and emojis"]',
        '//android.widget.EditText[@focused="true"][contains(@hint, "Message")]',
    ])
    
    _comments_close_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/dqh")]',
    ])

    @property
    def comments_close_button(self) -> List[str]:
        return self._comments_close_button_base + L("popup.comments_close_button")

    # Comment input area on video
    _comment_input_area_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/dzd")]',
    ])

    @property
    def comment_input_area(self) -> List[str]:
        return self._comment_input_area_base + L("popup.comment_input_area")
    
    # Keyboard/EditText detection
    keyboard_indicator: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[@focused="true"]',
        '//*[contains(@resource-id, ":id/jt3")]//android.widget.EditText',
    ])
    
    # === Android System Popups ===
    _system_deny_button_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.android.packageinstaller:id/permission_deny_button"]',
        '//*[@resource-id="com.android.permissioncontroller:id/permission_deny_button"]',
        '//*[@resource-id="com.google.android.permissioncontroller:id/permission_deny_button"]',
        "//*[@text=\"DON'T ALLOW\"][@clickable=\"true\"]",
        '//*[@text="NO"][@clickable="true"]',
    ])

    @property
    def system_deny_button(self) -> List[str]:
        return self._system_deny_button_base + L("popup.system_deny_button")
    
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

    # === Video options bottom sheet (longpress menu: Download, Report, Speed...) ===
    # resource-id f0u / content-desc="Bottom sheet"
    # Appears when the user long-presses a video or accidentally triggers the share sheet.
    # Must be closed via back button (tapping outside closes it but also interacts with video).
    video_options_sheet: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/f0u")][@content-desc="Bottom sheet"]',
        '//*[@content-desc="Bottom sheet"]',
    ])


POPUP_SELECTORS = PopupSelectors()
