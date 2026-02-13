from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

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
    
    likers_popup_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "J\'aime")]',
        '//*[contains(@text, "En commun")]',
        '//*[@resource-id="com.instagram.android:id/follow_list_username"]',
        '//*[@resource-id="com.instagram.android:id/row_user_primary_name"]',
        '//*[@resource-id="com.instagram.android:id/bottom_sheet_container"]'
    ])
    
    # Indicateurs de la vue des commentaires (pour éviter confusion avec likers popup)
    comments_view_indicators: List[str] = field(default_factory=lambda: [
        '//*[@text="Comments"]',
        '//*[@text="Commentaires"]',
        '//*[contains(@text, "What do you think")]',
        '//*[contains(@text, "Add a comment")]',
        '//*[contains(@text, "Ajouter un commentaire")]',
        '//*[contains(@hint, "Add a comment")]',
        '//*[contains(@hint, "What do you think")]',
        '//*[@resource-id="com.instagram.android:id/layout_comment_thread_edittext"]',
        '//*[@resource-id="com.instagram.android:id/row_comment_textview_comment"]'
    ])
    
    # === Sélecteurs automation.py ===
    automation_popup_indicators: List[str] = field(default_factory=lambda: [
        "//android.widget.TextView[@text='Likes']",
        "//android.widget.TextView[@text='J\'aime']",
        "//android.widget.TextView[@text='Like']",
        "//android.widget.EditText[contains(@text, 'Search') or contains(@text, 'Rechercher')]",
        "//android.widget.RecyclerView[contains(@resource-id, 'list')]",
        "//android.widget.ImageView[@content-desc='Close']",
        "//android.widget.ImageView[@content-desc='Fermer']",
        "//android.widget.Button[@text='Follow' or @text='Suivre']"
    ])
    
    automation_user_selectors: List[str] = field(default_factory=lambda: [
        "//android.widget.LinearLayout[.//android.widget.TextView and .//android.widget.Button[@text='Follow' or @text='Suivre']]",
        "//android.view.ViewGroup[.//android.widget.TextView and .//android.widget.Button[@text='Follow' or @text='Suivre']]",
        "//android.widget.LinearLayout[.//android.widget.TextView]",
        "//android.view.ViewGroup[.//android.widget.TextView]"
    ])
    
    close_popup_selectors: List[str] = field(default_factory=lambda: [
        "//android.widget.ImageView[@content-desc='Close']",
        "//android.widget.ImageView[@content-desc='Fermer']",
        "//android.widget.Button[@content-desc='Close']",
        "//android.widget.Button[@content-desc='Fermer']"
    ])
    
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
    
    not_now_selectors: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@text, "Not Now")]',
        '//android.widget.Button[contains(@text, "Pas maintenant")]',
        '//android.widget.TextView[contains(@text, "Not Now")]',
        '//android.widget.TextView[contains(@text, "Pas maintenant")]'
    ])
    
    # === Popup "Review this account before following" ===
    review_account_popup_indicators: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "Review this account")]',
        '//android.widget.TextView[contains(@text, "before following")]',
        '//android.widget.TextView[contains(@text, "Date joined")]',
        '//android.widget.TextView[contains(@text, "Account based in")]'
    ])
    
    review_account_follow_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="Follow"]',
        '//android.widget.Button[@text="Suivre"]',
        '//android.widget.Button[contains(@text, "Follow") and not(contains(@text, "Following"))]'
    ])
    
    review_account_cancel_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="Cancel"]',
        '//android.widget.Button[@text="Annuler"]',
        '//android.widget.TextView[@text="Cancel"]',
        '//android.widget.TextView[@text="Annuler"]'
    ])
    
    # === Popup de suggestions après follow ===
    follow_suggestions_indicators: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "Suggested for you")]',
        '//android.widget.TextView[contains(@text, "Suggestions")]',
        '//*[contains(@resource-id, "suggested")]',
        '//*[contains(@content-desc, "Suggested")]'
    ])
    
    follow_suggestions_close_methods: List[str] = field(default_factory=lambda: [
        '//*[contains(@content-desc, "Close")]',
        '//*[contains(@content-desc, "Dismiss")]',
        '//*[contains(@text, "×")]',
        '//*[contains(@content-desc, "Fermer")]'
    ])
    
    # === Sélecteurs hashtag_business.py ===
    username_list_selector: str = '//*[@resource-id="com.instagram.android:id/follow_list_username"]'
    drag_handle_selector: str = '//*[@resource-id="com.instagram.android:id/bottom_sheet_drag_handle_prism"]'
    
    # === Comment popup close ===
    comment_popup_drag_handle: str = '//*[@resource-id="com.instagram.android:id/bottom_sheet_drag_handle_prism"]'
    
    # === Unfollow confirmation selectors ===
    unfollow_confirmation_selectors: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Ne plus suivre")]',
        '//*[contains(@text, "Unfollow")]',
        '//*[contains(@text, "Confirmer")]',
        '//*[contains(@text, "Confirm")]'
    ])

POPUP_SELECTORS = PopupSelectors()
