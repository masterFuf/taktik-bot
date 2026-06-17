from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from ..locales import L

@dataclass
class PopupSelectors:
    """Sélecteurs pour les popups et modales (likers, followers, etc.)."""

    # === Utilisateurs dans les popups ===
    username_in_popup_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_user_primary_name"]',
        '//*[@resource-id="com.instagram.android:id/follow_list_username"]',
        '//*[@resource-id="com.instagram.android:id/username"]'
    ])

    # === Détection des popups ===
    popup_bounds_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/bottom_sheet_container"]',
        '//*[@resource-id="com.instagram.android:id/modal_container"]',
        '//*[@resource-id="com.instagram.android:id/dialog_container"]',
        '//*[contains(@resource-id, "sheet")]',
        '//*[contains(@resource-id, "popup")]'
    ])

    _likers_popup_indicators_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/follow_list_username"]',
        '//*[@resource-id="com.instagram.android:id/row_user_primary_name"]',
        '//*[@resource-id="com.instagram.android:id/bottom_sheet_container"]'
    ])

    @property
    def likers_popup_indicators(self) -> List[str]:
        return self._likers_popup_indicators_base + L("popup.likers_popup_indicators")

    # Indicateurs de la vue des commentaires (pour éviter confusion avec likers popup)
    _comments_view_indicators_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/layout_comment_thread_edittext"]',
        '//*[@resource-id="com.instagram.android:id/row_comment_textview_comment"]'
    ])

    @property
    def comments_view_indicators(self) -> List[str]:
        return self._comments_view_indicators_base + L("popup.comments_view_indicators")

    # === Sélecteurs automation.py ===
    _automation_popup_indicators_base: List[str] = field(default_factory=lambda: [
        "//android.widget.RecyclerView[contains(@resource-id, 'list')]",
    ])

    @property
    def automation_popup_indicators(self) -> List[str]:
        return self._automation_popup_indicators_base + L("popup.automation_popup_indicators")

    _automation_user_selectors_base: List[str] = field(default_factory=lambda: [
        "//android.widget.LinearLayout[.//android.widget.TextView]",
        "//android.view.ViewGroup[.//android.widget.TextView]"
    ])

    @property
    def automation_user_selectors(self) -> List[str]:
        return self._automation_user_selectors_base + L("popup.automation_user_selectors")

    @property
    def close_popup_selectors(self) -> List[str]:
        return L("popup.close_popup_selectors")

    username_in_user_element: str = "//android.widget.TextView[1]"
    follow_button_in_user_element: str = "//android.widget.Button[@text='Follow' or @text='Suivre']"

    # === Dialogs génériques ===
    dialog_selectors: Dict[str, str] = field(default_factory=lambda: {
        'dialog_title': '//android.widget.TextView[contains(@resource-id, "dialog_title")]',
        'dialog_message': '//android.widget.TextView[contains(@resource-id, "message")]',
        'dialog_positive_button': '//android.widget.Button[contains(@resource-id, "button1")]',
        'dialog_negative_button': '//android.widget.Button[contains(@resource-id, "button2")]',
        'dialog_neutral_button': '//android.widget.Button[contains(@resource-id, "button3")]',
        'toast_message': '//android.widget.Toast[1]',
        'popup_close': '//android.widget.ImageView[contains(@content-desc, "Fermer") or contains(@content-desc, "Close")]',
        'rate_app_dialog': '//android.widget.TextView[contains(@text, "Note") or contains(@text, "Rate")]',
        'update_app_dialog': '//android.widget.TextView[contains(@text, "Mise à jour") or contains(@text, "Update")]'
    })

    @property
    def not_now_selectors(self) -> List[str]:
        return L("popup.not_now_selectors")

    # === Popup "Review this account before following" ===
    @property
    def review_account_popup_indicators(self) -> List[str]:
        return L("popup.review_account_popup_indicators")

    @property
    def review_account_follow_button(self) -> List[str]:
        return L("popup.review_account_follow_button")

    @property
    def review_account_cancel_button(self) -> List[str]:
        return L("popup.review_account_cancel_button")

    # === Popup de suggestions après follow ===
    _follow_suggestions_indicators_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "suggested")]',
        # "Suggestions" est un sous-texte présent en FR ("Suggestions pour vous")
        # comme en EN ("Suggestions for you") -> neutre, gardé pour toutes les langues.
        '//android.widget.TextView[contains(@text, "Suggestions")]',
    ])

    @property
    def follow_suggestions_indicators(self) -> List[str]:
        return self._follow_suggestions_indicators_base + L("popup.follow_suggestions_indicators")

    _follow_suggestions_close_methods_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "×")]',
    ])

    @property
    def follow_suggestions_close_methods(self) -> List[str]:
        return self._follow_suggestions_close_methods_base + L("popup.follow_suggestions_close_methods")

    # === Sélecteurs hashtag_business.py ===
    username_list_selector: str = '//*[@resource-id="com.instagram.android:id/follow_list_username"]'
    drag_handle_selector: str = '//*[@resource-id="com.instagram.android:id/bottom_sheet_drag_handle_prism"]'

    # === Comment popup close ===
    comment_popup_drag_handle: str = '//*[@resource-id="com.instagram.android:id/bottom_sheet_drag_handle_prism"]'

    # === Unfollow confirmation selectors ===
    @property
    def unfollow_confirmation_selectors(self) -> List[str]:
        return L("popup.unfollow_confirmation_selectors")

    # === Meta Ad Consent popup (2-page flow) ===
    # Page 1: "Want to subscribe or continue using our products free of charge with ads?"
    ad_consent_page1_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "free of charge with ads")]',
        '//*[contains(@text, "gratuitement avec des publicités")]',
        '//*[contains(@text, "Want to subscribe")]',
        '//*[contains(@text, "Vous souhaitez vous abonner")]',
        '//*[contains(@text, "Subscribe to use without ads")]',
        '//*[contains(@text, "without ads")]',
    ])

    # Radio button "Use free of charge with ads" (ViewGroup, no text/resource-id)
    ad_consent_free_option: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Use free of charge with ads")]',
        '//*[contains(@text, "Utiliser gratuitement avec des publicités")]',
        '//*[contains(@content-desc, "Use free of charge with ads")]',
        '//*[contains(@content-desc, "Utiliser gratuitement avec des publicités")]',
    ])

    # "Continue" button on page 1
    ad_consent_continue_button: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Continue"]',
        '//*[@content-desc="Continuer"]',
        '//*[@text="Continue"]',
        '//*[@text="Continuer"]',
    ])

    # Page 2: "To use our products free of charge with ads, agree to Meta processing your data..."
    ad_consent_page2_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "agree to Meta processing")]',
        '//*[contains(@text, "acceptez que Meta traite")]',
        '//*[contains(@text, "How we process your data for ads")]',
        '//*[contains(@text, "Comment nous traitons vos données")]',
    ])

    # "Agree" button on page 2
    ad_consent_agree_button: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Agree"]',
        '//*[@content-desc="Accepter"]',
        '//*[@text="Agree"]',
        '//*[@text="Accepter"]',
    ])

    # Page 3: "You can manage your ad experience" — just click OK
    ad_consent_page3_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "manage your ad experience")]',
        '//*[contains(@text, "gérer votre expérience publicitaire")]',
        '//*[contains(@text, "Personalized ads")]',
        '//*[contains(@text, "Publicités personnalisées")]',
        '//*[contains(@text, "Less-personalized ads")]',
    ])

    ad_consent_ok_button: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="OK"]',
        '//*[@text="OK"]',
        '//*[@text="Ok"]',
    ])

POPUP_SELECTORS = PopupSelectors()
