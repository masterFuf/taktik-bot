"""Interact with a hand-picked LIST of TikTok profiles — with the profiles themselves.

Same reading Instagram's `profile_list` workflow already implements: until now the only thing
TikTok could do with a list of accounts was engage THEIR followers — the picked accounts were
sources, never targets. This workflow is the other reading of the same selection: go to each
picked profile and interact with that person.

The only thing that differs from the followers workflow is where the usernames come from: a list
the operator chose, not a list TikTok scrolled for us. So everything downstream is the production
path, unchanged — `_process_current_profile` (extract → save → filter → interact → follow), the
same `FollowersStats` shape (so the live panel, the bridge stats and the session finalisation all
keep working), the same skip policy, the same filters. No second interaction engine.

Three things the followers loop does are deliberately absent, because they answer questions a
chosen list does not ask: there is no scrolling (the list is finite and already known), no
"consecutive known usernames" stop (that policy exists to detect a list we have already walked
through — here the operator decided what is in it), and no recovery-by-restart onto a list
screen, since each profile is reached on its own from the home tab.
"""

import time
from dataclasses import dataclass, field
from typing import List, Optional

from taktik.core.social_media.tiktok.services.followers.stop_policy import normalize_username
from taktik.core.social_media.tiktok.services.navigation.reset import return_to_tiktok_home

from ..followers.models import FollowersConfig, FollowersStats
from ..followers.workflow import FollowersWorkflow


@dataclass
class TargetProfilesConfig(FollowersConfig):
    """Followers config plus the list of people to visit.

    `max_followers` keeps its meaning — a budget of profiles — so every limit, every stat and
    every progress log inherited from the followers workflow keeps reading correctly.
    """

    usernames: List[str] = field(default_factory=list)


class TargetProfilesWorkflow(FollowersWorkflow):
    """Visit each profile of a chosen list and interact with it."""

    #: A profile rejected here came from a hand-picked selection, not from anybody's followers.
    FILTER_SOURCE_TYPE = 'selection'

    MODULE_NAME = "tiktok-target-profiles-workflow"

    @property
    def _filter_source_name(self) -> str:
        return 'target_profiles'

    def __init__(self, device, config: TargetProfilesConfig):
        super().__init__(device, config)
        self.config: TargetProfilesConfig = config

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self, bot_username: str = None) -> FollowersStats:
        """Visit every username of the configured list, in order."""
        self._running = True
        self.stats = FollowersStats()
        self._processed_usernames.clear()

        targets = self._resolve_targets()

        self.logger.info(f"🚀 Starting Target Profiles workflow on {len(targets)} profiles")
        self.logger.info(
            f"📊 Config: max_profiles={self.config.max_followers}, "
            f"posts_per_profile={self.config.posts_per_profile}"
        )

        self._open_session(bot_username, targets)

        if not targets:
            self.logger.error("❌ No profile provided for the target-profiles workflow")
            self._end_session('ERROR', 'No profile provided', completion_reason='no_targets')
            return self.stats

        completion_reason = 'unknown'

        try:
            for idx, username in enumerate(targets):
                while self._paused and self._running:
                    time.sleep(1)

                if not self._running:
                    completion_reason = 'stopped_by_user'
                    break

                if self.stats.profiles_visited >= self.config.max_followers:
                    completion_reason = 'max_profiles_reached'
                    self.logger.info(f"🏁 Profile budget reached ({self.config.max_followers})")
                    break

                limit_reached = self._check_limits_reached()
                if limit_reached:
                    completion_reason = limit_reached
                    self.logger.info(f"📊 Session limit reached: {limit_reached}")
                    break

                self._handle_popups()

                self.logger.info(f"👤 Profile {idx + 1}/{len(targets)}: @{username}")

                if self._should_skip(username):
                    continue

                # Navigation, then the shared per-profile body. A failed navigation is counted
                # and skipped: it says nothing about the profiles that come after it.
                if not self._open_profile(username):
                    self.stats.errors += 1
                    self._send_action('skip_not_found', username)
                    self._recover_to_home()
                    continue

                self._process_current_profile()
                self._recover_to_home()
                self._human_delay()
                self._check_pause_needed()

            if completion_reason == 'unknown':
                completion_reason = 'list_exhausted'

            self.logger.info(
                f"✅ Target Profiles workflow completed: {self.stats.profiles_visited} profiles, "
                f"{self.stats.likes} likes, {self.stats.follows} follows (reason: {completion_reason})"
            )
            self._end_session('COMPLETED', completion_reason=completion_reason)

        except Exception as e:
            self.logger.error(f"❌ Error in Target Profiles workflow: {e}")
            self.stats.errors += 1
            self._end_session('ERROR', str(e))

        return self.stats

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def _resolve_targets(self) -> List[str]:
        """Normalised, de-duplicated usernames, in the order the operator gave them."""
        targets: List[str] = []
        seen = set()
        for raw in self.config.usernames or []:
            username = str(raw or '').strip().lstrip('@').strip()
            key = normalize_username(username)
            if username and key not in seen:
                seen.add(key)
                targets.append(username)
        return targets

    def _open_session(self, bot_username: Optional[str], targets: List[str]) -> None:
        """Open the DB session, under its own workflow type.

        Filed as `target_profiles`, never as `followers`: the two answer different questions and
        a shared type would merge them in every grouping the app does on that column.
        """
        if not bot_username:
            return
        try:
            session_ref = self._followers_repository.create_session(
                bot_username=bot_username,
                target=f"{len(targets)} profiles",
                config_used=self.config.to_dict() if hasattr(self.config, 'to_dict') else None,
                workflow_type='target_profiles',
                session_name='Target Profiles',
            )
            self._account_id = session_ref.account_id
            self._session_id = session_ref.session_id
            self.logger.info(f"📊 Database session created: {self._session_id}")
        except Exception as e:
            self.logger.warning(f"Failed to initialize database tracking: {e}")

    def _should_skip(self, username: str) -> bool:
        """Was this profile already handled recently BY THIS ACCOUNT?

        The same DB checks the followers loop runs before tapping a row, run here before any
        navigation — so a skip costs neither a screen nor an AI call. Each reason keeps its own
        counter: mixing "we already did this one" with "we rejected this one" is what makes a
        run's reject stats unreadable.
        """
        key = normalize_username(username)
        if key and key in self._processed_usernames:
            self.logger.debug(f"Skipping @{username} — already handled in this run")
            return True
        if key:
            self._processed_usernames.add(key)

        if not self._account_id:
            return False

        try:
            if self._followers_repository.has_recent_interaction(
                account_id=self._account_id, username=username, hours=168,
            ):
                self.stats.skipped += 1
                self._send_stats_update()
                self._send_action('skip_already_interacted', username)
                self.logger.info(f"⏭️ @{username} skipped — already interacted in the past 7 days")
                return True
        except Exception as e:
            self.logger.debug(f"Error checking interaction history for @{username}: {e}")

        if self.config.filters:
            try:
                if self._followers_repository.is_profile_filtered(
                    account_id=self._account_id, username=username,
                ):
                    self.stats.profiles_filtered += 1
                    self._send_stats_update()
                    self._send_action('skip_filtered', username)
                    self.logger.info(f"⏭️ @{username} skipped — already rejected by the filters")
                    return True
            except Exception as e:
                self.logger.debug(f"Error checking filter history for @{username}: {e}")

        return False

    def _open_profile(self, username: str) -> bool:
        """Search the handle and open THAT profile.

        The atomic verifies the profile it landed on actually belongs to `username`, which is
        what makes a hand-picked list safe: the Users tab also lists fan accounts carrying the
        searched handle as their display name.
        """
        try:
            return bool(self.navigation.navigate_to_user_profile(username))
        except Exception as e:
            self.logger.warning(f"Error opening @{username}: {e}")
            return False

    def _recover_to_home(self) -> None:
        """Back to a neutral screen before searching the next handle."""
        try:
            return_to_tiktok_home(self.device, logger=self.logger)
        except Exception as e:
            self.logger.debug(f"Could not return to home: {e}")
