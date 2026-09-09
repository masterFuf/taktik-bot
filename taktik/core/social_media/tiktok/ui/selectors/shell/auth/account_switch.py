"""Selectors for TikTok's native signed-in account switcher.

The Python defaults are the official TikTok 43.1.4 hierarchy captured on a
Galaxy A11. Newer resource IDs are supplied by the compatibility override
catalog, while package-agnostic suffix matches keep cloned packages working.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class AccountSwitchSelectors:
    profile_switcher_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@resource-id, ":id/qf8")]',
        '//android.widget.Button[contains(@resource-id, ":id/qh5")]/'
        'preceding::android.widget.Button[@clickable="true"][1]',
    ])
    profile_username: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@resource-id, ":id/qh5")]',
    ])
    switcher_indicator: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/nmh")]',
        '//*[@text="Switch account" or @content-desc="Switch account"]',
    ])
    account_rows: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@resource-id, ":id/k5o")]',
        '//*[@content-desc="Bottom sheet"]//android.widget.Button['
        '@clickable="true" and @content-desc!="" and @content-desc!="Close"]',
    ])
    username_labels: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ljk")]',
    ])
    active_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/en4")]',
        '//*[@content-desc="Checkmark"]',
    ])
    close_button: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Bottom sheet"]//*[@content-desc="Close"]',
        '//*[@content-desc="Close"]',
    ])
    post_switch_prompt_dismiss: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Dialog" or contains(@resource-id, ":id/visual_area")]'
        '//android.widget.Button[@text="Not now" or @content-desc="Not now"]',
        '//android.widget.Button[@text="Not now" or @content-desc="Not now"]',
    ])
    account_row_templates: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@resource-id, ":id/k5o") and '
        'translate(@content-desc, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", '
        '"abcdefghijklmnopqrstuvwxyz")="{username}"]',
        '//*[@content-desc="Bottom sheet"]//android.widget.Button['
        'translate(@content-desc, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", '
        '"abcdefghijklmnopqrstuvwxyz")="{username}"]',
    ])

    def account_row(self, username: str) -> List[str]:
        """Exact native row for a validated, normalized TikTok username."""
        return [template.format(username=username) for template in self.account_row_templates]


ACCOUNT_SWITCH_SELECTORS = AccountSwitchSelectors()

__all__ = ["ACCOUNT_SWITCH_SELECTORS", "AccountSwitchSelectors"]
