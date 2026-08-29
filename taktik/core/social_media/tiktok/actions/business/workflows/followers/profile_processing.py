"""What we do once we are standing on somebody's profile.

Extracted from the followers loop rather than written next to it. The followers workflow reaches
a profile by tapping a row; the target-profiles workflow reaches it by searching a handle the
operator typed. Everything AFTER that — read, count the visit, filter, interact, maybe follow —
is the same work, and it must stay the same work: two copies would drift, and the copy that
drifts is the one that stops recording interactions or stops honouring the follow cap.

So the loops own where the profile comes from, and this mixin owns what happens there.
"""

import random
import time

from taktik.core.shared.telemetry.sink import emit_step


class ProfileProcessingMixin:
    """The per-profile body shared by the followers and target-profiles workflows."""

    def _process_current_profile(self) -> None:
        """Interact with the profile currently on screen.

        Assumes navigation already happened and does NOT return anywhere — the caller owns
        getting back to wherever it came from, because a followers list and a search page are
        not returned to the same way.
        """
        self._current_profile_username = self._get_current_profile_username()
        self.stats.profiles_visited += 1
        self._send_stats_update()

        # Heartbeat: attribute the per-profile processing time (extract → browse posts
        # → interact → follow) in the cadence/run log.
        _username = self._current_profile_username
        _likes0 = getattr(self.stats, 'likes', 0)
        _follows0 = getattr(self.stats, 'follows', 0)
        _t0 = time.time()
        emit_step("analysis", action="start", target=_username)
        try:
            # Extract and save profile data (followers, likes, bio, etc.)
            profile_data = self._extract_and_save_profile_data()

            # Send profile visit action for Live Activity
            self._send_action('profile_visit', self._current_profile_username)

            self.logger.info(
                f"👤 Visiting profile @{self._current_profile_username} "
                f"({self.stats.profiles_visited}/{self.config.max_followers})"
            )

            # Filters, applied on what was just read rather than on a second reading. A
            # rejection skips the interactions -- but NOT the caller's return trip, without
            # which the next iteration would look for rows on a profile screen.
            if not self._filter_current_profile(profile_data):
                # Interact with posts on this profile
                self._interact_with_profile_posts()

                # Optionally follow this user
                if random.random() < self.config.follow_probability:
                    if self.stats.follows < self.config.max_follows_per_session:
                        self._try_follow_current_profile()
        finally:
            _acted = (getattr(self.stats, 'likes', 0) > _likes0
                      or getattr(self.stats, 'follows', 0) > _follows0)
            emit_step("analysis", action="done", target=_username,
                      duration_ms=int((time.time() - _t0) * 1000),
                      outcome="interacted" if _acted else "watched")
