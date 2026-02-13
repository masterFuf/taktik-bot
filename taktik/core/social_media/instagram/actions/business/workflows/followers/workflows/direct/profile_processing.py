"""Process a single follower profile: click → extract → filter → interact."""

from typing import Dict, Any, Optional

from ......core.ipc import IPCEmitter
from ......core.base_business.profile_processing import ProfileProcessingResult


class DirectProfileProcessingMixin:
    """Mixin: _process_single_follower_direct — handle one profile from the followers list."""

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
        
        # Vérifier qu'on est bien sur un profil
        if not self.detection_actions.is_on_profile_screen():
            self.logger.warning(f"Not on profile screen after clicking @{username}")
            if not self._ensure_on_followers_list(target_username):
                return None  # Critical
            stats['errors'] += 1
            return False
        
        # Profile successfully visited
        stats['visited'] += 1
        self.stats_manager.increment('profiles_visited')
        IPCEmitter.emit_profile_visit(username)
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
            stats['skipped'] += 1
            tracker.log_profile_filtered(username, "Private profile", result.profile_data)
            if not self._ensure_on_followers_list(target_username, force_back=True):
                return None  # Critical
            return False
        
        if result.was_filtered:
            stats['filtered'] += 1
            tracker.log_profile_filtered(username, ', '.join(result.filter_reasons), result.profile_data)
            if not self._ensure_on_followers_list(target_username, force_back=True):
                return None  # Critical
            return False
        
        # --- Interaction happened or skipped by probability ---
        if result.actually_interacted:
            if result.likes > 0:
                stats['liked'] += result.likes
                self.stats_manager.increment('likes', result.likes)
            if result.follows > 0:
                stats['followed'] += 1
                self.stats_manager.increment('follows')
            if result.stories > 0:
                stats['stories_viewed'] += result.stories
                self.stats_manager.increment('stories_watched')
            if result.stories_liked > 0:
                stats['story_likes'] += result.stories_liked
                self.stats_manager.increment('story_likes')
            
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
