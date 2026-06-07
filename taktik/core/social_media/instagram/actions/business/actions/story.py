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
            'stories_skipped_ads': 0,
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

                    # Never watch/like/react a sponsored story — advance past it
                    # (same guard as view_feed_stories).
                    metadata = self.detection_actions.get_story_viewer_metadata()
                    if metadata.get('is_ad'):
                        stats['stories_skipped_ads'] += 1
                        self.logger.debug("Skipping sponsored story")
                        if not self.nav_actions.navigate_to_next_story():
                            break
                        time.sleep(random.uniform(*config['navigation_delay_range']))
                        continue

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
            
            # Robust close: swipe-down (a back press is unreliable / can be swallowed
            # by an overlay); fall back to back only if the viewer is still open.
            self.click_actions.close_story()
            if self.detection_actions.is_story_viewer_open():
                self._press_back(1)
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
            'stories_skipped_ads': 0,
            'errors': 0,
            'success': False,
        }

        max_feed_profiles = config.get('max_feed_profiles', 5)
        max_stories = config.get('max_stories_per_profile', 3)
        max_tray_scrolls = config.get('max_tray_scrolls', 4)

        try:
            self.logger.info("Starting feed stories workflow")

            if not self.nav_actions.navigate_to_home():
                self.logger.error("Failed to navigate to home feed")
                stats['errors'] += 1
                return stats

            opened = 0
            tray_scrolls = 0

            # Watch up to `max_feed_profiles` friends; scroll the tray to reach more than
            # the few bubbles initially visible (bounded by `max_tray_scrolls`).
            while opened < max_feed_profiles:
                visible_stories = self.detection_actions.count_visible_feed_stories(skip_own_story=True)
                if visible_stories <= 0:
                    self.logger.info("No more visible friends' stories in feed tray")
                    break

                # Consumed the currently visible bubbles → reveal more friends to the right.
                if opened >= visible_stories:
                    if tray_scrolls >= max_tray_scrolls:
                        break
                    if not self.click_actions.scroll_feed_stories_left():
                        break
                    tray_scrolls += 1
                    continue

                if not self.click_actions.click_feed_story(opened, skip_own_story=True):
                    self.logger.debug(f"Could not open feed story #{opened}")
                    opened += 1
                    continue

                self._human_like_delay('story_load')
                if not self.detection_actions.is_story_viewer_open():
                    self.logger.debug("Story viewer did not open")
                    stats['errors'] += 1
                    opened += 1
                    continue

                stats['profiles_opened'] += 1
                current_username = None

                for story_index in range(max_stories):
                    if not self.detection_actions.is_story_viewer_open():
                        break

                    metadata = self.detection_actions.get_story_viewer_metadata()
                    current_username = metadata.get('title') or current_username or 'unknown'

                    # Never watch/like/react a sponsored story — advance past it.
                    if metadata.get('is_ad'):
                        stats['stories_skipped_ads'] += 1
                        self.logger.debug("Skipping sponsored story")
                        if not self.nav_actions.navigate_to_next_story():
                            break
                        time.sleep(random.uniform(*config['navigation_delay_range']))
                        continue

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

                    if story_index < max_stories - 1:
                        if not self.nav_actions.navigate_to_next_story():
                            break
                        time.sleep(random.uniform(*config['navigation_delay_range']))

                # Robust close: swipe-down (a back press is unreliable / can be swallowed by
                # an overlay); fall back to back only if the viewer is still open.
                self.click_actions.close_story()
                if self.detection_actions.is_story_viewer_open():
                    self._press_back(1)
                self._human_like_delay('navigation')
                opened += 1

            stats['success'] = stats['stories_viewed'] > 0
            self.logger.info(
                f"Feed stories completed: {stats['profiles_opened']} profiles, "
                f"{stats['stories_viewed']} viewed, {stats['stories_liked']} liked, "
                f"{stats['stories_reacted']} reacted, {stats['stories_skipped_ads']} ads skipped"
            )
            return stats

        except Exception as e:
            self.logger.error(f"General error viewing feed stories: {e}")
            stats['errors'] += 1
            return stats
    
