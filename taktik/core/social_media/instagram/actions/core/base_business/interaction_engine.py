"""Unified interaction engine — perform interactions on profile, view stories, IPC events."""

import time
import random
from typing import Optional, Dict, Any, List

from ..ipc import IPCEmitter


class InteractionEngineMixin:
    """Mixin: moteur d'interaction unifié (perform_interactions, stories, IPC events)."""

    def _perform_interactions_on_profile(
        self,
        username: str,
        config: Dict[str, Any],
        profile_data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Perform interactions (like, follow, comment, story) on a profile
        we are ALREADY viewing. Does NOT navigate or filter.
        
        All workflows delegate here so interaction logic is in one place.
        
        Args:
            username: Target username
            config: Workflow config (supports both percentage and probability keys)
            profile_data: Already-extracted profile data (for follow_button_state check, IPC events)
            
        Returns:
            Dict with keys: likes, follows, comments, stories, stories_liked, actually_interacted
        """
        result = {
            'likes': 0, 'follows': 0, 'comments': 0,
            'stories': 0, 'stories_liked': 0,
            'actually_interacted': False
        }

        try:
            interactions_to_do = self._determine_interactions_from_config(config)
            self.logger.debug(f"🎯 Planned interactions for @{username}: {interactions_to_do}")

            # === LIKE / COMMENT ===
            should_like = 'like' in interactions_to_do
            should_comment = 'comment' in interactions_to_do

            if should_like or should_comment:
                likes_result = self.like_business.like_profile_posts(
                    username,
                    max_likes=config.get('max_likes_per_profile', 3),
                    config={'randomize_order': True},
                    should_comment=should_comment,
                    custom_comments=config.get('custom_comments', []),
                    comment_template_category=config.get('comment_template_category', 'generic'),
                    max_comments=config.get('max_comments_per_profile', 1),
                    navigate_to_profile=False,
                    profile_data=profile_data,
                    should_like=should_like
                )
                if likes_result:
                    result['likes'] = likes_result.get('posts_liked', 0)
                    result['comments'] = likes_result.get('posts_commented', 0)
                    if result['likes'] > 0 or result['comments'] > 0:
                        result['actually_interacted'] = True
                    
                    # IPC event for likes (so frontend WorkflowAnalyzer can track)
                    if result['likes'] > 0:
                        self._emit_like_event(username, result['likes'], profile_data)

            # === FOLLOW ===
            if 'follow' in interactions_to_do:
                # Check if we already follow (avoids wasted click + API quota)
                follow_state = (profile_data or {}).get('follow_button_state', 'unknown')
                if follow_state in ('following', 'requested'):
                    self.logger.info(f"⏭️ Already following @{username} (button: {follow_state}) - skipping follow")
                else:
                    follow_success = self.click_actions.follow_user(username)
                    if follow_success:
                        result['follows'] = 1
                        result['actually_interacted'] = True
                        self.logger.info(f"✅ Followed @{username}")
                        
                        # NOTE: stats_manager.increment('follows') is NOT called here.
                        # Callers are responsible for stats tracking to avoid double-counting.
                        self._record_action(username, 'FOLLOW', 1)
                        self._emit_follow_event(username, profile_data)
                        self._handle_follow_suggestions_popup()

            # === STORIES ===
            if 'story' in interactions_to_do or 'story_like' in interactions_to_do:
                should_like_story = 'story_like' in interactions_to_do
                story_result = self._view_stories_on_current_profile(
                    username,
                    like_stories=should_like_story,
                    max_stories=config.get('max_stories_per_profile', 3)
                )
                if story_result:
                    result['stories'] = story_result.get('stories_viewed', 0)
                    result['stories_liked'] = story_result.get('stories_liked', 0)
                    if result['stories'] > 0:
                        result['actually_interacted'] = True

            return result

        except Exception as e:
            self.logger.error(f"Error performing interactions on @{username}: {e}")
            return result

    def _view_stories_on_current_profile(
        self, username: str, like_stories: bool = False, max_stories: int = 3
    ) -> Optional[Dict[str, int]]:
        """View stories when already on a profile page. No navigation."""
        try:
            if not self.detection_actions.has_stories():
                return None

            if not self.click_actions.click_story_ring():
                return None

            self._human_like_delay('story_load')

            stories_viewed = 0
            stories_liked = 0

            for _ in range(max_stories):
                if not self.detection_actions.is_story_viewer_open():
                    break

                view_duration = random.uniform(2, 5)
                time.sleep(view_duration)
                stories_viewed += 1

                if like_stories:
                    try:
                        if self.click_actions.like_story():
                            stories_liked += 1
                            self.logger.debug("Story liked")
                    except Exception:
                        pass

                if not self.nav_actions.navigate_to_next_story():
                    break

            # Back to profile
            self.device.press('back')
            self._human_like_delay('navigation')

            if stories_viewed > 0:
                self._record_action(username, 'STORY_WATCH', stories_viewed)
                if stories_liked > 0:
                    self._record_action(username, 'STORY_LIKE', stories_liked)
                self.logger.debug(f"{stories_viewed} stories viewed, {stories_liked} liked")
                return {'stories_viewed': stories_viewed, 'stories_liked': stories_liked}

            return None

        except Exception as e:
            self.logger.error(f"Error viewing stories @{username}: {e}")
            return None

    def _emit_follow_event(self, username: str, profile_data: Dict[str, Any] = None):
        """Send IPC follow event to frontend for WorkflowAnalyzer."""
        pd = profile_data or {}
        IPCEmitter.emit_follow(username, success=True, profile_data={
            "followers_count": pd.get('followers_count', 0),
            "following_count": pd.get('following_count', 0),
            "posts_count": pd.get('posts_count', 0)
        } if profile_data else None)

    def _emit_like_event(self, username: str, likes_count: int, profile_data: Dict[str, Any] = None):
        """Send IPC like event to frontend for WorkflowAnalyzer."""
        pd = profile_data or {}
        IPCEmitter.emit_like(username, likes_count=likes_count, profile_data={
            "followers_count": pd.get('followers_count', 0),
            "following_count": pd.get('following_count', 0),
            "posts_count": pd.get('posts_count', 0)
        } if profile_data else None)

    def _interact_with_user(self, username: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            if not self.nav_actions.navigate_to_profile(username):
                self.logger.error(f"❌ Cannot navigate to @{username}")
                return None
            
            profile_info = self.profile_business.get_complete_profile_info(username, navigate_if_needed=False)
            if not profile_info:
                self.logger.error(f"❌ Cannot get profile info for @{username}")
                return None
            
            if profile_info.get('is_private', False):
                self.logger.info(f"⏭️ Private profile @{username} - SKIP immediately")
                
                if hasattr(self, 'stats_manager'):
                    self.stats_manager.increment('private_profiles')
                
                return None
            
            filter_result = self.filtering_business.apply_comprehensive_filter(
                profile_info, 
                self._get_filter_criteria_from_config(config)
            )
            
            if not filter_result['suitable']:
                reason = filter_result.get('reason', 'Criteria not met')
                reasons = filter_result.get('reasons', [reason])
                self.logger.info(f"🚫 @{username} filtered: {reason}")
                
                if hasattr(self, 'stats_manager'):
                    if 'privé' in reason.lower() or 'private' in reason.lower():
                        self.stats_manager.increment('private_profiles')
                    else:
                        self.stats_manager.increment('profiles_filtered')
                
                try:
                    from ..business.common.database_helpers import DatabaseHelpers
                    reasons_text = ', '.join(reasons) if reasons else reason
                    
                    source_type = 'HASHTAG' if 'hashtag' in self.logger._context.get('module', '') else 'POST_URL'
                    source_name = config.get('source', 'unknown')
                    
                    DatabaseHelpers.record_filtered_profile(
                        username=username,
                        reason=reasons_text,
                        source_type=source_type,
                        source_name=source_name,
                        account_id=self._get_account_id(),
                        session_id=self._get_session_id()
                    )
                    self.logger.debug(f"✅ Filtered profile @{username} recorded in API")
                except Exception as e:
                    self.logger.error(f"❌ Error recording filtered profile @{username}: {e}")
                
                return None
            
            # === INTERACTIONS (delegated to unified method) ===
            result = self._perform_interactions_on_profile(username, config, profile_data=profile_info)
            
            return result if result.get('actually_interacted', False) else None
            
        except Exception as e:
            self.logger.error(f"❌ Error interacting with @{username}: {e}")
            return None
