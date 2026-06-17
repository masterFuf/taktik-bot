"""English (en) UI string overlay for Instagram selectors.

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
        '//*[contains(@text, "Follow") and not(contains(@text, "Following"))]',
    ],
    "profile.following_button": [
        '//*[contains(@text, "Following")]',
    ],
    "profile.follow_button_text_labels": [
        'Follow',
    ],
    "profile.message_button": [],
    "profile.message_button_text_labels": [],
    "profile.followers_link": [
        '//*[contains(@content-desc, "followers")]',
        '//*[contains(@content-desc, "Followers")]',
        '//android.view.ViewGroup[.//android.widget.TextView[contains(@text, "followers")]]',
        '//android.widget.LinearLayout[.//android.widget.TextView[contains(@text, "followers")]]',
        '//android.widget.TextView[contains(@text, "followers")]',
        '//android.widget.TextView[contains(@text, "Followers")]',
    ],
    "profile.following_link": [
        '//*[contains(@content-desc, "following")]',
        '//*[contains(@content-desc, "Following")]',
        '//android.view.ViewGroup[.//android.widget.TextView[contains(@text, "following")]]',
        '//android.widget.LinearLayout[.//android.widget.TextView[contains(@text, "following")]]',
        '//android.widget.TextView[contains(@text, "following")]',
        '//android.widget.TextView[contains(@text, "Following")]',
    ],
    "profile.private_indicators": [
        '//*[contains(@text, "Private")]',
        '//*[contains(@text, "private")]',
        '//*[contains(@text, "Follow to see")]',
        '//*[contains(@content-desc, "Private")]',
    ],
    "profile.private_text_contains": [
        "account is private",
    ],
    "profile.about_account_page_indicators": [
        '//*[@resource-id="com.instagram.android:id/action_bar_title" and @text="About this account"]',
    ],
    "profile.about_account_date_joined_value": [
        '//*[contains(@content-desc, "Date joined")]/android.view.View[2]',
    ],
    "profile.about_account_based_in_value": [
        '//*[contains(@content-desc, "Account based in")]/android.view.View[2]',
    ],
    "profile.advanced_follow_selectors": [
        '//android.widget.Button[@text="Follow" and not(contains(@content-desc, "followers")) and not(contains(@content-desc, "following"))]',
        '//android.widget.Button[contains(@content-desc, "Follow") and not(contains(@content-desc, "followers"))]',
    ],
    "profile.zero_posts_indicators": [],
}
