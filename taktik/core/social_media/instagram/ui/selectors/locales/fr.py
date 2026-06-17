"""French (fr) UI string overlay for Instagram selectors.

ONE module per language. Holds ONLY the language-specific selector fragments
(``@text`` / ``@content-desc`` / ``@hint`` / bare labels) keyed by
``"<surface>.<field>"``. Language-neutral selectors (resource-id / class /
position) live in the selector dataclasses under ``ui/selectors/**`` and are
combined with these via ``L(key)`` (see ``locales/__init__.py``).

Provenance: fragments extracted from the historical EN/FR selector lists
(real device dumps, Instagram v410.0.0.53.71).
"""
from typing import Dict, List

STRINGS: Dict[str, List[str]] = {
    # --- surfaces/profile.py ---
    "profile.follow_button": [
        '//*[contains(@text, "Suivre") and not(contains(@text, "Abonné"))]',
    ],
    "profile.following_button": [
        '//*[contains(@text, "Abonné")]',
        '//*[contains(@text, "Suivi(e)")]',
    ],
    "profile.follow_button_text_labels": [
        'Suivre',
    ],
    "profile.message_button": [
        '//*[contains(@text, "Envoyer un message")]',
    ],
    "profile.message_button_text_labels": [
        'Envoyer un message',
    ],
    "profile.followers_link": [
        '//*[contains(@content-desc, "abonnés")]',
        '//*[contains(@content-desc, "Abonnés")]',
        '//android.view.ViewGroup[.//android.widget.TextView[contains(@text, "abonnés")]]',
        '//android.widget.LinearLayout[.//android.widget.TextView[contains(@text, "abonnés")]]',
        '//android.widget.TextView[contains(@text, "abonnés")]',
        '//android.widget.TextView[contains(@text, "Abonnés")]',
    ],
    "profile.following_link": [
        '//*[contains(@content-desc, "abonnements")]',
        '//*[contains(@content-desc, "Abonnements")]',
        '//android.view.ViewGroup[.//android.widget.TextView[contains(@text, "abonnements")]]',
        '//android.widget.LinearLayout[.//android.widget.TextView[contains(@text, "abonnements")]]',
        '//android.widget.TextView[contains(@text, "abonnements")]',
        '//android.widget.TextView[contains(@text, "Abonnements")]',
    ],
    "profile.private_indicators": [
        '//*[contains(@text, "privé")]',
        '//*[contains(@text, "Suivre pour voir")]',
        '//*[contains(@content-desc, "privé")]',
    ],
    "profile.private_text_contains": [
        "compte est privé",
    ],
    "profile.about_account_page_indicators": [
        '//*[@resource-id="com.instagram.android:id/action_bar_title" and @text="À propos de ce compte"]',
    ],
    "profile.about_account_date_joined_value": [
        '//*[contains(@content-desc, "Date d\'inscription")]/android.view.View[2]',
    ],
    "profile.about_account_based_in_value": [
        '//*[contains(@content-desc, "Compte basé")]/android.view.View[2]',
    ],
    "profile.advanced_follow_selectors": [
        '//android.widget.Button[@text="Suivre" and not(contains(@content-desc, "followers")) and not(contains(@content-desc, "following"))]',
        '//android.widget.Button[contains(@content-desc, "Suivre") and not(contains(@content-desc, "followers"))]',
    ],
    "profile.zero_posts_indicators": [
        '//*[contains(@content-desc, "0publications")]',
        '//*[contains(@content-desc, "0 publications")]',
    ],
}
