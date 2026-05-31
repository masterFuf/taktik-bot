"""Selector catalog for YouTube account management surfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, NamedTuple

from taktik.core.social_media.youtube.ui.selectors.upload import YOUTUBE_PACKAGE


YOUTUBE_HOME_ACTIVITY = (
    "com.google.android.youtube/"
    ".app.honeycomb.Shell$HomeActivity"
)


class UiSelector(NamedTuple):
    """A uiautomator2 selector expressed without leaking UI strings to workflows."""

    kind: Literal["resourceId", "description", "text"]
    value: str


@dataclass(frozen=True)
class AccountSelectors:
    """Selectors for YouTube account switcher and launch popups."""

    launch_popup_close: tuple[UiSelector, ...] = field(
        default_factory=lambda: (
            UiSelector(
                "resourceId",
                "com.android.permissioncontroller:id/permission_deny_button",
            ),
            UiSelector(
                "resourceId",
                f"{YOUTUBE_PACKAGE}:id/custom_confirm_dialog_cancel_button",
            ),
            UiSelector("resourceId", f"{YOUTUBE_PACKAGE}:id/close_button"),
            UiSelector("resourceId", f"{YOUTUBE_PACKAGE}:id/dismiss_button"),
            UiSelector("resourceId", f"{YOUTUBE_PACKAGE}:id/cancel_button"),
            UiSelector("description", "Close"),
            UiSelector("description", "Dismiss"),
            UiSelector("description", "Not now"),
            UiSelector("text", "No thanks"),
            UiSelector("text", "Non merci"),
            UiSelector("text", "Not now"),
            UiSelector("text", "Skip"),
            UiSelector("text", "Cancel"),
            UiSelector("text", "Close"),
            UiSelector("text", "Ne pas autoriser"),
            UiSelector("text", "Don't allow"),
        )
    )

    account_button_queries: tuple[str, ...] = field(
        default_factory=lambda: (
            'content-desc*="Account"',
            'content-desc*="Compte"',
            f'resource-id="{YOUTUBE_PACKAGE}:id/account_icon_layout"',
            f'resource-id="{YOUTUBE_PACKAGE}:id/avatar"',
        )
    )

    def account_button_queries_for_email(self, email: str) -> tuple[str, ...]:
        """Return account avatar queries, preferring the target account identity."""
        return (f'content-desc*="{email}"', *self.account_button_queries)

    def account_entry_for_email(self, email: str) -> UiSelector:
        """Return the visible account row selector for the target Google identity."""
        return UiSelector("text", email)


ACCOUNT_SELECTORS = AccountSelectors()
