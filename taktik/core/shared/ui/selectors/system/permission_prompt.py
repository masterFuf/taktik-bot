"""Android's runtime-permission prompt ("Allow <app> to take pictures and record video?").

Drawn by Android's permission controller, not by the app that asks. Matched by ids only: they
come from the framework and do not change with the phone language.

Dumps: Pixel 3a, Android 12 in French, over Instagram 410.0.0.53.71 (the story camera asks for
the camera, then the microphone). The window's package is `com.google.android.permissioncontroller`
while its ids carry `com.android.permissioncontroller`: both prefixes are accepted. Android 9 hosts
the prompt in `com.android.packageinstaller`, with no "only this time" choice; it is recognised so
that such a phone fails clearly.

Each id is matched with `substring-after` and `starts-with`, never with an `@resource-id="..."`
equality: the clone proxy rewrites every equality into a package-agnostic match, which would let
an app's own `permission_message` pass for Android's. Written this way a selector means the same
through the proxy and without it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

CONTROLLER_PACKAGES: Tuple[str, ...] = (
    "com.android.permissioncontroller",
    "com.google.android.permissioncontroller",
)
INSTALLER_PACKAGES: Tuple[str, ...] = ("com.android.packageinstaller",)


def system_id_xpath(token: str, owners: Sequence[str]) -> str:
    """The node whose id is `<owner>:id/<token>` for one of `owners`."""
    owned = " or ".join(f'starts-with(@resource-id, "{owner}:id/")' for owner in owners)
    return f'//*[substring-after(@resource-id, ":id/")="{token}" and ({owned})]'


_ANY_OWNER = CONTROLLER_PACKAGES + INSTALLER_PACKAGES


@dataclass(frozen=True)
class PermissionPromptSelectors:
    # The prompt: its window, or its question.
    prompt: Tuple[str, ...] = tuple(
        system_id_xpath(token, _ANY_OWNER)
        for token in ("grant_dialog", "grant_singleton", "permission_message")
    )
    # The question asked, read for the logs.
    message: Tuple[str, ...] = (system_id_xpath("permission_message", _ANY_OWNER),)
    # "Only this time": the only answer the bot gives. Android 11+ only.
    allow_one_time: Tuple[str, ...] = (
        system_id_xpath("permission_allow_one_time_button", CONTROLLER_PACKAGES),
    )

    def all_xpaths(self) -> Tuple[str, ...]:
        return self.prompt + self.message + self.allow_one_time


PERMISSION_PROMPT_SELECTORS = PermissionPromptSelectors()

__all__ = [
    "CONTROLLER_PACKAGES",
    "INSTALLER_PACKAGES",
    "PERMISSION_PROMPT_SELECTORS",
    "PermissionPromptSelectors",
    "system_id_xpath",
]
