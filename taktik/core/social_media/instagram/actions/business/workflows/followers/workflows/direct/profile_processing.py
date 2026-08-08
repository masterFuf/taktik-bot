"""Process a single follower profile: click → extract → filter → interact."""

from typing import Dict, Any, Optional

from ......core.base_business.profile_processing import ProfileProcessingResult


class DirectProfileProcessingMixin:
    """Mixin: _process_single_follower_direct — handle one profile from the followers list."""

    #: Was the profile just VISITED a private one? Read by the main loop to keep its
    #: consecutive-private streak, which is what detects a poisoned head of list.
    #:
    #: Carried on the instance rather than returned, on purpose: the return value is a
    #: three-state contract (interacted / skipped / unrecoverable) that several callers
    #: already branch on, and widening it to carry a filter reason would change all of
    #: them to answer a question only one of them asks. `None` means "no visit happened",
    #: which is NOT the same as "the visit found a public profile" — a skip that never
    #: opened a profile must leave the streak untouched.
    _last_visit_was_private = None

    def _process_single_follower_direct(
        self, username, idx, stats, interaction_config, account_id,
        target_username, target_followers_count, total_usernames_seen,
        max_interactions, tracker
    ):
        """
        Process a single follower: click profile → extract info → filter → interact.

        Returns:
            True if interaction happened, False if skipped/filtered, None if critical error (can't recover)
        """
        self._last_visit_was_private = None
        # === Skip niveau-LISTE (le moins cher de tous) ===
        # La LIGNE du follower montre deja notre relation via son bouton (Suivre / Suivi(e) / Suivre
        # en retour), lisible SANS ouvrir le profil. Si une relation existe et que l'operateur veut
        # la skipper, on skip ICI : zero navigation, zero extraction, zero appel IA. C'est un
        # court-circuit du garde-fou niveau-profil (_process_profile_on_screen), qui reste la source
        # de verite. FAIL-OPEN : une ligne illisible ('unknown', ex. derniere ligne partiellement
        # scrollee) retombe sur le clic + le garde-fou profil -> jamais de cible valide perdue.
        fc = interaction_config.get('filter_criteria', interaction_config.get('filters', {})) or {}
        if fc.get('skip_follows_us') or fc.get('skip_already_following'):
            row_state = self.detection_actions.get_row_follow_state(username)
            reason = None
            if fc.get('skip_follows_us') and row_state == 'follow_back':
                reason = 'Already follows us'
            elif fc.get('skip_already_following') and row_state in ('following', 'requested'):
                reason = 'Already followed by us'
            if reason:
                self.logger.info(f"🤝 @{username} ignoré (liste, sans ouvrir le profil) — {reason}")
                self.stats_manager.increment('relationship_skipped')
                # Enregistrer comme filtre pour que is_profile_skippable le saute aux passes suivantes
                # (jamais revisiter) — meme voie que le skip niveau-profil.
                self._record_filtered_in_db(
                    username, reason, 'FOLLOWER', target_username, account_id, self._get_session_id()
                )
                return False

        # Progress info
        profiles_clicked = stats.get('profiles_clicked', 0) + 1
        stats['profiles_clicked'] = profiles_clicked
        progress_info = f"[{stats['interacted']}/{max_interactions} interactions, {profiles_clicked} visited]"
        if target_followers_count > 0:
            progress_pct = (total_usernames_seen / target_followers_count) * 100
            progress_info += f" ({progress_pct:.1f}% of {target_followers_count:,} followers scanned)"
        self.logger.info(f"{progress_info} 👆 Clicking on @{username}")
        
        # Cliquer sur le profil dans la liste
        if not self.detection_actions.click_follower_in_list(username):
            self.logger.warning(f"Could not click on @{username}")
            stats['errors'] += 1
            return False
        
        self._human_like_delay('navigation')

        # WAIT for the profile to LOAD before deciding. On a slow / tethered connection the profile
        # page takes several seconds; a single immediate check would wrongly conclude "not a profile"
        # and skip the follower (mislabelled as filtered). This is exactly the case where 17/20
        # profiles got skipped without ever loading.
        if not self.detection_actions.wait_for_profile_screen(timeout=8.0):
            self.logger.warning(f"Profile did not load after clicking @{username} (slow connection?)")
            if not self._ensure_on_followers_list(target_username):
                return None  # Critical
            stats['errors'] += 1
            return False
        
        # Profile screen loaded. The VISIT counters are incremented after the filter branches
        # below, so the live panel and the persisted stats share one semantic ("profiles
        # actually processed") — counting here made the hub show +56% vs the final card
        # (opened-but-filtered profiles were live-counted but never DB-recorded).
        # profile_visit IPC is emitted centrally in _process_profile_on_screen.
        tracker.log_profile_visit(username, idx, already_in_db=False)
        
        # === UNIFIED PROFILE PROCESSING ===
        session_id = self._get_session_id()
        result = self._process_profile_on_screen(
            username, interaction_config,
            source_type='FOLLOWER', source_name=target_username,
            account_id=account_id, session_id=session_id
        )
        
        # --- Handle result with followers-specific extras ---
        
        if result.was_error:
            stats['errors'] += 1
            if not self._ensure_on_followers_list(target_username, force_back=True):
                return None  # Critical
            return False
        
        if result.was_private:
            self._last_visit_was_private = True
            stats['skipped'] += 1
            tracker.log_profile_filtered(username, "Private profile", result.profile_data)
            if not self._ensure_on_followers_list(target_username, force_back=True):
                return None  # Critical
            return False
        
        if result.was_filtered:
            # A profile rejected for "too few posts" is PUBLIC — we could read its posts.
            # It therefore proves we are out of the private zone and must clear the streak,
            # exactly like a profile we interacted with.
            self._last_visit_was_private = False
            stats['filtered'] += 1
            tracker.log_profile_filtered(username, ', '.join(result.filter_reasons), result.profile_data)
            if not self._ensure_on_followers_list(target_username, force_back=True):
                return None  # Critical
            return False

        # Profile passed the filters — THIS is a visit in the persisted sense (the DB records
        # PROFILE_VISIT for processed profiles only, probability-skipped included).
        self._last_visit_was_private = False
        stats['visited'] += 1
        self.stats_manager.increment('profiles_visited')

        # --- Interaction happened or skipped by probability ---
        # Action counters (likes/follows/stories/story likes/comments) are NOT added here:
        # the interaction engine now moves them as each gesture lands, so the desktop live
        # panel ticks in real time instead of jumping by the profile's total. Adding them
        # again here would double-count. Only the local run tallies are accumulated.
        if result.actually_interacted:
            if result.likes > 0:
                stats['liked'] += result.likes
            if result.follows > 0:
                stats['followed'] += 1
            if result.stories > 0:
                stats['stories_viewed'] += result.stories
            if result.stories_liked > 0:
                stats['story_likes'] += result.stories_liked
            if result.comments > 0:
                # No alias key exists for comments (unlike liked/followed): increment the
                # canonical key directly. This was the only action missing from the local
                # tally, which is why every end-of-run summary showed comments_made=0.
                stats['comments_made'] += result.comments


            stats['interacted'] += 1
            stats['processed'] += 1
            self.stats_manager.increment('profiles_interacted')
            self.human.record_interaction()
            tracker.log_profile_interacted(username, {
                'liked': result.likes > 0,
                'followed': result.follows > 0,
                'story_viewed': result.stories > 0,
                'commented': result.comments > 0
            })
            
            if self.session_manager:
                self.session_manager.record_profile_processed()
            
            return True
        else:
            stats['skipped'] += 1
            return False
