"""Which cold DM recipients to leave alone, decided on what their profile screen shows.

Two settings of the cold DM page and of the scheduler's DM node, « Ignorer les comptes privés » and
« Ignorer les comptes certifiés », travelled to the bridge and were read by nobody: a private
profile was always skipped, whatever the operator said, and the certified badge was never looked
at. The decision lives here, free of any device, so the bridge only has to read the screen and
ask.

The defaults are the behaviour the bridge had before the settings were read: private profiles
skipped, certified ones not.

A private profile that the operator does NOT want skipped is tried like any other: with the
Message button of its header, or, without one, from the inbox's « Nouveau message » picker, the
opening the welcome DM takes too (`MessagingBusiness.open_conversation_from_profile`). Until
2026-10-24 it was skipped without a button (`private_no_message_button`), for want of that way.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

SKIP_VERIFIED = "verified"
SKIP_PRIVATE = "private"

#: Every reason that means « a private profile, left alone ».
PRIVATE_SKIP_REASONS = (SKIP_PRIVATE,)


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
) -> Optional[str]:
    """Why this profile gets no cold DM, or None when it should get one.

    A profile without a Message button, public or private, is no skip: the opening writes to it
    from the inbox's new-message picker, and says when that fails too.
    """
    if policy.skip_verified and is_verified:
        return SKIP_VERIFIED
    if is_private and policy.skip_private:
        return SKIP_PRIVATE
    return None


__all__ = [
    "ColdDmRecipientPolicy",
    "PRIVATE_SKIP_REASONS",
    "SKIP_PRIVATE",
    "SKIP_VERIFIED",
    "cold_dm_skip_reason",
]
