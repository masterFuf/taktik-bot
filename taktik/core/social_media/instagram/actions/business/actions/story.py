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
            'max_feed_profiles': 5,
            'view_duration_range': (2, 6),
            'navigation_delay_range': (0.5, 1.5),
            'like_probability': 0.3,
            'reaction_probability': 0.0,
            'reaction': 'laugh',
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

    def view_feed_stories(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """View friends' stories from the home feed carousel.

        Instagram does not expose a reliable duration per story in the UI dump.
        The workflow therefore uses `view_duration_range` and limits story
        advancement with `max_stories_per_profile`.
        """
        config = {**self.default_config, **(config or {})}
        stats = {
            'profiles_opened': 0,
            'stories_viewed': 0,
            'stories_liked': 0,
            'stories_reacted': 0,
            'errors': 0,
            'success': False,
        }

        try:
            self.logger.info("Starting feed stories workflow")

            if not self.nav_actions.navigate_to_home():
                self.logger.error("Failed to navigate to home feed")
                stats['errors'] += 1
                return stats

            visible_stories = self.detection_actions.count_visible_feed_stories(skip_own_story=True)
            max_profiles = min(config.get('max_feed_profiles', 5), visible_stories)
            if max_profiles <= 0:
                self.logger.info("No visible friends' stories in feed tray")
                return stats

            for profile_index in range(max_profiles):
                if not self.click_actions.click_feed_story(profile_index, skip_own_story=True):
                    self.logger.debug(f"Could not open feed story #{profile_index}")
                    continue

                self._human_like_delay('story_load')
                if not self.detection_actions.is_story_viewer_open():
                    self.logger.debug("Story viewer did not open")
                    stats['errors'] += 1
                    continue

                stats['profiles_opened'] += 1
                current_username = None

                for story_index in range(config.get('max_stories_per_profile', 3)):
                    if not self.detection_actions.is_story_viewer_open():
                        break

                    metadata = self.detection_actions.get_story_viewer_metadata()
                    current_username = metadata.get('title') or current_username or 'unknown'

                    view_duration = random.uniform(*config['view_duration_range'])
                    self.logger.debug(f"Viewing feed story @{current_username} for {view_duration:.1f}s")
                    time.sleep(view_duration)

                    stats['stories_viewed'] += 1
                    self._record_action(current_username, 'STORY_WATCH', 1)

                    if random.random() < config.get('like_probability', 0.0):
                        if self.click_actions.like_story():
                            stats['stories_liked'] += 1
                            self._record_action(current_username, 'STORY_LIKE', 1)

                    if random.random() < config.get('reaction_probability', 0.0):
                        if self.click_actions.react_to_story(
                            reaction=config.get('reaction'),
                            emoji_index=config.get('reaction_index'),
                        ):
                            stats['stories_reacted'] += 1
                            self._record_action(current_username, 'STORY_REACTION', 1)

                    if story_index < config.get('max_stories_per_profile', 3) - 1:
                        if not self.nav_actions.navigate_to_next_story():
                            break
                        time.sleep(random.uniform(*config['navigation_delay_range']))

                self._press_back(1)
                self._human_like_delay('navigation')

            stats['success'] = stats['stories_viewed'] > 0
            self.logger.info(
                f"Feed stories completed: {stats['profiles_opened']} profiles, "
                f"{stats['stories_viewed']} stories viewed, {stats['stories_liked']} liked, "
                f"{stats['stories_reacted']} reacted"
            )
            return stats

        except Exception as e:
            self.logger.error(f"General error viewing feed stories: {e}")
            stats['errors'] += 1
            return stats
    
