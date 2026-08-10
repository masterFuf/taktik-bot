"""Shared base class for workflows that interact with likers from a popup list.

Used by HashtagBusiness and PostUrlBusiness — both follow the same pattern:
1. Open a likers popup (from a post)
2. Iterate visible likers: click → visit profile → filter → interact → back
3. Scroll for more likers

This avoids ~300 lines of duplicated code between hashtag.py and post_url.py.
"""

import time
from typing import Dict, Any, Optional, List, Set
from loguru import logger

from ....core.base_business import BaseBusinessAction
from ....core.base_business.profile_processing import ProfileProcessingResult
from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService
from taktik.core.shared.telemetry import emit_step
from taktik.core.social_media.instagram.actions.core.ipc import IPCEmitter
from .revisit_policy import RevisitPolicy
from .list_sources import InteractionListSource, make_likers_source


class LikersWorkflowBase(BaseBusinessAction):
    """Base class for workflows that interact with profiles from a likers popup."""

    # ─── Main interaction loop ───────────────────────────────────────────

    def _interact_with_likers_list(
        self,
        stats: Dict[str, Any],
        effective_config: Dict[str, Any],
        max_interactions: int,
        source_type: str,
        source_name: str,
        max_scroll_attempts: int = 50,
        list_source: Optional[InteractionListSource] = None,
    ) -> None:
        """
        Shared interaction loop for the people gathered around a post.

        Iterates the visible rows, clicks each one, visits the profile, applies filters,
        performs interactions, and returns to the list.

        Args:
            stats: Mutable stats dict (updated in place)
            effective_config: Merged workflow config
            max_interactions: Target number of successful interactions
            source_type: 'HASHTAG' or 'POST_URL' (for DB recording)
            source_name: e.g. '#travel' or 'https://instagram.com/p/...'
            max_scroll_attempts: Max scroll attempts before giving up
            list_source: WHERE the rows come from — the likers sheet (default, historical
                behaviour) or the comments thread. Only the row plumbing differs; everything
                downstream of the click is identical.
        """
        source = list_source or make_likers_source(self)
        processed_usernames: Set[str] = set()
        scroll_attempts = 0
        consecutive_empty = 0
        known_usernames_streak = 0
        max_consecutive_known_usernames = effective_config.get('max_consecutive_known_usernames')
        if max_consecutive_known_usernames is not None:
            max_consecutive_known_usernames = max(1, int(max_consecutive_known_usernames or 1))

        # Operator-set revisit delays for THIS account (interaction cooldown + filter expiry).
        revisit_policy = RevisitPolicy.from_filters(
            effective_config.get('filter_criteria', effective_config.get('filters', {}))
        )

        account_id = getattr(self.automation, 'active_account_id', None) if self.automation else None
        session_id = getattr(self.automation, 'current_session_id', None) if self.automation else None

        def _ledger(uname: str, outcome: str, reason: Optional[str] = None, **extra) -> None:
            """One audit entry per UNIQUE encountered user → its outcome + reason. The
            full ledger lets us verify we saw everyone and that every skip was intended."""
            emit_step(
                "follower_decision", action=outcome, target=uname,
                reason=reason, encounter_order=stats['users_found'],
                source_type=source_type, **extra,
            )

        while stats['users_interacted'] < max_interactions and scroll_attempts < max_scroll_attempts:
            # Check session limits
            if self.session_manager:
                should_continue, stop_reason = self.session_manager.should_continue()
                if not should_continue:
                    self.logger.warning(f"🛑 Session stopped: {stop_reason}")
                    break

            # Get the visible rows (likers sheet or comments thread)
            visible_likers = source.get_visible()

            if not visible_likers:
                consecutive_empty += 1
                popup_open = source.is_open()
                # WRONG SCREEN: tapping a REEL's like count can drop us into the full-screen clips/
                # Reels viewer instead of the likers list, and the popup then never opens no matter
                # how much we scroll. Detect it (likers-popup indicators absent for a couple of
                # cycles — tolerates a slow-loading popup) and LEAVE this post instead of scrolling
                # into the void (a real run wasted ~40s / 50 scrolls stuck on a reel viewer).
                if not popup_open and consecutive_empty >= 2:
                    self.logger.warning(f"{source.label} list not open after retries (wrong screen, e.g. reel/clips viewer) — leaving this post")
                    source.exit_wrong_screen()
                    break
                # List IS open but shows nothing more after several scrolls → end of the list.
                if popup_open and consecutive_empty >= 4:
                    self.logger.debug(f"No more {source.label} after several scrolls — end of list")
                    break
                self.logger.debug(f"No visible {source.label} found on screen")
                scroll_attempts += 1
                source.scroll()
                self._human_like_delay('scroll')
                continue

            consecutive_empty = 0
            new_likers_found = False

            for liker_data in visible_likers:
                username = liker_data['username']

                if username in processed_usernames:
                    continue

                processed_usernames.add(username)
                new_likers_found = True
                stats['users_found'] += 1

                # DB skip check
                should_skip, skip_reason = InstagramWorkflowStateService.is_profile_skippable(
                    username, account_id,
                    hours_limit=revisit_policy.reinteraction_hours,
                    filtered_max_age_days=revisit_policy.filtered_max_age_days,
                )
                if should_skip:
                    known_usernames_streak += 1
                    # "Already known" is its OWN outcome — not a this-session rejection, so it
                    # must NOT land in skipped/profiles_filtered (mirror of the followers fix).
                    # Dedicated buckets + action="already_known" telemetry + a live SkippedProfileCard
                    # keep it separate and visible everywhere it is tallied.
                    if skip_reason == "already_processed":
                        self.logger.info(f"🔄 @{username} already processed")
                        stats['already_processed'] += 1
                    elif skip_reason == "already_filtered":
                        self.logger.info(f"🚫 @{username} already filtered")
                        stats['already_filtered'] += 1
                    _ledger(username, "already_known", skip_reason or "db_skip", streak=known_usernames_streak)
                    skip_detail = InstagramWorkflowStateService.get_skip_detail(
                        username, account_id, skip_reason
                    )
                    IPCEmitter.emit_profile_skipped(
                        username, reason=skip_reason or "already in DB", detail=skip_detail
                    )

                    if (
                        max_consecutive_known_usernames is not None
                        and known_usernames_streak >= max_consecutive_known_usernames
                    ):
                        stop_reason = (
                            f"No new followers after {max_consecutive_known_usernames} known usernames in a row "
                            f"({stats['users_found']} seen)"
                        )
                        stats['stop_reason'] = stop_reason
                        self.logger.info(
                            f"🏁 No new followers discovered after {max_consecutive_known_usernames} known usernames in a row "
                            f"(seen {stats['users_found']:,} usernames)"
                        )
                        return

                    continue
                known_usernames_streak = 0

            # === LIST-level skip (the cheapest) — same mechanics as the followers path ===
            # The likers sheet is the same unified follow-list component: each row carries
            # an action button whose state is readable WITHOUT opening the profile.
            # FAIL-OPEN: an unreadable row falls through to the click plus the
            # profile-level guard, which stays the source of truth.
                fc = effective_config.get('filter_criteria', effective_config.get('filters', {})) or {}
                if fc.get('skip_follows_us') or fc.get('skip_already_following'):
                    row_state = source.row_follow_state(username)
                    rel_reason = None
                    if fc.get('skip_follows_us') and row_state == 'follow_back':
                        rel_reason = 'Already follows us'
                    elif fc.get('skip_already_following') and row_state in ('following', 'requested'):
                        rel_reason = 'Already followed by us'
                    if rel_reason:
                        self.logger.info(f"🤝 @{username} ignoré (liste, sans ouvrir le profil) — {rel_reason}")
                        self.stats_manager.increment('relationship_skipped')
                    # Record it as filtered: the skip check will catch it on later passes
                    # (never revisit) — the same route as the profile-level skip.
                        self._record_filtered_in_db(
                            username, rel_reason, source_type, source_name, account_id, session_id
                        )
                        _ledger(username, "filtered", "relationship")
                        continue

                # Click on profile
                self.logger.info(
                    f"[{stats['users_interacted']}/{max_interactions}] 👆 Clicking on @{username}"
                )

                if not source.click(username, liker_data.get('element')):
                    self.logger.warning(f"Could not click on @{username}")
                    stats['errors'] += 1
                    _ledger(username, "error", "click_failed")
                    continue

                self._human_like_delay('click')

                # WAIT for the profile to LOAD (slow/tethered connections take seconds); a single
                # immediate check would wrongly skip a still-loading profile.
                if not self.detection_actions.wait_for_profile_screen(timeout=8.0):
                    self.logger.warning(f"Profile did not load after clicking @{username} (slow connection?)")
                    _ledger(username, "error", "profile_screen_missing")
                    if not source.ensure_open():
                        self.logger.error(f"Could not recover to the {source.label} list, stopping")
                        break
                    stats['errors'] += 1
                    continue

                # === UNIFIED PROFILE PROCESSING ===
                result = self._process_profile_on_screen(
                    username, effective_config,
                    source_type=source_type, source_name=source_name,
                    account_id=account_id, session_id=session_id
                )

                if result.was_error:
                    stats['errors'] += 1
                    _ledger(username, "error", "processing_error")
                    if not source.ensure_open(force_back=True):
                        self.logger.error(f"Could not recover to the {source.label} list, stopping")
                        break
                    continue

                if result.was_private:
                    stats['skipped'] += 1
                    _ledger(username, "skipped", "private")
                    if not source.ensure_open(force_back=True):
                        self.logger.error(f"Could not recover to the {source.label} list, stopping")
                        break
                    continue

                if result.was_filtered:
                    stats['profiles_filtered'] += 1
                    _ledger(username, "filtered", "filter_criteria",
                            filters=getattr(result, "filter_reasons", None))
                    if not source.ensure_open(force_back=True):
                        self.logger.error(f"Could not recover to the {source.label} list, stopping")
                        break
                    continue

                if result.actually_interacted:
                    stats['users_interacted'] += 1
                    stats['likes_made'] += result.likes
                    stats['follows_made'] += result.follows
                    stats['comments_made'] += result.comments
                    stats['stories_watched'] += result.stories
                    stats['stories_liked'] += result.stories_liked

                    self._update_stats_from_interaction_result(
                        username, result.interaction_result, account_id, session_id
                    )
                    self.stats_manager.display_stats(current_profile=username)
                    _ledger(username, "interacted", None,
                            likes=result.likes, follows=result.follows,
                            comments=result.comments, stories=result.stories,
                            stories_liked=result.stories_liked)
                else:
                    stats['skipped'] += 1
                    _ledger(username, "skipped", "no_interaction")

                # Return to likers list
                if not source.ensure_open(force_back=True):
                    self.logger.error(f"Could not return to the {source.label} list, stopping")
                    break

                # Check if target reached
                if stats['users_interacted'] >= max_interactions:
                    self.logger.info(
                        f"✅ Reached target of {max_interactions} successful interactions"
                    )
                    break

                self._human_like_delay('interaction_gap')

            # Scroll if no new likers found
            if not new_likers_found:
                scroll_attempts += 1
                source.scroll()
                self._human_like_delay('scroll')
            else:
                scroll_attempts = 0

    # ─── Liker extraction from current post ─────────────────────────────

    def _extract_likers_from_current_post(self, is_reel: bool = None, max_interactions: int = None) -> list:
        """Extract likers from the currently displayed post (regular or reel).
        Shared by HashtagBusiness and PostUrlBusiness."""
        try:
            if is_reel is None:
                is_reel = self._is_reel_post()

            if is_reel:
                self.logger.debug("Reel post detected")
                return self._extract_likers_from_reel(max_interactions=max_interactions)
            else:
                self.logger.debug("Regular post detected")
                return self._extract_likers_from_regular_post(max_interactions=max_interactions)

        except Exception as e:
            self.logger.error(f"Error extracting likers: {e}")
            return []

    # ─── Perform interactions on a single profile ────────────────────────

    def _perform_likers_interactions(
        self,
        username: str,
        config: Dict[str, Any],
        profile_data: Dict[str, Any] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Perform interactions (like, follow, story, comment) on a profile.
        Delegates to unified _perform_interactions_on_profile (BaseBusinessAction).
        """
        return self._perform_interactions_on_profile(username, config, profile_data=profile_data)

    # ─── Likers popup navigation helpers ─────────────────────────────────

    def _go_back_to_likers_list(self) -> bool:
        """Go back to the likers list using Instagram's UI back button."""
        try:
            # Fast path: combined XPath to find any back button in 1 round-trip
            back_selectors = self.navigation_selectors.back_buttons
            combined = ' | '.join(back_selectors[:5])  # Top 5 most reliable
            try:
                element = self.device.xpath(combined)
                if element.exists:
                    element.click()
                    self.logger.debug("⬅️ Clicked Instagram back button")
                    self._human_like_delay('click')
                else:
                    # Fallback: system back (some devices may not support it)
                    self.logger.debug("⬅️ No UI back button found, using system back (fallback)")
                    self.device.press('back')
                    self._human_like_delay('click')
            except Exception:
                self.device.press('back')
                self._human_like_delay('click')

            if self._is_likers_popup_open():
                self.logger.debug("✅ Back to likers list confirmed")
                return True
            else:
                self.logger.warning("⚠️ Back clicked but not on likers list")
                return False

        except Exception as e:
            self.logger.error(f"Error going back: {e}")
            return False

    def _ensure_on_likers_popup(self, force_back: bool = False) -> bool:
        """
        Ensure we're on the likers popup. Tries up to 3 back presses.

        Args:
            force_back: If True, always press back first (use after visiting a profile)
        """
        if not force_back and self._is_likers_popup_open():
            return True

        for attempt in range(3):
            self.logger.debug(f"🔙 Back attempt {attempt + 1}/3 to return to likers popup")
            if self._go_back_to_likers_list():
                return True
            time.sleep(0.5)

        self.logger.error("❌ Could not return to likers popup after 3 attempts")
        return False

    def _scroll_likers_popup_up(self) -> bool:
        """Scroll the likers popup up to reveal more likers."""
        return self.ui_extractors.scroll_likers_popup_up(
            logger_instance=self.logger,
            is_likers_popup_open_checker=self._is_likers_popup_open,
            verbose_logs=False
        )

    def _exit_wrong_likers_screen(self) -> None:
        """Best-effort: a single back press to leave the wrong fullscreen surface we got dropped into
        (e.g. the reel/clips viewer), so the run isn't left stuck on it. Never raises."""
        try:
            self.device.press("back")
            self._human_like_delay('navigation')
        except Exception:
            pass
