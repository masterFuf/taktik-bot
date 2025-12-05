"""Business logic for Instagram interactions."""

from typing import Optional, Dict, Any, List, Tuple
from loguru import logger
import random

from ...core.base_business_action import BaseBusinessAction
from ...atomic.text_actions import TextActions


class InteractionBusiness(BaseBusinessAction):
    
    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device, session_manager, automation=automation, module_name="interaction")
        
        self.text_actions = TextActions(device)
    
    def perform_follow_action(self, username: str, navigate_if_needed: bool = True) -> Dict[str, Any]:
        result = {
            'success': False,
            'action': 'follow',
            'username': username,
            'reason': '',
            'button_state_before': 'unknown',
            'button_state_after': 'unknown'
        }
        
        try:
            if navigate_if_needed:
                if not self.nav_actions.navigate_to_profile(username):
                    result['reason'] = 'Navigation failed'
                    return result
            
            initial_state = self.click_actions.get_follow_button_state()
            result['button_state_before'] = initial_state
            
            if initial_state == 'unfollow':
                result['reason'] = 'Already following'
                result['success'] = True
                return result
            elif initial_state == 'message':
                result['reason'] = 'Own profile or already following'
                return result
            elif initial_state != 'follow':
                result['reason'] = f'Unexpected button state: {initial_state}'
                return result
            
            if self.click_actions.click_follow_button():
                self._human_like_delay('click')
                
                final_state = self.click_actions.get_follow_button_state()
                result['button_state_after'] = final_state
                
                if final_state in ['unfollow', 'message']:
                    result['success'] = True
                    result['reason'] = 'Follow successful'
                    self.logger.info(f"Follow successful: @{username}")
                    
                    # Record follow in database
                    self._record_action(username, 'FOLLOW', 1)
                else:
                    result['reason'] = f'Button state unchanged: {final_state}'
                    self.logger.warning(f"Follow uncertain: @{username}")
            else:
                result['reason'] = 'Click follow button failed'
                
        except Exception as e:
            result['reason'] = f'Exception: {str(e)}'
            self.logger.error(f"Error following @{username}: {e}")
        
        return result
    
    def perform_unfollow_action(self, username: str, navigate_if_needed: bool = True) -> Dict[str, Any]:
        result = {
            'success': False,
            'action': 'unfollow',
            'username': username,
            'reason': '',
            'button_state_before': 'unknown',
            'button_state_after': 'unknown'
        }
        
        try:
            if navigate_if_needed:
                if not self.nav_actions.navigate_to_profile(username):
                    result['reason'] = 'Navigation failed'
                    return result
            
            initial_state = self.click_actions.get_follow_button_state()
            result['button_state_before'] = initial_state
            
            if initial_state == 'follow':
                result['reason'] = 'Not following'
                result['success'] = True
                return result
            elif initial_state != 'unfollow':
                result['reason'] = f'Cannot unfollow, button state: {initial_state}'
                return result
            
            if self.click_actions.click_unfollow_button():
                self._human_like_delay('click')
                
                if self._find_and_click(self.popup_selectors.unfollow_confirmation_selectors, timeout=2):
                    self._human_like_delay('click')
                
                final_state = self.click_actions.get_follow_button_state()
                result['button_state_after'] = final_state
                
                if final_state == 'follow':
                    result['success'] = True
                    result['reason'] = 'Unfollow successful'
                    self.logger.info(f"Unfollow successful: @{username}")
                    
                    # Record unfollow in database
                    self._record_action(username, 'UNFOLLOW', 1)
                else:
                    result['reason'] = f'Button state unchanged: {final_state}'
                    self.logger.warning(f"Unfollow uncertain: @{username}")
            else:
                result['reason'] = 'Click unfollow button failed'
                
        except Exception as e:
            result['reason'] = f'Exception: {str(e)}'
            self.logger.error(f"Error unfollowing @{username}: {e}")
        
        return result
    
    def perform_like_sequence(self, max_likes: int = 3, 
                            like_probability: float = 0.8) -> Dict[str, Any]:
        result = {
            'success': False,
            'action': 'like_sequence',
            'posts_processed': 0,
            'posts_liked': 0,
            'posts_skipped': 0,
            'errors': 0,
            'details': []
        }
        
        try:
            if not self.detection_actions.is_post_grid_visible():
                result['reason'] = 'No post grid visible'
                return result
            
            posts_count = self.detection_actions.count_visible_posts()
            if posts_count == 0:
                result['reason'] = 'No posts found'
                return result
            
            self.logger.info(f"Starting like sequence: max {max_likes} on {posts_count} posts")
            
            likes_performed = 0
            posts_to_process = min(max_likes, posts_count)
            
            for i in range(posts_to_process):
                try:
                    should_like = random.random() < like_probability
                    
                    if not should_like:
                        result['posts_skipped'] += 1
                        result['details'].append({
                            'post_index': i,
                            'action': 'skipped',
                            'reason': 'probability'
                        })
                        continue
                    
                    if not self.click_actions.click_post_thumbnail(i):
                        result['errors'] += 1
                        result['details'].append({
                            'post_index': i,
                            'action': 'error',
                            'reason': 'click_post_failed'
                        })
                        continue
                    
                    self._human_like_delay('navigation')
                    
                    if self.click_actions.is_post_already_liked():
                        result['posts_skipped'] += 1
                        result['details'].append({
                            'post_index': i,
                            'action': 'skipped',
                            'reason': 'already_liked'
                        })
                    else:
                        if self.click_actions.click_like_button():
                            likes_performed += 1
                            result['posts_liked'] += 1
                            result['details'].append({
                                'post_index': i,
                                'action': 'liked',
                                'reason': 'success'
                            })
                            self.logger.debug(f"Post {i+1} liked")
                        else:
                            result['errors'] += 1
                            result['details'].append({
                                'post_index': i,
                                'action': 'error',
                                'reason': 'like_button_failed'
                            })
                    
                    result['posts_processed'] += 1
                    
                    self._press_back(1)
                    self._human_like_delay('navigation')
                    
                    if likes_performed < max_likes:
                        self._human_like_delay('click')
                    
                except Exception as e:
                    result['errors'] += 1
                    result['details'].append({
                        'post_index': i,
                        'action': 'error',
                        'reason': f'exception: {str(e)}'
                    })
                    self.logger.debug(f"Error on post {i}: {e}")
                    
                    self._press_back(2)
                    self._human_like_delay('navigation')
            
            result['success'] = result['posts_liked'] > 0
            self.logger.info(f"Sequence completed: {result['posts_liked']} likes on {result['posts_processed']} posts")
            
        except Exception as e:
            result['reason'] = f'Sequence exception: {str(e)}'
            self.logger.error(f"Error in like sequence: {e}")
        
        return result
    
    def perform_story_interaction(self, max_stories: int = 3, 
                                like_probability: float = 0.6) -> Dict[str, Any]:
        result = {
            'success': False,
            'action': 'story_interaction',
            'stories_viewed': 0,
            'stories_liked': 0,
            'errors': 0,
            'details': []
        }
        
        try:
            stories_count = self.detection_actions.count_visible_stories()
            if stories_count == 0:
                result['reason'] = 'No stories available'
                return result
            
            self.logger.info(f"Starting story interaction: max {max_stories} out of {stories_count} available")
            
            if not self.click_actions.click_story_ring(0):
                result['reason'] = 'Failed to open first story'
                return result
            
            self._human_like_delay('navigation')
            
            stories_to_process = min(max_stories, stories_count)
            
            for i in range(stories_to_process):
                try:
                    if not self.detection_actions.is_story_viewer_open():
                        result['errors'] += 1
                        result['details'].append({
                            'story_index': i,
                            'action': 'error',
                            'reason': 'story_viewer_not_open'
                        })
                        break
                    
                    result['stories_viewed'] += 1
                    
                    should_like = random.random() < like_probability
                    
                    if should_like:
                        if self.click_actions.click_story_like_button():
                            result['stories_liked'] += 1
                            result['details'].append({
                                'story_index': i,
                                'action': 'liked',
                                'reason': 'success'
                            })
                            self.logger.debug(f"Story {i+1} liked")
                        else:
                            result['details'].append({
                                'story_index': i,
                                'action': 'viewed',
                                'reason': 'like_failed'
                            })
                    else:
                        result['details'].append({
                            'story_index': i,
                            'action': 'viewed',
                            'reason': 'probability_skip'
                        })
                    
                    view_duration = self.utils.generate_human_like_delay(2.0, 5.0)
                    self._random_sleep(view_duration)
                    
                    if i < stories_to_process - 1:
                        center_x = self.device.info['displayWidth'] * 0.8
                        center_y = self.device.info['displayHeight'] * 0.5
                        self.device.click(center_x, center_y)
                        self._human_like_delay('click')
                    
                except Exception as e:
                    result['errors'] += 1
                    result['details'].append({
                        'story_index': i,
                        'action': 'error',
                        'reason': f'exception: {str(e)}'
                    })
                    self.logger.debug(f"Error on story {i}: {e}")
            
            self._press_back(1)
            self._human_like_delay('navigation')
            
            result['success'] = result['stories_viewed'] > 0
            self.logger.info(f"Stories completed: {result['stories_viewed']} viewed, {result['stories_liked']} liked")
            
        except Exception as e:
            result['reason'] = f'Story interaction exception: {str(e)}'
            self.logger.error(f"Error in story interaction: {e}")
        
        return result
    
    def perform_comment_action(self, comment_text: str, post_index: int = 0) -> Dict[str, Any]:
        result = {
            'success': False,
            'action': 'comment',
            'comment_text': comment_text,
            'post_index': post_index,
            'reason': ''
        }
        
        try:
            if not comment_text or not comment_text.strip():
                result['reason'] = 'Empty comment text'
                return result
            
            if not self.click_actions.click_post_thumbnail(post_index):
                result['reason'] = 'Failed to open post'
                return result
            
            self._human_like_delay('navigation')
            
            if not self.click_actions.click_comment_button():
                result['reason'] = 'Failed to click comment button'
                return result
            
            self._human_like_delay('click')
            
            if not self.text_actions.type_comment(comment_text.strip()):
                result['reason'] = 'Failed to type comment'
                return result
            
            if self._find_and_click(self.post_selectors.send_post_button_selectors, timeout=3):
                self._human_like_delay('click')
                result['success'] = True
                result['reason'] = 'Comment posted successfully'
                self.logger.info(f"Comment posted: '{comment_text[:30]}...'")
            else:
                if self.text_actions.press_enter():
                    result['success'] = True
                    result['reason'] = 'Comment posted with Enter'
                    self.logger.info(f"Comment posted (Enter): '{comment_text[:30]}...'")
                else:
                    result['reason'] = 'Failed to send comment'
            
            self._press_back(1)
            self._human_like_delay('navigation')
            
        except Exception as e:
            result['reason'] = f'Comment exception: {str(e)}'
            self.logger.error(f"Error posting comment: {e}")
        
        return result
    
    def perform_comprehensive_interaction(self, username: str, 
                                        interaction_config: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            'success': False,
            'username': username,
            'actions_performed': [],
            'total_actions': 0,
            'successful_actions': 0,
            'errors': 0
        }
        
        try:
            if not self.nav_actions.navigate_to_profile(username):
                result['reason'] = 'Navigation failed'
                return result
            
            self.logger.info(f"Comprehensive interaction with @{username}")
            
            config = {
                'do_follow': True,
                'do_likes': True,
                'do_stories': True,
                'max_likes': 3,
                'max_stories': 2,
                'like_probability': 0.8,
                'story_like_probability': 0.6,
                **interaction_config
            }
            
            if config.get('do_follow', True):
                follow_result = self.perform_follow_action(username, navigate_if_needed=False)
                result['actions_performed'].append(follow_result)
                result['total_actions'] += 1
                if follow_result['success']:
                    result['successful_actions'] += 1
                else:
                    result['errors'] += 1
            
            if config.get('do_likes', True):
                likes_result = self.perform_like_sequence(
                    max_likes=config.get('max_likes', 3),
                    like_probability=config.get('like_probability', 0.8)
                )
                result['actions_performed'].append(likes_result)
                result['total_actions'] += 1
                if likes_result['success']:
                    result['successful_actions'] += 1
                else:
                    result['errors'] += 1
            
            if config.get('do_stories', True):
                stories_result = self.perform_story_interaction(
                    max_stories=config.get('max_stories', 2),
                    like_probability=config.get('story_like_probability', 0.6)
                )
                result['actions_performed'].append(stories_result)
                result['total_actions'] += 1
                if stories_result['success']:
                    result['successful_actions'] += 1
                else:
                    result['errors'] += 1
            
            result['success'] = result['successful_actions'] > 0
            success_rate = result['successful_actions'] / result['total_actions'] if result['total_actions'] > 0 else 0
            
            self.logger.info(f"Interaction completed @{username}: "
                           f"{result['successful_actions']}/{result['total_actions']} "
                           f"({success_rate:.1%} success)")
            
        except Exception as e:
            result['reason'] = f'Comprehensive interaction exception: {str(e)}'
            self.logger.error(f"Error in comprehensive interaction @{username}: {e}")
        
        return result
