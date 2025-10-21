import time
import random
from typing import Dict, List, Any, Optional
from loguru import logger

from ...core.base_business_action import BaseBusinessAction
from ..management.profile import ProfileBusiness


class StoryBusiness(BaseBusinessAction):
    
    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device, session_manager, automation=automation, module_name="story")
        
        self.profile_business = ProfileBusiness(device, session_manager)
        
        self.default_config = {
            'max_stories_per_profile': 5,
            'view_duration_range': (2, 6),
            'navigation_delay_range': (0.5, 1.5),
            'like_probability': 0.3,
            'skip_viewed_stories': True
        }
    
    def view_profile_stories(self, username: str,
                           max_stories: int = 5,
                           config: Dict[str, Any] = None) -> Dict[str, Any]:
        config = {**self.default_config, **(config or {})}
        
        stats = {
            'username': username,
            'stories_viewed': 0,
            'stories_liked': 0,
            'stories_skipped': 0,
            'total_stories_detected': 0,
            'errors': 0,
            'success': False
        }
        
        try:
            self.logger.info(f"Starting to view stories from @{username}")
            
            if not self.nav_actions.navigate_to_profile(username):
                self.logger.error(f"Failed to navigate to @{username}")
                stats['errors'] += 1
                return stats
            
            if not self.detection_actions.has_stories():
                self.logger.debug(f"@{username} has no stories")
                return stats
            
            if not self.click_actions.click_story_ring():
                self.logger.error("Failed to click on story avatar")
                stats['errors'] += 1
                return stats
            
            self._human_like_delay('story_load')
            
            current_story, total_stories = self.detection_actions.get_story_count_from_viewer()
            if total_stories > 0:
                stats['total_stories_detected'] = total_stories
                self.logger.info(f"{total_stories} stories detected for @{username}")
                max_stories = min(max_stories, total_stories)
            else:
                self.logger.debug(f"Story count not detected, using max_stories={max_stories}")
            
            for i in range(max_stories):
                try:
                    if not self.detection_actions.is_story_viewer_open():
                        self.logger.debug("No longer in story screen")
                        break
                    
                    current_story, total_stories = self.detection_actions.get_story_count_from_viewer()
                    if total_stories > 0:
                        self.logger.debug(f"Viewing story {current_story}/{total_stories}")
                    else:
                        self.logger.debug(f"Viewing story {i+1}")
                    
                    view_duration = random.uniform(*config['view_duration_range'])
                    self.logger.debug(f"View duration: {view_duration:.1f}s")
                    time.sleep(view_duration)
                    
                    stats['stories_viewed'] += 1
                    
                    # Record story view in database
                    try:
                        from ..common.database_helpers import DatabaseHelpers
                        account_id = self._get_account_id()
                        session_id = self._get_session_id()
                        
                        if account_id:
                            DatabaseHelpers.record_individual_actions(
                                username=username,
                                action_type='STORY_WATCH',
                                count=1,
                                account_id=account_id,
                                session_id=session_id
                            )
                            self.logger.debug(f"Story view recorded for @{username}")
                    except Exception as e:
                        self.logger.error(f"Failed to record story view: {e}")
                    
                    if random.random() < config.get('like_probability', 0.3):
                        if self.click_actions.like_story():
                            stats['stories_liked'] += 1
                            self.logger.debug(f"Story {i+1} liked")
                            
                            # Record story like in database
                            try:
                                from ..common.database_helpers import DatabaseHelpers
                                account_id = self._get_account_id()
                                session_id = self._get_session_id()
                                
                                if account_id:
                                    DatabaseHelpers.record_individual_actions(
                                        username=username,
                                        action_type='STORY_LIKE',
                                        count=1,
                                        account_id=account_id,
                                        session_id=session_id
                                    )
                                    self.logger.debug(f"Story like recorded for @{username}")
                            except Exception as e:
                                self.logger.error(f"Failed to record story like: {e}")
                    
                    if i < max_stories - 1:
                        if not self.nav_actions.navigate_to_next_story():
                            self.logger.debug("No next story or end of stories")
                            break
                        
                        delay = random.uniform(*config['navigation_delay_range'])
                        time.sleep(delay)
                
                except Exception as e:
                    self.logger.error(f"Error on story {i+1}: {e}")
                    stats['errors'] += 1
                    continue
            
            self.device.back()
            self._human_like_delay('navigation')
            
            stats['success'] = stats['stories_viewed'] > 0
            
            if stats['total_stories_detected'] > 0:
                self.logger.info(f"Stories completed for @{username}: {stats['stories_viewed']}/{stats['total_stories_detected']} viewed, {stats['stories_liked']} liked")
            else:
                self.logger.info(f"Stories completed for @{username}: {stats['stories_viewed']} viewed, {stats['stories_liked']} liked")
            
            return stats
            
        except Exception as e:
            self.logger.error(f"General error viewing stories @{username}: {e}")
            stats['errors'] += 1
            return stats
    
    def view_multiple_profiles_stories(self, usernames: List[str],
                                     stories_per_profile: int = 3,
                                     config: Dict[str, Any] = None) -> Dict[str, Any]:
        config = {**self.default_config, **(config or {})}
        
        global_stats = {
            'profiles_processed': 0,
            'total_stories_viewed': 0,
            'total_stories_liked': 0,
            'total_stories_skipped': 0,
            'total_errors': 0,
            'profiles_success': 0,
            'profiles_failed': 0,
            'profiles_no_stories': 0,
            'details': []
        }
        
        self.logger.info(f"Starting to view stories from {len(usernames)} profiles")
        
        for i, username in enumerate(usernames):
            try:
                self.logger.info(f"[{i+1}/{len(usernames)}] Viewing stories from @{username}")
                
                profile_stats = self.view_profile_stories(username, stories_per_profile, config)
                global_stats['profiles_processed'] += 1
                global_stats['total_stories_viewed'] += profile_stats['stories_viewed']
                global_stats['total_stories_liked'] += profile_stats['stories_liked']
                global_stats['total_stories_skipped'] += profile_stats['stories_skipped']
                global_stats['total_errors'] += profile_stats['errors']
                
                if profile_stats['success']:
                    global_stats['profiles_success'] += 1
                elif profile_stats['stories_viewed'] == 0 and profile_stats['errors'] == 0:
                    global_stats['profiles_no_stories'] += 1
                else:
                    global_stats['profiles_failed'] += 1
                
                global_stats['details'].append(profile_stats)
                
                if i < len(usernames) - 1:
                    delay = random.randint(5, 15)
                    self.logger.debug(f"Delay {delay}s before next profile")
                    time.sleep(delay)
                
            except Exception as e:
                self.logger.error(f"Error processing stories @{username}: {e}")
                global_stats['total_errors'] += 1
                global_stats['profiles_failed'] += 1
                continue
        
        self.logger.info(f"Story viewing completed on all profiles: {global_stats}")
        return global_stats
    
    def view_feed_stories(self, max_stories: int = 10,
                         config: Dict[str, Any] = None) -> Dict[str, Any]:
        config = {**self.default_config, **(config or {})}
        
        stats = {
            'stories_viewed': 0,
            'stories_liked': 0,
            'profiles_viewed': 0,
            'errors': 0,
            'success': False
        }
        
        try:
            self.logger.info(f"Starting to view feed stories (max: {max_stories})")
            
            if not self.nav_actions.navigate_to_home_feed():
                self.logger.error("Failed to navigate to feed")
                stats['errors'] += 1
                return stats
            
            if not self.click_actions.click_first_story_in_feed():
                self.logger.warning("No stories available in feed")
                return stats
            
            self._human_like_delay('story_load')
            
            current_profile = None
            stories_in_current_profile = 0
            
            for i in range(max_stories):
                try:
                    if not self.detection_actions.is_story_viewer_open():
                        self.logger.debug("No longer in story screen")
                        break
                    
                    profile_name = self.detection_actions.get_story_profile_name()
                    if profile_name != current_profile:
                        if current_profile is not None:
                            stats['profiles_viewed'] += 1
                        current_profile = profile_name
                        stories_in_current_profile = 0
                        self.logger.debug(f"New profile: @{profile_name}")
                    
                    view_duration = random.uniform(*config['view_duration_range'])
                    self.logger.debug(f"Story {i+1} from @{current_profile} for {view_duration:.1f}s")
                    time.sleep(view_duration)
                    
                    stats['stories_viewed'] += 1
                    stories_in_current_profile += 1
                    
                    if random.random() < config.get('like_probability', 0.3):
                        if self.click_actions.like_story():
                            stats['stories_liked'] += 1
                            self.logger.debug(f"Story liked")
                    
                    if i < max_stories - 1:
                        if not self.nav_actions.navigate_to_next_story():
                            self.logger.debug("End of stories")
                            break
                        
                        delay = random.uniform(*config['navigation_delay_range'])
                        time.sleep(delay)
                
                except Exception as e:
                    self.logger.error(f"Error on story {i+1}: {e}")
                    stats['errors'] += 1
                    continue
            
            if current_profile is not None:
                stats['profiles_viewed'] += 1
            
            self.device.back()
            self._human_like_delay('navigation')
            
            stats['success'] = stats['stories_viewed'] > 0
            self.logger.info(f"Feed stories completed: {stats['stories_viewed']} viewed from {stats['profiles_viewed']} profiles")
            
            return stats
            
        except Exception as e:
            self.logger.error(f"General error viewing feed stories: {e}")
            stats['errors'] += 1
            return stats
    
    def like_current_story(self) -> bool:
        try:
            if not self.detection_actions.is_story_viewer_open():
                self.logger.warning("Not on a story screen")
                return False
            
            if self.click_actions.like_story():
                self.logger.debug("Story liked successfully")
                return True
            else:
                self.logger.warning("Failed to like story")
                return False
                
        except Exception as e:
            self.logger.error(f"Error liking current story: {e}")
            return False
