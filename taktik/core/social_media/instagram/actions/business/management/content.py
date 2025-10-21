"""Business logic for Instagram content management."""

from typing import Optional, Dict, Any, List, Tuple
from loguru import logger
import re

from ...core.base_business_action import BaseBusinessAction


class ContentBusiness(BaseBusinessAction):
    
    def __init__(self, device, session_manager=None):
        super().__init__(device, session_manager, automation=None, module_name="content")
    
    def extract_usernames_from_follow_list(self) -> List[str]:
        return self.detection_actions.extract_usernames_from_follow_list()
    
    def extract_followers_from_profile(self, username: str, max_followers: int = 100, 
                                     scroll_attempts: int = 10) -> List[str]:
        followers = []
        
        try:
            if not self.nav_actions.navigate_to_profile(username):
                self.logger.error(f"Failed to navigate to @{username}")
                return followers
            
            if not self.nav_actions.open_followers_list():
                self.logger.error("Failed to open followers list")
                return followers
            
            self.logger.info(f"Extracting followers from @{username} (max: {max_followers})")
            
            extracted_count = 0
            scroll_count = 0
            no_new_users_count = 0
            
            while extracted_count < max_followers and scroll_count < scroll_attempts:
                current_usernames = self.detection_actions.extract_usernames_from_follow_list()
                
                new_users_found = 0
                for username_found in current_usernames:
                    if username_found not in followers:
                        followers.append(username_found)
                        extracted_count += 1
                        new_users_found += 1
                        
                        if extracted_count >= max_followers:
                            break
                
                self.logger.debug(f"Extraction: {new_users_found} new, total: {extracted_count}")
                
                if new_users_found == 0:
                    no_new_users_count += 1
                    if no_new_users_count >= 3:
                        self.logger.info("No new users found, stopping extraction")
                        break
                else:
                    no_new_users_count = 0
                
                if extracted_count < max_followers:
                    self.scroll_actions.scroll_followers_list_down()
                    self._human_like_delay('scroll')
                    scroll_count += 1
            
            self.logger.info(f"Extraction completed: {len(followers)} followers extracted")
            
        except Exception as e:
            self.logger.error(f"Error extracting followers: {e}")
        
        return followers
    
    def extract_following_from_profile(self, username: str, max_following: int = 100,
                                     scroll_attempts: int = 10) -> List[str]:
        following = []
        
        try:
            if not self.nav_actions.navigate_to_profile(username):
                self.logger.error(f"Failed to navigate to @{username}")
                return following
            
            if not self.nav_actions.open_following_list():
                self.logger.error("Failed to open following list")
                return following
            
            self.logger.info(f"Extracting following from @{username} (max: {max_following})")
            
            extracted_count = 0
            scroll_count = 0
            no_new_users_count = 0
            
            while extracted_count < max_following and scroll_count < scroll_attempts:
                current_usernames = self.detection_actions.extract_usernames_from_follow_list()
                
                new_users_found = 0
                for username_found in current_usernames:
                    if username_found not in following:
                        following.append(username_found)
                        extracted_count += 1
                        new_users_found += 1
                        
                        if extracted_count >= max_following:
                            break
                
                self.logger.debug(f"Extraction: {new_users_found} new, total: {extracted_count}")
                
                if new_users_found == 0:
                    no_new_users_count += 1
                    if no_new_users_count >= 3:
                        break
                else:
                    no_new_users_count = 0
                
                if extracted_count < max_following:
                    self.scroll_actions.scroll_followers_list_down()
                    self._human_like_delay('scroll')
                    scroll_count += 1
            
            self.logger.info(f"Extraction completed: {len(following)} following extracted")
            
        except Exception as e:
            self.logger.error(f"Error extracting following: {e}")
        
        return following
    
    def extract_likers_from_post(self, post_url: str, max_likers: int = 50) -> List[str]:
        likers = []
        
        try:
            if not self._navigate_to_post_via_url(post_url):
                self.logger.error(f"Failed to navigate to post: {post_url}")
                return likers
            
            likes_count_selectors = [
                '//*[contains(@text, "J\'aime")]',
                '//*[contains(@text, "likes")]',
                '//*[contains(@resource-id, "like_count")]'
            ]
            
            if not self._find_and_click(likes_count_selectors, timeout=5):
                self.logger.error("Failed to open likes list")
                return likers
            
            self._human_like_delay('navigation')
            
            self.logger.info(f"Extracting likers from post (max: {max_likers})")
            
            extracted_count = 0
            scroll_attempts = 0
            max_scroll_attempts = 10
            
            while extracted_count < max_likers and scroll_attempts < max_scroll_attempts:
                current_usernames = self.detection_actions.extract_usernames_from_follow_list()
                
                new_users_found = 0
                for username_found in current_usernames:
                    if username_found not in likers:
                        likers.append(username_found)
                        extracted_count += 1
                        new_users_found += 1
                        
                        if extracted_count >= max_likers:
                            break
                
                if new_users_found == 0:
                    break
                
                if extracted_count < max_likers:
                    self.scroll_actions.scroll_followers_list_down()
                    self._human_like_delay('scroll')
                    scroll_attempts += 1
            
            self.logger.info(f"Extraction completed: {len(likers)} likers extracted")
            
        except Exception as e:
            self.logger.error(f"Error extracting likers: {e}")
        
        return likers
    
    def extract_hashtag_posts(self, hashtag: str, max_posts: int = 20, 
                            post_type: str = "recent") -> List[Dict[str, Any]]:
        posts = []
        
        try:
            if not self._navigate_to_hashtag(hashtag):
                self.logger.error(f"Failed to navigate to #{hashtag}")
                return posts
            
            if post_type == "recent":
                recent_tab_selectors = [
                    '//*[contains(@text, "Récents")]',
                    '//*[contains(@text, "Recent")]'
                ]
                self._find_and_click(recent_tab_selectors, timeout=3)
            
            self.logger.info(f"Extracting posts from #{hashtag} (max: {max_posts}, type: {post_type})")
            
            extracted_count = 0
            scroll_attempts = 0
            max_scroll_attempts = 5
            
            while extracted_count < max_posts and scroll_attempts < max_scroll_attempts:
                visible_posts = self.detection_actions.count_visible_posts()
                
                for i in range(min(visible_posts, max_posts - extracted_count)):
                    try:
                        if self.click_actions.click_post_thumbnail(i):
                            self._human_like_delay('navigation')
                            
                            post_info = self._extract_post_information()
                            if post_info:
                                posts.append(post_info)
                                extracted_count += 1
                            
                            self._press_back(1)
                            self._human_like_delay('navigation')
                    
                    except Exception as e:
                        self.logger.debug(f"Error extracting post {i}: {e}")
                        continue
                
                if extracted_count < max_posts:
                    self.scroll_actions.scroll_post_grid_down()
                    self._human_like_delay('scroll')
                    scroll_attempts += 1
            
            self.logger.info(f"Extraction completed: {len(posts)} posts extracted")
            
        except Exception as e:
            self.logger.error(f"Error extracting hashtag: {e}")
        
        return posts
    
    def _navigate_to_post_via_url(self, post_url: str) -> bool:
        try:
            post_id_match = re.search(r'/p/([^/]+)/', post_url)
            if not post_id_match:
                return False
            
            post_id = post_id_match.group(1)
            
            import subprocess
            cmd = [
                'adb', 'shell', 'am', 'start',
                '-W', '-a', 'android.intent.action.VIEW',
                '-d', f'https://www.instagram.com/p/{post_id}/',
                'com.instagram.android'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                self._human_like_delay('navigation')
                return True
            
        except Exception as e:
            self.logger.debug(f"Error navigating to post: {e}")
        
        return False
    
    def _navigate_to_hashtag(self, hashtag: str) -> bool:
        try:
            if not self.nav_actions.navigate_to_search():
                return False
            
            search_term = f"#{hashtag}"
            if not self._find_and_click(self.detection_selectors.hashtag_search_bar_selectors, timeout=5):
                return False
            
            self._human_like_delay('click')
            self.device.send_keys(search_term)
            self._human_like_delay('typing')
            
            hashtag_result_selectors = [
                f'//*[contains(@text, "#{hashtag}")]',
                '//*[contains(@resource-id, "hashtag")]'
            ]
            
            if self._find_and_click(hashtag_result_selectors, timeout=5):
                self._human_like_delay('navigation')
                return True
            
        except Exception as e:
            self.logger.debug(f"Error navigating to hashtag: {e}")
        
        return False
    
    def _extract_post_information(self) -> Optional[Dict[str, Any]]:
        try:
            post_info = {
                'author_username': None,
                'caption': None,
                'likes_count': None,
                'comments_count': None,
                'is_video': False,
                'hashtags': [],
                'mentions': []
            }
            
            author_selectors = [
                '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_name"]',
                '//*[contains(@resource-id, "profile_name")]'
            ]
            author_text = self._get_text_from_element(author_selectors)
            if author_text:
                post_info['author_username'] = self._clean_username(author_text)
            
            caption_selectors = [
                '//*[@resource-id="com.instagram.android:id/row_feed_comment_text"]',
                '//*[contains(@resource-id, "caption")]'
            ]
            caption_text = self._get_text_from_element(caption_selectors)
            if caption_text:
                post_info['caption'] = caption_text
                post_info['hashtags'] = self.utils.extract_hashtags_from_text(caption_text)
                post_info['mentions'] = self.utils.extract_mentions_from_text(caption_text)
            
            likes_selectors = [
                '//*[contains(@text, "J\'aime")]',
                '//*[contains(@text, "likes")]'
            ]
            likes_text = self._get_text_from_element(likes_selectors)
            if likes_text:
                post_info['likes_count'] = self._extract_number_from_text(likes_text)
            
            return post_info
            
        except Exception as e:
            self.logger.debug(f"Error extracting post info: {e}")
            return None
    
    def get_content_statistics(self, username: str) -> Dict[str, Any]:
        stats = {
            'username': username,
            'total_posts': 0,
            'total_followers': 0,
            'total_following': 0,
            'engagement_rate': 0.0,
            'content_analysis': {}
        }
        
        try:
            # Navigation vers le profil
            if not self.nav_actions.navigate_to_profile(username):
                return stats
            
            stats['total_posts'] = self.detection_actions.get_posts_count() or 0
            stats['total_followers'] = self.detection_actions.get_followers_count() or 0
            stats['total_following'] = self.detection_actions.get_following_count() or 0
            
            if stats['total_followers'] > 0:
                posts_ratio = stats['total_posts'] / stats['total_followers']
                if posts_ratio > 0.01:
                    stats['engagement_rate'] = min(posts_ratio * 100, 10.0)
            
            stats['content_analysis'] = {
                'posts_per_follower_ratio': stats['total_posts'] / max(stats['total_followers'], 1),
                'followers_following_ratio': stats['total_followers'] / max(stats['total_following'], 1),
                'account_activity_level': 'high' if stats['total_posts'] > 100 else 'medium' if stats['total_posts'] > 20 else 'low'
            }
            
        except Exception as e:
            self.logger.error(f"Error getting content statistics: {e}")
        
        return stats
