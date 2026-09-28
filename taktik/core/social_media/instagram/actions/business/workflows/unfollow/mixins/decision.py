"""The on-screen half of the unfollow decision: what the base cannot know.

The candidates come from the base (`unfollow/candidates.py`), reciprocity included: who follows us
is what the followers list says (`sync_followers_list`). Before an unfollow, the engine opens the
candidate's profile from its list row only for what the profile alone shows: verified and business
accounts. In doubt, no unfollow.

No "Follows you" badge is read: no Instagram 410 or 447 profile of the capture corpus shows one, a
mutual's included; read, it never said yes, and the mutual mode refused every candidate.
"""

import time
from typing import Any, Dict, Optional

from taktik.core.social_media.instagram.actions.core.ipc import IPCEmitter


class UnfollowDecisionMixin:
    """Mixin: checks run on the candidate's profile, opened from its row of the following list."""

    # Bounded wait for the profile to open after a tap on the row (class attribute for tests).
    profile_open_timeout = 4.0

    def _on_profile_of(self, username: str) -> bool:
        """Is the screen the profile of @username (not another one, not the list)?"""
        if not self.detection_actions.is_on_profile_screen():
            return False
        shown = (self.detection_actions.get_username_from_profile() or '').strip().lstrip('@')
        return shown.lower() == username.strip().lstrip('@').lower()

    def _wait_profile_of(self, username: str) -> bool:
        """Wait (bounded) for @username's profile after the tap on its row."""
        deadline = time.time() + self.profile_open_timeout
        while True:
            try:
                if self._on_profile_of(username):
                    return True
            except Exception:
                pass
            if time.time() >= deadline:
                return False
            time.sleep(0.5)

    def _profile_refusal(self, row: Dict[str, Any], forced: bool,
                         config: Dict[str, Any]) -> Optional[str]:
        """Open the row's profile, run the checks the base cannot, come back to the list.

        Returns None when the unfollow may go on, else the reason for NOT unfollowing:
        'profile_unreadable' (the profile did not open, or is someone else's), 'verified',
        'business'. Reciprocity takes no part: it was decided on the followers list. A
        blacklisted account is forced: no check. With no account kind to check, the profile is not
        opened at all.
        """
        if forced:
            return None
        skip_verified = bool(config.get('skip_verified', True))
        skip_business = bool(config.get('skip_business', False))
        if not (skip_verified or skip_business):
            return None

        username = row['username']
        name_element = row.get('name_element')
        if name_element is None:
            return 'profile_unreadable'
        try:
            from taktik.core.shared.behavior.tap import tap_element_human

            if not tap_element_human(self.device, name_element, logger=self.logger):
                name_element.click()
            if not self._wait_profile_of(username):
                return 'profile_unreadable'
            # A profile opened to be checked: the live panel counts them.
            IPCEmitter.emit_profile_visit(username)
            if skip_verified and self.detection_actions.is_verified_account():
                return 'verified'
            if skip_business and self.detection_actions.is_business_account():
                return 'business'
            return None
        except Exception as e:
            self.logger.debug(f"Profile check of @{username} failed: {e}")
            return 'profile_unreadable'
        finally:
            self._go_back_to_following_list()
