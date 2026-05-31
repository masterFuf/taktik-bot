from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class WatchdogSelectors:
    """UI dump signatures used by the workflow watchdog support runtime."""

    overlay_signatures: List[Dict[str, object]] = field(default_factory=lambda: [
        {
            "name": "comments_popup",
            "label": "Comments popup",
            "indicators": [
                'id/sticky_header_list"',
                'text="Comments"',
                'content-desc="Add a comment"',
            ],
            "min_matches": 1,
            "recovery": ["back"],
        },
        {
            "name": "follow_options_bottom_sheet",
            "label": "Follow options bottom sheet",
            "indicators": [
                'id/bottom_sheet_container"',
                'id/background_dimmer"',
            ],
            "min_matches": 2,
            "recovery": ["back", "tap_outside"],
        },
        {
            "name": "share_bottom_sheet",
            "label": "Share bottom sheet",
            "indicators": [
                'id/bottom_sheet_container"',
                'text="Share"',
            ],
            "min_matches": 2,
            "recovery": ["back"],
        },
        {
            "name": "dialog_popup",
            "label": "Dialog / alert popup",
            "indicators": [
                'resource-id="android:id/alertTitle"',
                'resource-id="android:id/button1"',
            ],
            "min_matches": 1,
            "recovery": ["back"],
        },
        {
            "name": "rate_limit_popup",
            "label": "Rate limit warning",
            "indicators": [
                'text="Try Again Later"',
                'text="R\u00e9essayer plus tard"',
                'text="Action Blocked"',
            ],
            "min_matches": 1,
            "recovery": ["ok_button", "back"],
        },
        {
            "name": "login_required",
            "label": "Login screen detected",
            "indicators": [
                'text="Log in"',
                'text="Se connecter"',
                'content-desc="Instagram from Meta"',
            ],
            "min_matches": 2,
            "recovery": [],
        },
        {
            "name": "generic_bottom_sheet",
            "label": "Bottom sheet overlay",
            "indicators": [
                'id/bottom_sheet_container"',
            ],
            "min_matches": 1,
            "recovery": ["back", "swipe_down"],
        },
    ])

    visible_text_regex: str = r'text="([^"]{2,80})"'
    clickable_button_regexes: List[str] = field(default_factory=lambda: [
        r'<[^>]*(?:Button|button)[^>]*text="([^"]+)"[^>]*clickable="true"',
        r'<[^>]*clickable="true"[^>]*(?:Button|button)[^>]*text="([^"]+)"',
    ])
    screen_summary_signatures: Dict[str, List[str]] = field(default_factory=lambda: {
        "Comments page": ['text="Comments"', 'text="Commentaires"'],
        "Followers list": ['text="Followers"', 'text="Abonn\u00e9s"'],
        "Following list": ['text="Following"', 'text="Abonnements"'],
        "Home feed": ['content-desc="Home"', 'content-desc="Accueil"'],
    })
    ok_button_texts: List[str] = field(default_factory=lambda: [
        "OK",
        "Ok",
        "Dismiss",
        "Fermer",
        "Got it",
    ])

    def clickable_text_selector(self, text: str) -> str:
        """Build a clickable exact-text selector for recovery buttons."""
        return f'//*[@text="{text}" and @clickable="true"]'


WATCHDOG_SELECTORS = WatchdogSelectors()
