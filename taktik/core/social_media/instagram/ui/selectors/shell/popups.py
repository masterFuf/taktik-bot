from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from ..locales import L

@dataclass
class PopupSelectors:
    """Selectors for popups and modal sheets (likers, followers, …)."""

    # === Users inside popups ===
    username_in_popup_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_user_primary_name"]',
        '//*[@resource-id="com.instagram.android:id/follow_list_username"]',
        '//*[@resource-id="com.instagram.android:id/username"]'
    ])

    # === Popup detection ===
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

    # Comments-view markers (to avoid confusing it with the likers popup)
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

    # === Section inline de suggestions après follow ===
    _follow_suggestions_indicators_base: List[str] = field(default_factory=lambda: [
        # "Suggestions" is a substring of the heading in both languages, so it is
        # neutral and kept for every locale.
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

    # === Bottom sheets (generic) ===
    # The grey grab bar at the top of a bottom sheet. Instagram names it on some sheets
    # (comments) and leaves it anonymous on others — on the Direct share sheet it is a bare
    # 88x6 ImageView with no resource-id and no content-desc, which is why an id-only lookup
    # finds nothing there. Ids first (cheap, exact), geometry second (see bottom_sheet.py).
    bottom_sheet_drag_handle_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/bottom_sheet_drag_handle_prism"]',
        '//*[contains(@resource-id, "bottom_sheet_drag_handle")]',
    ])

    # Root of an open bottom sheet. Used to bound the geometric handle search to the sheet's
    # own top edge instead of the screen's, and to tell "a sheet is up" from "nothing is up".
    bottom_sheet_container_selectors: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "layout_container_bottom_sheet")]',
        '//*[contains(@resource-id, "bottom_sheet_container")]',
    ])

    # Candidate pool for the geometric grab-bar search, SCOPED to the sheet's own subtree: the
    # bar is decorative (never clickable) and belongs to the sheet, so searching the whole screen
    # would also offer up dividers from the page still rendered behind the dimmer. Shape filtering
    # (thin, wide-ish, centred) happens in actions/atomic/interaction/bottom_sheet.py — a ratio of
    # the screen cannot be expressed as XPath.
    bottom_sheet_handle_candidates: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "layout_container_bottom_sheet")]//*[@clickable="false"]',
        '//*[contains(@resource-id, "bottom_sheet_container")]//*[@clickable="false"]',
    ])

    # The Direct / share sheet reached from a post's share button. Its own marker, so a caller
    # can ask "is THAT sheet still up" rather than "is any sheet up".
    share_sheet_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "direct_private_share_container_view")]',
        '//*[contains(@resource-id, "direct_private_share_recipients_recycler_view")]',
        '//*[contains(@resource-id, "direct_external_reshare_row")]',
    ])

    # The "add this to my own story" cell of that sheet's external-reshare row.
    #
    # Structure from a real dump (`post.open_share`, IG v410, FR device): the row is a
    # RecyclerView `direct_external_reshare_row` whose clickable child is an ImageView with
    # the generic id `button`, labelled by content-desc; a sibling TextView `label` repeats
    # the wording and is NOT clickable. We therefore anchor on the row and take the clickable
    # descendant, and only fall back to the label text — `button` and `label` are far too
    # generic to be searched screen-wide.
    #
    # The wording itself lives in the locale overlay, shared with the feed tray's empty-ring
    # badge which uses the SAME label; see `content_creation.add_to_story_texts`.
    #
    # NOTE: confirmed for a POST's share sheet. Whether a STORY's share sheet offers this row
    # at all is a product question — Instagram only lets you re-share someone's story when it
    # mentions you. The relay task reports its absence as 'unavailable' rather than as a
    # failure, which is how running it once answers the question.
    add_to_story_row: str = (
        '//*[contains(@resource-id, "direct_external_reshare_row")]//*[@clickable="true"]'
    )

    @property
    def add_to_story_labels(self) -> List[str]:
        """Text fallback for the same cell, scoped to the sheet's reshare row."""
        from ..surfaces.content_creation import CONTENT_CREATION_SELECTORS

        return [
            f'//*[contains(@resource-id, "direct_external_reshare_row")]'
            f'//*[@text="{label}" or @content-desc="{label}"]'
            for label in CONTENT_CREATION_SELECTORS.add_to_story_texts
        ]

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

    # === Modale "Autoriser Instagram a acceder a vos contacts ?" ===
    # Appears after the "See all" CTA of the feed suggestions carousel.
    # (dump reel, IG v410.0.0.53.71, 2026-07-26).
    #
    # WARNING: the three `igds_alert_dialog_*` resource-ids are the GENERIC chassis
    # of Instagram alerts — the restriction modal carries them too. NEVER tap the
    # primary button on the strength of those ids alone: the HEADLINE must be
    # confirmed first through `contacts_access_headline_texts`.
    contacts_access_dialog: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/igds_alert_dialog_headline"]',
    ])
    contacts_access_subtext: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/igds_alert_dialog_subtext"]',
    ])
    # Buttons: resource-id, so language-independent. The primary one ACCEPTS
    # (uploads the address book), the cancel one REFUSES.
    contacts_access_allow_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/igds_alert_dialog_primary_button"]',
    ])
    contacts_access_deny_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/igds_alert_dialog_cancel_button"]',
    ])

    @property
    def contacts_access_headline_texts(self) -> List[str]:
        """Headline fragments (raw LABELS, not xpaths) proving that
        the alert on screen really is the contacts-access request."""
        return L("popup.contacts_access_headline_texts")

POPUP_SELECTORS = PopupSelectors()
