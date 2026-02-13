import time
import random
from typing import Dict, List, Any, Optional
from loguru import logger

from ...core.base_business import BaseBusinessAction
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
                    self._record_action(username, 'STORY_WATCH', 1)
                    
                    if random.random() < config.get('like_probability', 0.3):
                        if self.click_actions.like_story():
                            stats['stories_liked'] += 1
                            self.logger.debug(f"Story {i+1} liked")
                            
                            # Record story like in database
                            self._record_action(username, 'STORY_LIKE', 1)
                    
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
    
