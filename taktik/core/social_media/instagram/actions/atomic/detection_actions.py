from typing import Optional, Dict, Any, List, Tuple
from loguru import logger

from ..core.base_action import BaseAction
from ...ui.selectors import DETECTION_SELECTORS, PROFILE_SELECTORS, POST_SELECTORS


class DetectionActions(BaseAction):
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="instagram-detection-atomic")
        self.detection_selectors = DETECTION_SELECTORS
        self.selectors = PROFILE_SELECTORS
        self.post_selectors = POST_SELECTORS
    
    def _detect_element(self, selectors, element_name: str, log_found: bool = False) -> bool:
        """
        Generic method to detect if an element is present.
        
        Args:
            selectors: Selector or list of selectors
            element_name: Name for logging
            log_found: Whether to log when found
            
        Returns:
            True if element found, False otherwise
        """
        self.logger.debug(f"Detecting {element_name}")
        is_present = self._is_element_present(selectors)
        
        if log_found and is_present:
            self.logger.debug(f"✅ {element_name} detected")
        elif log_found:
            self.logger.debug(f"❌ {element_name} not found")
            
        return is_present
    
    def is_private_account(self) -> bool:
        return self._detect_element(self.detection_selectors.private_account_indicators, "Private account", log_found=True)
    
    def is_verified_account(self) -> bool:
        return self._detect_element(self.detection_selectors.verified_account_indicators, "Verified account")
    
    def is_business_account(self) -> bool:
        return self._detect_element(self.detection_selectors.business_account_indicators, "Business account")
    
    def get_username_from_profile(self) -> Optional[str]:
        try:
            # Try main username selectors
            for selector in self.selectors.username:
                element = self.device.xpath(selector)
                if element.exists:
                    username = element.get_text().strip()
                    if username:
                        username = username.replace('@', '')
                        self.logger.debug(f"Username found: {username}")
                        return username
            
            # Try content-desc fallback
            username_element = self.device.xpath(self.selectors.username_content_desc)
            if username_element.exists:
                username = username_element.get_attribute('content-desc', '').strip()
                if username and '@' in username:
                    username = username.split('@')[-1].split(' ')[0]
                    self.logger.debug(f"Username extracted from content-desc: {username}")
                    return username
            
            self.logger.warning("Cannot find username from profile")
            return None
            
        except Exception as e:
            self.logger.error(f"Error retrieving username: {e}")
            return None
    
    def get_full_name_from_profile(self) -> Optional[str]:
        return self._get_text_from_element(self.selectors.full_name)
    
    def get_biography_from_profile(self) -> Optional[str]:
        return self._get_text_from_element(self.selectors.bio)
    
    def _get_count_from_selectors(self, selectors) -> Optional[int]:
        """Generic method to get count from selectors."""
        text = self._get_text_from_element(selectors)
        if text:
            return self._extract_number_from_text(text)
        return None
    
    def get_followers_count_text(self) -> Optional[str]:
        return self._get_text_from_element(self.selectors.followers_count)
    
    def get_following_count_text(self) -> Optional[str]:
        return self._get_text_from_element(self.selectors.following_count)
    
    def get_posts_count_text(self) -> Optional[str]:
        return self._get_text_from_element(self.selectors.posts_count)
    
    def get_followers_count(self) -> Optional[int]:
        return self._get_count_from_selectors(self.selectors.followers_count)
    
    def get_following_count(self) -> Optional[int]:
        return self._get_count_from_selectors(self.selectors.following_count)
    
    def get_posts_count(self) -> Optional[int]:
        return self._get_count_from_selectors(self.selectors.posts_count)
    
    def is_on_home_screen(self) -> bool:
        return self._detect_element(self.detection_selectors.home_screen_indicators, "Home screen")
    
    def is_on_search_screen(self) -> bool:
        return self._detect_element(self.detection_selectors.search_screen_indicators, "Search screen")
    
    def is_on_profile_screen(self) -> bool:
        is_profile = self._is_element_present(self.detection_selectors.profile_screen_indicators)
        if is_profile:
            self.logger.debug("✅ Profile screen detected")
        else:
            self.logger.debug("❌ Not on profile screen")
        
        return is_profile
    
    def is_on_own_profile(self) -> bool:
        if not self.is_on_profile_screen():
            self.logger.debug("❌ Not on profile screen")
            return False
        
        has_edit_profile = self._is_element_present(self.detection_selectors.own_profile_indicators)
        is_own_profile = has_edit_profile
        
        self.logger.debug(f"Profile detection - Edit profile: {has_edit_profile}")
        
        if is_own_profile:
            self.logger.debug("✅ Confirmed: on own profile")
        else:
            self.logger.debug("❌ Not on own profile")
            
        return is_own_profile
    
    def is_followers_list_open(self) -> bool:
        return self._detect_element(self.detection_selectors.followers_list_indicators, "Followers list")
    
    def is_following_list_open(self) -> bool:
        return self.is_followers_list_open()
    
    def is_followers_list_limited(self) -> bool:
        """
        Detect if the followers list is limited (Meta Verified / Business accounts).
        Instagram shows: "We limit the number of followers shown for certain Meta Verified and Business accounts."
        """
        return self._detect_element(self.detection_selectors.limited_followers_indicators, "Limited followers list", log_found=False)
    
    def is_followers_list_end_reached(self) -> bool:
        """
        Detect if we've reached the end of the followers list.
        Instagram shows: "And X others" when there are more followers but they're hidden.
        """
        return self._detect_element(self.detection_selectors.followers_list_end_indicators, "Followers list end", log_found=False)
    
    def is_suggestions_section_visible(self) -> bool:
        """
        Detect if the suggestions section is visible (indicates end of real followers).
        Instagram shows: "Suggested for you" header after the last real follower.
        """
        return self._detect_element(self.detection_selectors.suggestions_section_indicators, "Suggestions section", log_found=False)
    
    def is_post_grid_visible(self) -> bool:
        return self._detect_element(self.detection_selectors.post_grid_visibility_indicators, "Post grid")
    
    def is_story_viewer_open(self) -> bool:
        return self._detect_element(self.detection_selectors.story_viewer_indicators, "Story viewer")
    
    def count_visible_posts(self) -> int:
        count = 0
        for selector in self.detection_selectors.post_thumbnail_selectors:
            try:
                elements = self.device.xpath(selector)
                if elements.exists:
                    count = len(elements.all())
                    break
            except Exception:
                continue
        
        self.logger.debug(f"{count} visible posts in grid")
        return count
    
    def count_visible_stories(self) -> int:
        try:
            count = 0
            for selector in self.detection_selectors.story_ring_indicators:
                elements = self.device.xpath(selector).all()
                if elements:
                    count = len(elements)
                    break
            
            self.logger.debug(f"{count} visible stories")
            return count
            
        except Exception as e:
            self.logger.debug(f"Error counting stories: {e}")
            return 0
    
    def get_story_count_from_viewer(self) -> tuple[int, int]:
        try:
            from ...ui.selectors import STORY_SELECTORS
            
            element = self.device.xpath(STORY_SELECTORS.story_viewer_text_container).get()
            
            if element:
                content_desc = element.attrib.get('content-desc', '')
                self.logger.debug(f"📱 Story viewer content-desc: {content_desc}")
                
                import re
                pattern = r'story\s+(\d+)\s+of\s+(\d+)'
                match = re.search(pattern, content_desc, re.IGNORECASE)
                
                if match:
                    current_story = int(match.group(1))
                    total_stories = int(match.group(2))
                    self.logger.info(f"📊 Stories detected: {current_story}/{total_stories}")
                    return (current_story, total_stories)
                else:
                    self.logger.debug(f"⚠️ Pattern 'story X of Y' not found in: {content_desc}")
                    return (0, 0)
            else:
                self.logger.debug("⚠️ Element story_viewer_text_container not found")
                return (0, 0)
                
        except Exception as e:
            self.logger.debug(f"Error extracting story count: {e}")
            return (0, 0)
    
    def has_stories(self) -> bool:
        try:
            return self.count_visible_stories() > 0
        except Exception as e:
            self.logger.debug(f"Error checking stories: {e}")
            return False

    def extract_usernames_from_follow_list(self) -> List[str]:
        usernames = []
        
        for selector in self.detection_selectors.follow_list_username_selectors:
            try:
                elements = self.device.xpath(selector)
                if elements.exists:
                    for element in elements.all():
                        username_text = element.text
                        if username_text:
                            clean_username = self._clean_username(username_text)
                            if self._is_valid_username(clean_username):
                                usernames.append(clean_username)
                    break
            except Exception as e:
                self.logger.debug(f"Error extracting usernames: {e}")
                continue
        
        unique_usernames = list(dict.fromkeys(usernames))
        self.logger.debug(f"{len(unique_usernames)} usernames extracted from list")
        return unique_usernames
    
    def get_visible_followers_with_elements(self) -> List[Dict[str, Any]]:
        """
        Récupère les followers visibles avec leurs éléments cliquables.
        Utilisé pour le nouveau workflow d'interaction directe.
        
        Returns:
            Liste de dicts avec 'username' et 'element' (élément cliquable)
        """
        followers = []
        
        for selector in self.detection_selectors.follow_list_username_selectors:
            try:
                elements = self.device.xpath(selector)
                if elements.exists:
                    for element in elements.all():
                        username_text = element.text
                        if username_text:
                            clean_username = self._clean_username(username_text)
                            if self._is_valid_username(clean_username):
                                followers.append({
                                    'username': clean_username,
                                    'element': element
                                })
                    break
            except Exception as e:
                self.logger.debug(f"Error getting followers with elements: {e}")
                continue
        
        self.logger.debug(f"{len(followers)} clickable followers found")
        return followers
    
    def click_follower_in_list(self, username: str) -> bool:
        """
        Clique sur un follower spécifique dans la liste.
        
        Args:
            username: Le username du follower à cliquer
            
        Returns:
            True si le clic a réussi
        """
        try:
            # Chercher l'élément avec ce username
            for selector in self.detection_selectors.follow_list_username_selectors:
                elements = self.device.xpath(selector)
                if elements.exists:
                    for element in elements.all():
                        element_text = element.text
                        if element_text:
                            clean_text = self._clean_username(element_text)
                            if clean_text == username:
                                element.click()
                                self.logger.debug(f"✅ Clicked on @{username} in list")
                                return True
            
            self.logger.warning(f"❌ Could not find @{username} in visible list")
            return False
            
        except Exception as e:
            self.logger.error(f"Error clicking follower @{username}: {e}")
            return False
    
    def detect_error_messages(self) -> List[str]:
        errors = []
        for selector in self.detection_selectors.error_message_indicators:
            try:
                elements = self.device.xpath(selector)
                if elements.exists:
                    for element in elements.all():
                        error_text = element.get_text()
                        if error_text and error_text not in errors:
                            errors.append(error_text)
            except Exception:
                continue
        
        if errors:
            self.logger.warning(f"{len(errors)} error messages detected")
        
        return errors
    
    def is_rate_limited(self) -> bool:
        is_limited = self._detect_element(self.detection_selectors.rate_limit_indicators, "Rate limit")
        if is_limited:
            self.logger.warning("Rate limit detected!")
        return is_limited
    
    def is_login_required(self) -> bool:
        return self._detect_element(self.detection_selectors.login_required_indicators, "Login required")
    
    def detect_popup_or_modal(self) -> Optional[str]:
        for popup_type, selector in self.detection_selectors.popup_types.items():
            if self._is_element_present([selector]):
                self.logger.debug(f"Popup detected: {popup_type}")
                return popup_type
        
        return None
    
    def get_screen_state_summary(self) -> Dict[str, Any]:
        return {
            'is_home': self.is_on_home_screen(),
            'is_search': self.is_on_search_screen(),
            'is_profile': self.is_on_profile_screen(),
            'is_followers_list': self.is_followers_list_open(),
            'is_post_grid': self.is_post_grid_visible(),
            'is_story_viewer': self.is_story_viewer_open(),
            'visible_posts': self.count_visible_posts(),
            'visible_stories': self.count_visible_stories(),
            'errors': self.detect_error_messages(),
            'is_rate_limited': self.is_rate_limited(),
            'popup_detected': self.detect_popup_or_modal()
        }
    
    def is_post_liked(self) -> bool:
        return self._detect_element(self.detection_selectors.liked_button_indicators, "Liked button", log_found=True)
    
    def is_on_post_screen(self) -> bool:
        return self._detect_element(self.detection_selectors.post_screen_indicators, "Post screen")
    
    def is_reel_post(self) -> bool:
        return self._detect_element(self.detection_selectors.reel_indicators, "Reel post")
    
    def is_in_suggestions_section(self) -> bool:
        """
        Détecte si on est dans la section suggestions (après la liste des vrais followers).
        Retourne True si on voit des éléments de suggestions.
        """
        return self._detect_element(
            self.detection_selectors.suggestions_section_indicators, 
            "Suggestions section"
        )
    
    def is_loading_spinner_visible(self) -> bool:
        """
        Détecte si un spinner de chargement est visible (Instagram charge du contenu).
        """
        return self._detect_element(
            self.detection_selectors.loading_spinner_indicators,
            "Loading spinner"
        )
    
    def get_profile_flags_batch(self) -> Dict[str, bool]:
        """
        Get all profile boolean flags in a single XML dump.
        Much faster than individual checks (~1s vs ~20s).
        
        Returns:
            Dict with keys: is_private, is_verified, is_business
        """
        selectors_dict = {
            'is_private': self.detection_selectors.private_account_indicators,
            'is_verified': self.detection_selectors.verified_account_indicators,
            'is_business': self.detection_selectors.business_account_indicators,
        }
        
        results = self.device.batch_xpath_check(selectors_dict)
        self.logger.debug(f"📊 Batch profile flags: private={results.get('is_private')}, verified={results.get('is_verified')}, business={results.get('is_business')}")
        return results
    
    def get_profile_text_batch(self) -> Dict[str, Optional[str]]:
        """
        Get username, full_name, bio in a single XML dump.
        Much faster than individual calls (~1s vs ~9s).
        
        Returns:
            Dict with keys: username, full_name, biography
        """
        from lxml import etree
        
        results = {
            'username': None,
            'full_name': None,
            'biography': None
        }
        
        xml_content = self.device.get_xml_dump()
        if not xml_content:
            return results
        
        try:
            tree = etree.fromstring(xml_content.encode('utf-8'))
            
            # Extract username
            for selector in self.selectors.username:
                try:
                    elements = tree.xpath(selector)
                    if elements:
                        text = elements[0].get('text', '').strip()
                        if text:
                            results['username'] = text.replace('@', '')
                            break
                except Exception:
                    continue
            
            # Extract full name
            for selector in self.selectors.full_name:
                try:
                    elements = tree.xpath(selector)
                    if elements:
                        text = elements[0].get('text', '').strip()
                        if text:
                            results['full_name'] = text
                            break
                except Exception:
                    continue
            
            # Extract biography
            for selector in self.selectors.bio:
                try:
                    elements = tree.xpath(selector)
                    if elements:
                        text = elements[0].get('text', '').strip()
                        if text:
                            results['biography'] = text
                            break
                except Exception:
                    continue
            
            if results['username']:
                self.logger.debug(f"📊 Batch text: @{results['username']}, name={results['full_name']}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in batch text extraction: {e}")
            return results

    def get_enriched_profile_data(self) -> Dict[str, Any]:
        """
        Get all enriched profile data in a single XML dump.
        Extracts: username, full_name, bio, business_category, website, linked_accounts.
        Also detects if bio has "more" button to expand.
        
        Returns:
            Dict with all enriched profile fields
        """
        from lxml import etree
        
        results = {
            'username': None,
            'full_name': None,
            'biography': None,
            'business_category': None,  # "Digital creator", "Entrepreneur", etc.
            'website': None,
            'linked_accounts': [],  # List of {platform, name, url}
            'bio_truncated': False,  # True if "more" button detected
        }
        
        xml_content = self.device.get_xml_dump()
        if not xml_content:
            return results
        
        try:
            tree = etree.fromstring(xml_content.encode('utf-8'))
            
            # Extract username from action bar
            username_selectors = [
                '//*[@resource-id="com.instagram.android:id/action_bar_title"]',
                '//*[@resource-id="com.instagram.android:id/action_bar_username_container"]//android.widget.TextView',
            ]
            for selector in username_selectors:
                try:
                    elements = tree.xpath(selector)
                    if elements:
                        text = elements[0].get('text', '').strip()
                        if text:
                            results['username'] = text.replace('@', '')
                            break
                except Exception:
                    continue
            
            # Extract full name
            full_name_selectors = [
                '//*[@resource-id="com.instagram.android:id/profile_header_full_name_above_vanity"]',
                '//*[@resource-id="com.instagram.android:id/profile_header_full_name"]',
            ]
            for selector in full_name_selectors:
                try:
                    elements = tree.xpath(selector)
                    if elements:
                        text = elements[0].get('text', '').strip()
                        if text:
                            results['full_name'] = text
                            break
                except Exception:
                    continue
            
            # Extract business category (Digital creator, Entrepreneur, etc.)
            category_selectors = [
                '//*[@resource-id="com.instagram.android:id/profile_header_business_category"]',
            ]
            for selector in category_selectors:
                try:
                    elements = tree.xpath(selector)
                    if elements:
                        text = elements[0].get('text', '').strip()
                        if text:
                            results['business_category'] = text
                            break
                except Exception:
                    continue
            
            # Extract biography from compose view
            bio_selectors = [
                '//*[@resource-id="com.instagram.android:id/profile_user_info_compose_view"]//android.widget.TextView',
                '//*[@resource-id="com.instagram.android:id/profile_user_info_compose_view"]//*[@class="android.widget.TextView"]',
                '//*[@resource-id="com.instagram.android:id/profile_header_bio_text"]',
            ]
            for selector in bio_selectors:
                try:
                    elements = tree.xpath(selector)
                    self.logger.debug(f"Bio selector '{selector[:60]}...' found {len(elements)} elements")
                    # Iterate through all TextViews to find one with actual bio text
                    for element in elements:
                        text = element.get('text', '').strip()
                        # Skip empty, "See translation", or very short texts that are likely not bio
                        if text and text != 'See translation' and len(text) > 3:
                            # Check if bio is truncated (contains "more" or "… more")
                            if 'more' in text.lower() and ('…' in text or '...' in text):
                                results['bio_truncated'] = True
                            results['biography'] = text
                            self.logger.debug(f"Bio found: {text[:50]}...")
                            break
                    if results.get('biography'):
                        break
                except Exception as e:
                    self.logger.debug(f"Bio selector error: {e}")
                    continue
            
            # Extract website from profile_links_view
            website_selectors = [
                '//*[@resource-id="com.instagram.android:id/profile_links_view"]//*[@resource-id="com.instagram.android:id/text_view"]',
                '//*[@resource-id="com.instagram.android:id/profile_header_website"]',
            ]
            for selector in website_selectors:
                try:
                    elements = tree.xpath(selector)
                    if elements:
                        text = elements[0].get('text', '').strip()
                        if text:
                            results['website'] = text
                            break
                except Exception:
                    continue
            
            # Extract linked accounts from banner_row (Thread, Facebook, etc.)
            banner_selectors = [
                '//*[@resource-id="com.instagram.android:id/banner_row"]//*[@resource-id="com.instagram.android:id/profile_header_banner_item_layout"]',
            ]
            for selector in banner_selectors:
                try:
                    elements = tree.xpath(selector)
                    for elem in elements:
                        # Get the title (account name)
                        title_elem = elem.xpath('.//*[@resource-id="com.instagram.android:id/profile_header_banner_item_title"]')
                        if title_elem:
                            account_name = title_elem[0].get('text', '').strip()
                            if account_name:
                                # Try to detect platform from icon or context
                                # For now, just store the name
                                results['linked_accounts'].append({
                                    'name': account_name,
                                    'platform': 'unknown'  # Could be Thread, Facebook, etc.
                                })
                except Exception:
                    continue
            
            if results['username']:
                self.logger.debug(f"📊 Enriched profile: @{results['username']}, category={results['business_category']}, website={results['website']}, bio={results.get('biography', 'N/A')[:50] if results.get('biography') else 'None'}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in enriched profile extraction: {e}")
            return results

    def click_bio_more_button(self) -> bool:
        """
        Click on the 'more' button in bio to expand truncated biography.
        
        The bio TextView contains both @username links and "more" text.
        Clicking in the center might trigger a @username link instead of "more".
        We need to click on the RIGHT side of the TextView where "more" is located.
        
        Returns:
            True if button was found and clicked, False otherwise
        """
        try:
            # Look for text containing "more" in the bio area
            more_selectors = [
                '//*[@resource-id="com.instagram.android:id/profile_user_info_compose_view"]//*[contains(@text, "more")]',
                '//*[contains(@text, "… more")]',
                '//*[contains(@text, "...more")]',
            ]
            
            for selector in more_selectors:
                element = self.device.xpath(selector)
                if element.exists:
                    # Get element bounds to click on the RIGHT side where "more" is
                    try:
                        info = element.info
                        bounds = info.get('bounds', {})
                        if bounds:
                            # Click on the right side of the element (where "more" text is)
                            # Use 90% of the width to avoid edge issues
                            right = bounds.get('right', 0)
                            left = bounds.get('left', 0)
                            top = bounds.get('top', 0)
                            bottom = bounds.get('bottom', 0)
                            
                            # Calculate click position: far right side, vertically centered
                            click_x = left + int((right - left) * 0.92)  # 92% from left = near right edge
                            click_y = (top + bottom) // 2  # Vertically centered
                            
                            self.logger.debug(f"Clicking 'more' at right side: ({click_x}, {click_y}) - bounds: [{left},{top}][{right},{bottom}]")
                            self.device.click(click_x, click_y)
                            self._human_like_delay('click')
                            self.logger.debug("Clicked 'more' button to expand bio (right-side click)")
                            return True
                    except Exception as e:
                        self.logger.debug(f"Could not get bounds for right-side click: {e}, falling back to center click")
                    
                    # Fallback: center click (may trigger @username links)
                    element.click()
                    self.logger.debug("Clicked 'more' button to expand bio (center click fallback)")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error clicking bio more button: {e}")
            return False
