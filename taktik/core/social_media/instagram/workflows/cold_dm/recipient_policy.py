"""Which cold DM recipients to leave alone, decided on what their profile screen shows.

Two settings of the cold DM page and of the scheduler's DM node, « Ignorer les comptes privés » and
« Ignorer les comptes certifiés », travelled to the bridge and were read by nobody: a private
profile was always skipped, whatever the operator said, and the certified badge was never looked
at. The decision lives here, free of any device, so the bridge only has to read the screen and
ask.

The defaults are the behaviour the bridge had before the settings were read: private profiles
skipped, certified ones not.

A private profile that the operator does NOT want skipped is only worth a try when Instagram
offers the conversation, that is when the profile shows a Message button. Without one there is
nothing to tap, and the skip is reported under its own reason so the run does not count it as a
failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

SKIP_VERIFIED = "verified"
SKIP_PRIVATE = "private"
SKIP_PRIVATE_NO_MESSAGE = "private_no_message_button"

#: Every reason that means « a private profile, left alone ».
PRIVATE_SKIP_REASONS = (SKIP_PRIVATE, SKIP_PRIVATE_NO_MESSAGE)


@dataclass(frozen=True)
class ColdDmRecipientPolicy:
    """The operator's two cold DM skip settings."""

    skip_private: bool = True
    skip_verified: bool = False


def cold_dm_skip_reason(
    policy: ColdDmRecipientPolicy,
    *,
    is_private: bool,
    is_verified: bool,
    has_message_button: bool,
) -> Optional[str]:
    """Why this profile gets no cold DM, or None when it should get one.

    A public profile without a Message button is not a skip: it is a failure the caller already
    reports as one, and turning it into a quiet skip would hide a broken selector.
    """
    if policy.skip_verified and is_verified:
        return SKIP_VERIFIED
    if is_private:
        if policy.skip_private:
            return SKIP_PRIVATE
        if not has_message_button:
            return SKIP_PRIVATE_NO_MESSAGE
    return None


__all__ = [
    "ColdDmRecipientPolicy",
    "PRIVATE_SKIP_REASONS",
    "SKIP_PRIVATE",
    "SKIP_PRIVATE_NO_MESSAGE",
    "SKIP_VERIFIED",
    "cold_dm_skip_reason",
]
