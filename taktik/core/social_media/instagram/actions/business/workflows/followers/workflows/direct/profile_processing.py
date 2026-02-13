"""Process a single follower profile: click → extract → filter → interact."""

from typing import Dict, Any, Optional

from .....common import DatabaseHelpers


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
        
        # Emit IPC event
        try:
            from bridges.instagram.desktop_bridge import send_instagram_profile_visit
            send_instagram_profile_visit(username)
        except (ImportError, Exception):
            pass
        
        tracker.log_profile_visit(username, idx, already_in_db=False)
        
        # Extraire les infos du profil
        try:
            profile_data = self.profile_business.get_complete_profile_info(
                username=username, 
                navigate_if_needed=False
            )
            
            if not profile_data:
                self.logger.warning(f"Could not get profile data for @{username}")
                if not self._ensure_on_followers_list(target_username, force_back=True):
                    return None  # Critical
                stats['errors'] += 1
                return False
            
            # Vérifier si profil privé
            if profile_data.get('is_private', False):
                self.logger.info(f"🔒 Private profile @{username} - skipped")
                stats['skipped'] += 1
                self.stats_manager.increment('private_profiles')
                tracker.log_profile_filtered(username, "Private profile", profile_data)
                
                if account_id:
                    try:
                        DatabaseHelpers.record_filtered_profile(
                            username=username,
                            reason='Private profile',
                            source_type='FOLLOWER',
                            source_name=target_username,
                            account_id=account_id,
                            session_id=self._get_session_id()
                        )
                    except Exception:
                        pass
                
                if not self._ensure_on_followers_list(target_username, force_back=True):
                    return None  # Critical
                return False
            
            # Appliquer les filtres
            filter_criteria = interaction_config.get('filter_criteria', {})
            filter_result = self.filtering_business.apply_comprehensive_filter(
                profile_data, filter_criteria
            )
            
            if not filter_result.get('suitable', False):
                reasons = filter_result.get('reasons', [])
                self.logger.info(f"🚫 @{username} filtered: {', '.join(reasons)}")
                stats['filtered'] += 1
                self.stats_manager.increment('profiles_filtered')
                tracker.log_profile_filtered(username, ', '.join(reasons), profile_data)
                
                if account_id:
                    try:
                        DatabaseHelpers.record_filtered_profile(
                            username=username,
                            reason=', '.join(reasons),
                            source_type='FOLLOWER',
                            source_name=target_username,
                            account_id=account_id,
                            session_id=self._get_session_id()
                        )
                    except Exception as e:
                        self.logger.debug(f"Error recording filtered profile @{username}: {e}")
                
                if not self._ensure_on_followers_list(target_username, force_back=True):
                    return None  # Critical
                return False
            
            # === EFFECTUER LES INTERACTIONS ===
            interaction_result = self._perform_profile_interactions(
                username, 
                interaction_config, 
                profile_data=profile_data
            )
            
            self.logger.debug(f"🔍 interaction_result for @{username}: {interaction_result}")
            
            actually_interacted = False
            
            if interaction_result.get('liked'):
                likes_count = interaction_result.get('likes_count', 1)
                stats['liked'] += likes_count
                self.stats_manager.increment('likes', likes_count)
                actually_interacted = True
            if interaction_result.get('followed'):
                stats['followed'] += 1
                self.stats_manager.increment('follows')
                actually_interacted = True
            if interaction_result.get('story_viewed'):
                stats['stories_viewed'] += 1
                self.stats_manager.increment('stories_watched')
                actually_interacted = True
            if interaction_result.get('story_liked'):
                stats['story_likes'] += 1
                self.stats_manager.increment('story_likes')
                actually_interacted = True
            if interaction_result.get('commented'):
                actually_interacted = True
            
            if actually_interacted:
                stats['interacted'] += 1
                stats['processed'] += 1
                self.stats_manager.increment('profiles_interacted')
                self.human.record_interaction()
                tracker.log_profile_interacted(username, {
                    'liked': interaction_result.get('liked', False),
                    'followed': interaction_result.get('followed', False),
                    'story_viewed': interaction_result.get('story_viewed', False),
                    'commented': interaction_result.get('commented', False)
                })
            else:
                self.logger.debug(f"@{username} visited but no interaction (probability)")
                stats['skipped'] += 1
            
            # Marquer comme traité dans la DB
            if account_id:
                try:
                    DatabaseHelpers.mark_profile_as_processed(
                        username, 
                        "Direct interaction from followers list" if actually_interacted else "Visited but no interaction",
                        account_id=account_id,
                        session_id=self._get_session_id()
                    )
                except Exception:
                    pass
            
            if actually_interacted and self.session_manager:
                self.session_manager.record_profile_processed()
            
            return actually_interacted
        
        except Exception as e:
            self.logger.error(f"Error interacting with @{username}: {e}")
            stats['errors'] += 1
            return False
