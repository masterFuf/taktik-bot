"""Follower extraction and filtering from Instagram profiles."""

import time
from typing import Dict, Any, List, Optional

from ....common import DatabaseHelpers


class FollowerExtractionMixin:
    """Mixin: extract followers from profile lists, scroll & filter."""
    
    def extract_followers_from_profile(self, target_username: str, 
                                     max_followers: int = 50,
                                     filter_criteria: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        try:
            self.logger.info(f"Extracting followers from @{target_username} (max: {max_followers})")
            
            if not self.nav_actions.navigate_to_profile(target_username):
                self.logger.error(f"Failed to navigate to @{target_username}")
                return []
            
            # Vérifier que le profil est accessible
            if self.detection_actions.is_private_account():
                self.logger.warning(f"@{target_username} is a private account")
                return []
            
            if not self.nav_actions.open_followers_list():
                self.logger.error("Failed to open followers list")
                return []
            
            self._random_sleep()
            
            followers = self._extract_followers_with_scroll(max_followers)
            
            if not followers:
                self.logger.warning("No followers extracted")
                return []
            
            self.logger.info(f"{len(followers)} followers extracted from @{target_username}")
            
            if filter_criteria:
                filtered_followers = self._filter_followers(followers, filter_criteria)
                self.logger.info(f"{len(filtered_followers)}/{len(followers)} followers after filtering")
                return filtered_followers
            
            return followers
            
        except Exception as e:
            self.logger.error(f"Error extracting followers from @{target_username}: {e}")
            return []
    
    def _extract_followers_with_scroll(self, max_followers: int, account_id: int = None, target_username: str = None, max_followers_count: int = 0) -> List[Dict[str, Any]]:
        followers_data = []
        processed_usernames = set()
        scroll_attempts = 0
        max_scroll_attempts = 10
        total_usernames_seen = 0  # Track total usernames seen (including filtered ones)
        
        def follower_callback(follower_username):
            if follower_username in processed_usernames:
                return True
            
            processed_usernames.add(follower_username)
            
            if account_id:
                try:
                    should_skip, skip_reason = DatabaseHelpers.is_profile_skippable(
                        follower_username, account_id, hours_limit=24*60
                    )
                    if should_skip:
                        self.logger.info(f"Profile @{follower_username} skipped ({skip_reason})")
                        return True
                except Exception as e:
                    self.logger.warning(f"Error checking @{follower_username}: {e}")
            
            follower_data = {
                'username': follower_username,
                'source_account_id': account_id,
                'source_username': target_username,
                'full_name': None,
                'is_verified': False,
                'is_private': False,
                'followers_count': None,
                'following_count': None,
                'timestamp': time.time()
            }
            followers_data.append(follower_data)
            
            if len(followers_data) >= max_followers:
                return False
            
            return True
        
        self.logger.info(f"Extracting with individual filtering (max: {max_followers})")
        
        while len(followers_data) < max_followers and scroll_attempts < max_scroll_attempts:
            current_usernames = self.content_business.extract_usernames_from_follow_list()
            
            if not current_usernames:
                self.logger.debug("No new followers found")
                scroll_attempts += 1
            else:
                new_found = 0
                for username in current_usernames:
                    if username:
                        total_usernames_seen += 1
                        continue_extraction = follower_callback(username)
                        if continue_extraction:
                            new_found += 1
                        else:
                            self.logger.info(f"{len(followers_data)} eligible followers collected")
                            return followers_data
                
                # Check if we've seen approximately all followers from this profile
                if max_followers_count > 0 and total_usernames_seen >= max_followers_count * 0.95:
                    self.logger.info(f"🏁 Reached end of list: seen {total_usernames_seen}/{max_followers_count} followers from @{target_username}")
                    break
                
                if new_found == 0:
                    scroll_attempts += 1
                    if scroll_attempts >= max_scroll_attempts:
                        self.logger.info(f"No new eligible followers found after {scroll_attempts} scrolls - end of list reached")
                        break
                else:
                    scroll_attempts = 0
                
                self.logger.debug(f"{new_found} new eligible, total: {len(followers_data)} (seen: {total_usernames_seen}/{max_followers_count if max_followers_count > 0 else '?'})")
            
            if len(followers_data) < max_followers:
                load_more_result = self.scroll_actions.check_and_click_load_more()
                if load_more_result:
                    self.logger.info("'Load more' button clicked, 25 new followers loaded")
                    self._human_like_delay('load_more')
                    scroll_attempts = 0
                elif load_more_result is False:
                    self.logger.info("End of followers list detected")
                    break
                elif load_more_result is None:
                    self.scroll_actions.scroll_followers_list_down()
                    self._human_like_delay('scroll')
        
        self.logger.info(f"Extraction completed: {len(followers_data)} eligible followers")
        return followers_data
    
    def _filter_followers(self, followers: List[Dict[str, Any]], 
                         criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        filtered = []
        
        for follower in followers:
            username = follower.get('username', '')
            if not username:
                continue
            
            # DISABLED: Bot username detection - too many false positives
            # if criteria.get('exclude_bots', True):
            #     if self.utils.is_likely_bot_username(username):
            #         continue
            
            filtered.append(follower)
        
        return filtered
