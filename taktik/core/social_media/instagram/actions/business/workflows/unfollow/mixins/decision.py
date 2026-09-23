"""The on-screen half of the unfollow decision: what the base cannot know.

The candidates come from the base (`unfollow/candidates.py`). Before an unfollow, the engine opens
the candidate's profile from its list row and checks what only the screen shows: the "Follows you"
badge (the modes that depend on reciprocity), and verified or business accounts. In doubt, no
unfollow.

Until 2026-09-24 this module held a decision nobody called, which reached each profile through
the search, took a missing badge as "does not follow back" ("in doubt, unfollow"), and stopped its
extraction after one scroll.
"""

import time
from typing import Any, Dict, Optional


class UnfollowDecisionMixin:
    """Mixin: checks run on the candidate's profile, opened from its row of the following list."""

    # Bounded wait for the profile to open after a tap on the row (class attribute for tests).
    profile_open_timeout = 4.0

    def _profile_follows_you(self, username: str) -> Optional[bool]:
        """Does @username follow us, read on its open profile: True, False, or None (unknown).

        The last check before an unfollow (U6, 2026-09-24): the base chose the candidate, the
        profile confirms. The badge is read through the localized `unfollow.follows_back_indicators`
        ("Follows you", "Vous suit"). None whenever the screen is not @username's profile: the
        ABSENCE of a badge proves something only on the right, loaded profile. The caller treats
        None as a doubt, and a doubt as no unfollow.
        """
        try:
            if not self._on_profile_of(username):
                return None
            return bool(self._is_element_present(self._unfollow_sel.follows_back_indicators))
        except Exception as e:
            self.logger.debug(f"Could not read the follows-you badge of @{username}: {e}")
            return None

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

    def _profile_refusal(self, row: Dict[str, Any], mode: str, forced: bool,
                         config: Dict[str, Any]) -> Optional[str]:
        """Open the row's profile, run the checks the base cannot, come back to the list.

        Returns None when the unfollow may go on, else the reason for NOT unfollowing:
        'profile_unreadable' (the profile did not open, or is someone else's), 'follows_back'
        (non-followers mode, badge shown), 'not_mutual' (mutual mode, badge absent), 'verified',
        'business'. A blacklisted account is forced: no check. With neither reciprocity to confirm
        nor account kind to check, the profile is not opened at all.
        """
        if forced:
            return None
        needs_badge = mode in ('non-followers', 'mutual')
        skip_verified = bool(config.get('skip_verified', True))
        skip_business = bool(config.get('skip_business', False))
        if not (needs_badge or skip_verified or skip_business):
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
            if needs_badge:
                follows = self._profile_follows_you(username)
                if follows is None:
                    return 'profile_unreadable'
                if mode == 'non-followers' and follows:
                    return 'follows_back'
                if mode == 'mutual' and not follows:
                    return 'not_mutual'
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
