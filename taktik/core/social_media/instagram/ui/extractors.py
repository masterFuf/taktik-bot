import re
import time
from typing import Optional, List, Any, Dict
from loguru import logger
log = logger.bind(module="instagram-ui-extractors")


class InstagramUIExtractors:
    def __init__(self, device):
        self.device = device
        
        from .selectors import POST_SELECTORS, POPUP_SELECTORS, DETECTION_SELECTORS
        self.post_selectors = POST_SELECTORS
        self.popup_selectors = POPUP_SELECTORS
        self.detection_selectors = DETECTION_SELECTORS
    
    def extract_post_stats_atomic(self) -> Dict[str, int]:
        """
        Extract likes and comments counts atomically from the same carousel element.
        This prevents timing issues during scrolling where likes and comments 
        might be read from different posts.
        
        Returns:
            dict: {'likes': int, 'comments': int} or None if extraction failed
        """
        try:
            # Try to find carousel elements that contain both likes and comments in content-desc
            for selector in self.detection_selectors.carousel_selectors:
                try:
                    elements = self.device.xpath(selector).all()
                    for element in elements:
                        element_info = element.info
                        content_desc = element_info.get('contentDescription', '')
                        
                        if not content_desc:
                            continue
                        
                        # Extract likes
                        likes_match = re.search(
                            r'(\d+(?:[,.]\d+)?(?:\s?[KkMmBb])?)\s*(?:like|j\'aime)',
                            content_desc,
                            re.IGNORECASE
                        )
                        
                        # Extract comments
                        comments_match = re.search(
                            r'(\d+(?:[,.]\d+)?(?:\s?[KkMmBb])?)\s*(?:comment|commentaire)',
                            content_desc,
                            re.IGNORECASE
                        )
                        
                        if likes_match and comments_match:
                            likes_text = likes_match.group(1)
                            comments_text = comments_match.group(1)
                            
                            likes_count = self.parse_instagram_number(likes_text)
                            comments_count = self.parse_instagram_number(comments_text)
                            
                            if likes_count >= 0 and comments_count >= 0:
                                log.debug(f"✅ Post stats extracted atomically from carousel: {likes_count} likes, {comments_count} comments")
                                log.debug(f"   Source content-desc: {content_desc[:100]}...")
                                return {
                                    'likes': likes_count,
                                    'comments': comments_count
                                }
                        
                except Exception as e:
                    log.debug(f"Error with carousel selector {selector}: {e}")
                    continue
            
            log.debug("⚠️ Could not extract post stats atomically, falling back to separate extraction")
            return None
            
        except Exception as e:
            log.error(f"Error in atomic extraction: {e}")
            return None
    
    def parse_instagram_number(self, text: str) -> int:
        """Parse Instagram number - delegates to parse_number_from_text"""
        return parse_number_from_text(text)
    
    def is_like_count_text(self, text: str) -> bool:
        if not text:
            return False
        
        cleaned_text = re.sub(r'[\s,.\u00A0\u2000-\u200F\u2028-\u202F\u205F\u3000]+', '', text)
        
        if cleaned_text.endswith('K') or cleaned_text.endswith('k'):
            try:
                number = float(cleaned_text[:-1])
                return number > 0
            except ValueError:
                return False
        elif cleaned_text.endswith('M') or cleaned_text.endswith('m'):
            try:
                number = float(cleaned_text[:-1])
                return number > 0
            except ValueError:
                return False
        
        try:
            count = int(cleaned_text)
            return count > 0
        except ValueError:
            return False
    
    def extract_likes_count_from_ui(self) -> int:
        try:
            # Try Reel like count selector first
            try:
                element = self.device.xpath(self.detection_selectors.reel_like_count_selector)
                if element.exists:
                    content_desc = element.info.get('contentDescription', '')
                    if content_desc:
                        # Parse "Like number is16. View likes" or "Like number is16"
                        like_match = re.search(r'Like number is\s*(\d+(?:[,.]?\d+)?(?:\s?[KkMmBb])?)', content_desc, re.IGNORECASE)
                        if like_match:
                            likes_text = like_match.group(1)
                            likes_count = self.parse_instagram_number(likes_text)
                            if likes_count >= 0:
                                log.debug(f"✅ Likes extracted from Reel format: {likes_count}")
                                return likes_count
            except Exception as e:
                log.debug(f"Reel like selector not found or error: {e}")
            
            all_photo_elements = self.device.xpath(self.post_selectors.photo_imageview_selector).all()
            
            for i, element in enumerate(all_photo_elements):
                try:
                    element_info = element.info
                    content_desc = element_info.get('contentDescription', '')
                    
                    if content_desc:
                        apostrophe_variants = ["J'aime", "J'aime", "J`aime", "Jaime", "J'aime"]
                        has_jaime = any(variant in content_desc for variant in apostrophe_variants)
                        has_likes = 'likes' in content_desc
                        has_aime = 'aime' in content_desc.lower()
                        
                        if has_jaime or has_likes or has_aime:
                            like_match = re.search(
                                r"(\d+(?:\s\d+)*(?:[,.]?\d+)?(?:\s?[KkMmBb])?)\s*J[''`'ʼ']?aime",
                                content_desc,
                                re.IGNORECASE
                            )
                            
                            if not like_match:
                                like_match = re.search(
                                    r"(\d+(?:\s\d+)*(?:[,.]?\d+)?(?:\s?[KkMmBb])?)\s+aime",
                                    content_desc,
                                    re.IGNORECASE
                                )
                            
                            if like_match:
                                likes_text = like_match.group(1)
                                likes_count = self.parse_instagram_number(likes_text)
                                if likes_count >= 0:
                                    log.debug(f"✅ Likes extracted from content-desc: {likes_count} (text: '{likes_text}')")
                                    return likes_count
                except Exception as e:
                    log.debug(f"Error with photo element {i+1}: {e}")
                    continue
            
            for selector in self.post_selectors.button_like_selectors:
                try:
                    elements = self.device.xpath(selector).all()
                    max_likes = 0
                    max_text = ""
                    
                    for element in elements:
                        element_info = element.info
                        text = element_info.get('text', '')
                        if text:
                            likes_count = self.parse_instagram_number(text)
                            if likes_count > max_likes:
                                max_likes = likes_count
                                max_text = text
                    
                    if max_likes > 0:
                        log.debug(f"✅ Likes extracted from button: {max_likes} (text: '{max_text}')")
                        return max_likes
                        
                except Exception as e:
                    log.debug(f"Error with button selector {selector}: {e}")
                    continue
            
            log.debug("⚠️ Like count not found")
            return 0
            
        except Exception as e:
            log.error(f"Error extracting likes: {e}")
            return 0
    
    def extract_comments_count_from_ui(self) -> int:
        try:
            # Try Reel comment count selector first
            try:
                element = self.device.xpath(self.detection_selectors.reel_comment_count_selector)
                if element.exists:
                    content_desc = element.info.get('contentDescription', '')
                    if content_desc:
                        comment_match = re.search(r'Comment number is\s*(\d+(?:[,.]?\d+)?(?:\s?[KkMmBb])?)', content_desc, re.IGNORECASE)
                        if comment_match:
                            comments_text = comment_match.group(1)
                            comments_count = self.parse_instagram_number(comments_text)
                            if comments_count >= 0:
                                log.debug(f"✅ Comments extracted from Reel format: {comments_count}")
                                return comments_count
            except Exception as e:
                log.debug(f"Reel comment selector not found or error: {e}")
            
            all_photo_elements = self.device.xpath(self.post_selectors.photo_imageview_selector).all()
            
            for i, element in enumerate(all_photo_elements):
                try:
                    element_info = element.info
                    content_desc = element_info.get('contentDescription', '')
                    
                    if content_desc and ('commentaire' in content_desc or 'comment' in content_desc):
                        comment_match = re.search(
                            r'(\d+(?:\s?\d+)*(?:[,.]?\d+)?(?:\s?[KkMmBb])?)\s*(?:commentaire|comment)',
                            content_desc
                        )
                        if comment_match:
                            comments_text = comment_match.group(1)
                            comments_count = self.parse_instagram_number(comments_text)
                            if comments_count >= 0:
                                log.debug(f"✅ Comments extracted from content-desc: {comments_count}")
                                return comments_count
                except Exception as e:
                    log.debug(f"Error with photo element {i+1}: {e}")
                    continue
            
            for selector in self.post_selectors.button_like_selectors:
                try:
                    elements = self.device.xpath(selector).all()
                    numeric_buttons = []
                    for element in elements:
                        element_info = element.info
                        text = element_info.get('text', '')
                        if text:
                            parsed_number = self.parse_instagram_number(text)
                            if parsed_number >= 0:
                                numeric_buttons.append((parsed_number, text))
                    
                    if len(numeric_buttons) >= 2:
                        numeric_buttons.sort(reverse=True, key=lambda x: x[0])
                        comments_count, comments_text = numeric_buttons[1]
                        log.debug(f"✅ Comments extracted from buttons: {comments_count}")
                        return comments_count
                    elif len(numeric_buttons) == 1:
                        return 0
                        
                except Exception as e:
                    log.debug(f"Error with button selector {selector}: {e}")
                    continue
            
            log.debug("⚠️ Comment count not found")
            return 0
            
        except Exception as e:
            log.error(f"Error extracting comments: {e}")
            return 0
    
    
    def find_like_count_element(self, logger_instance=None):
        logger_to_use = logger_instance if logger_instance else log
        
        for selector in self.post_selectors.like_count_selectors:
            try:
                elements = self.device.xpath(selector).all()
                logger_to_use.debug(f"Selector '{selector}' found {len(elements)} elements")
                
                for element in elements:
                    try:
                        text = None
                        if hasattr(element, 'text'):
                            text = element.text
                        elif hasattr(element, 'get_text'):
                            text = element.get_text()
                        elif hasattr(element, 'attrib') and 'text' in element.attrib:
                            text = element.attrib['text']
                        
                        content_desc = None
                        try:
                            element_info = element.info
                            content_desc = element_info.get('contentDescription', '')
                        except:
                            pass
                        
                        logger_to_use.debug(f"Checking element - text: '{text}', content-desc: '{content_desc}' (clickable: {element.attrib.get('clickable', 'unknown')})")
                        
                        if text and self.is_like_count_text(text):
                            logger_to_use.info(f"✅ Valid like counter found (post): {selector} (text: '{text}')")
                            return element
                        elif content_desc and ('Like number is' in content_desc or 'View likes' in content_desc):
                            logger_to_use.info(f"✅ Valid like counter found (Reel): {selector} (content-desc: '{content_desc}')")
                            return element
                    except Exception as e:
                        logger_to_use.debug(f"Error checking element: {e}")
                        continue
            except Exception as e:
                logger_to_use.debug(f"Error with selector {selector}: {e}")
                continue
        
        logger_to_use.warning("❌ No like counter found with all selectors")
        return None
    
    def extract_usernames_from_likers_popup(
        self,
        max_interactions: int = None,
        automation=None,
        logger_instance=None,
        add_initial_sleep: bool = False,
        current_max_interactions_attr: Any = None
    ) -> List[str]:

        logger_to_use = logger_instance if logger_instance else log
        
        usernames = []
        
        if max_interactions is not None:
            target_count = max_interactions
        elif current_max_interactions_attr is not None:
            target_count = current_max_interactions_attr
        else:
            target_count = 30
        
        max_scrolls = min(200, target_count * 2)
        scroll_count = 0
        consecutive_no_new = 0
        max_consecutive = 20
        
        logger_to_use.info(f"🔄 Optimized extraction for {target_count} users")
        
        if add_initial_sleep:
            logger_to_use.debug("⏳ Waiting for usernames to load (2s)...")
            time.sleep(2.0)
        
        try:
            while scroll_count < max_scrolls and len(usernames) < target_count:
                users_before = len(usernames)
                
                new_users = self.extract_visible_usernames(logger_instance=logger_to_use)
                
                for username in new_users:
                    if username not in usernames and len(usernames) < target_count:
                        if automation:
                            from ..actions.business.common.database_helpers import DatabaseHelpers
                            account_id = getattr(automation, 'active_account_id', None)
                            if DatabaseHelpers.is_profile_already_processed(username, account_id):
                                continue
                        
                        usernames.append(username)
                        logger_to_use.debug(f"✅ Eligible user: @{username} ({len(usernames)}/{target_count})")
                        
                        if len(usernames) >= target_count:
                            logger_to_use.info(f"🎯 Target reached! {len(usernames)} users collected")
                            break
                
                if len(usernames) >= target_count:
                    logger_to_use.info(f"🏁 Optimized stop: target of {target_count} users reached")
                    break
                
                if len(usernames) == users_before:
                    consecutive_no_new += 1
                    logger_to_use.debug(f"⚠️ No new eligible user found (attempt {consecutive_no_new}/{max_consecutive})")
                    
                    if consecutive_no_new >= max_consecutive:
                        logger_to_use.info(f"🛑 Stop: {consecutive_no_new} consecutive attempts without new eligible users")
                        break
                else:
                    consecutive_no_new = 0
                    gained = len(usernames) - users_before
                    logger_to_use.info(f"📈 Scroll #{scroll_count + 1}: +{gained} eligible users (total: {len(usernames)}/{target_count})")
                
                scroll_success = self.scroll_likers_popup_up(logger_instance=logger_to_use)
                if not scroll_success:
                    logger_to_use.warning("⚠️ Scroll failed - popup closed or not detected")
                    break
                
                scroll_count += 1
                time.sleep(0.6)
            
            logger_to_use.info(f"🎯 Extraction completed: {len(usernames)} users in {scroll_count} scrolls")
            return usernames
            
        except Exception as e:
            logger_to_use.error(f"❌ Error extracting users from popup: {e}")
            return []
    
    def extract_visible_usernames(self, logger_instance=None) -> List[str]:
        logger_to_use = logger_instance if logger_instance else log
        usernames = []
        
        for selector in self.popup_selectors.username_in_popup_selectors:
            try:
                elements = self.device.xpath(selector)
                if elements.exists:
                    for element in elements.all():
                        username = self.extract_username_from_element(element, logger_instance=logger_to_use)
                        if username and username not in usernames:
                            usernames.append(username)
            except Exception as e:
                logger_to_use.debug(f"Error with selector {selector}: {e}")
                continue
        
        return usernames
    
    def extract_username_from_element(self, element, logger_instance=None) -> Optional[str]:

        logger_to_use = logger_instance if logger_instance else log
        
        try:
            text = None
            if hasattr(element, 'get_text'):
                text = element.get_text()
            elif hasattr(element, 'text'):
                text = element.text
            
            if not text:
                return None
            
            username = text.strip().replace('@', '')
            
            if self.is_valid_username(username):
                return username
            
            return None
            
        except Exception as e:
            logger_to_use.debug(f"Error extracting username: {e}")
            return None
    
    def is_valid_username(self, username: str) -> bool:
        if not username or len(username) < 1 or len(username) > 30:
            return False
        
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._]*$', username):
            return False
        
        ui_texts = ['j\'aime', 'likes', 'vues', 'views', 'abonné', 'suivre', 'follow']
        if username.lower() in ui_texts:
            return False
        
        return True
    
    def scroll_likers_popup_up(
        self,
        logger_instance=None,
        is_likers_popup_open_checker=None,
        verbose_logs: bool = True
    ) -> bool:

        logger_to_use = logger_instance if logger_instance else log
        
        try:
            if is_likers_popup_open_checker and not is_likers_popup_open_checker():
                if verbose_logs:
                    logger_to_use.warning("⚠️ Likers popup not detected - cannot scroll")
                return False
            
            screen_info = self.device.info
            screen_width = screen_info.get('displayWidth', 1080)
            screen_height = screen_info.get('displayHeight', 1920)
            
            if verbose_logs:
                logger_to_use.debug(f"📱 Resolution detected: {screen_width}x{screen_height}")
            
            center_x = screen_width // 2
            
            # Reduced wait time for faster extraction (was 0.8s)
            time.sleep(0.3)
            
            username_elements = self.device.xpath(self.popup_selectors.username_list_selector).all()
            
            if username_elements and len(username_elements) >= 1:
                first_username = username_elements[0]
                bounds = first_username.info.get('bounds', {})
                
                if bounds:
                    username_y = (bounds.get('top', 0) + bounds.get('bottom', 0)) // 2
                    start_y = username_y + 100
                    end_y = max(username_y - 400, int(screen_height * 0.35))
                    
                    if verbose_logs:
                        logger_to_use.debug(f"✅ First username detected at Y={username_y}, bounds={bounds}")
                        logger_to_use.debug(f"🎯 Swipe from username: start={start_y}, end={end_y}")
                    else:
                        logger_to_use.debug(f"✅ First username detected at Y={username_y}")
                        logger_to_use.debug(f"🎯 Swipe from username: start={start_y}, end={end_y}")
                else:
                    start_y = int(screen_height * 0.70)
                    end_y = int(screen_height * 0.45)
                    if verbose_logs:
                        logger_to_use.debug(f"⚠️ Bounds not available, proportional fallback")
                    else:
                        logger_to_use.debug(f"⚠️ Bounds not available, fallback")
            else:
                start_y = int(screen_height * 0.70)
                end_y = int(screen_height * 0.45)
                if verbose_logs:
                    logger_to_use.debug(f"⚠️ No username detected ({len(username_elements) if username_elements else 0}), proportional fallback")
                else:
                    logger_to_use.debug(f"⚠️ No username detected, fallback")
            
            # Faster scroll for better extraction speed (was 0.8s)
            self.device.swipe(center_x, start_y, center_x, end_y, duration=0.5)
            
            if verbose_logs:
                logger_to_use.debug(f"📜 Adaptive scroll in likers popup: ({center_x},{start_y}) → ({center_x},{end_y}) in 0.5s")
            
            # Reduced post-scroll wait (was 0.4s)
            time.sleep(0.2)
            return True
            
        except Exception as e:
            if verbose_logs:
                logger_to_use.error(f"❌ Error scrolling popup: {e}")
            return False
    
    def is_reel_post(self, logger_instance=None) -> bool:
        logger_to_use = logger_instance if logger_instance else log
        
        try:
            for indicator in self.post_selectors.reel_indicators:
                try:
                    if self.device.xpath(indicator).exists:
                        logger_to_use.debug(f"🎬 Reel detected with: {indicator}")
                        return True
                except Exception as e:
                    logger_to_use.debug(f"Error testing Reel indicator {indicator}: {e}")
                    continue
            
            logger_to_use.debug("📷 Classic post detected")
            return False
            
        except Exception as e:
            logger_to_use.debug(f"Error detecting Reel: {e}")
            return False



def parse_instagram_number(text: str) -> int:
    """Parse Instagram number - delegates to parse_number_from_text"""
    return parse_number_from_text(text)


def parse_number_from_text(text: str) -> int:
    """Parse a number from text, handling formats like '166 K', '1.2M', '1,234', etc."""
    if not text:
        return 0
    
    try:
        text_str = str(text).strip()
        
        # Normalize: remove non-breaking spaces and extra whitespace
        text_str = text_str.replace('\xa0', ' ').strip()
        
        multipliers = {
            'K': 1000, 'k': 1000,
            'M': 1000000, 'm': 1000000,
            'B': 1000000000, 'b': 1000000000
        }
        
        # Check for suffix with or without space (e.g., "166K", "166 K", "1.2 M")
        for suffix, multiplier in multipliers.items():
            # Handle "166 K" format (space before suffix)
            if text_str.endswith(f' {suffix}') or text_str.endswith(f' {suffix.lower()}'):
                try:
                    number_part = text_str[:-2].strip().replace(',', '.')
                    return int(float(number_part) * multiplier)
                except (ValueError, AttributeError):
                    continue
            # Handle "166K" format (no space)
            elif text_str.endswith(suffix):
                try:
                    number_part = text_str[:-1].strip().replace(',', '.')
                    return int(float(number_part) * multiplier)
                except (ValueError, AttributeError):
                    continue
        
        # No suffix found - extract digits only
        number_str = ''.join(c for c in text_str if c.isdigit() or c in ',. ')
        
        number_str = number_str.replace(' ', '').replace(',', '').replace('.', '')
        
        return int(number_str) if number_str else 0
        
    except (ValueError, AttributeError):
        return 0


def get_text_from_element(element) -> str:

    try:
        if hasattr(element, 'get_text'):
            text = element.get_text()
            return str(text) if text is not None else ""
        elif hasattr(element, 'text'):
            text = element.text
            return str(text) if text is not None else ""
        return str(element) if element is not None else ""
    except Exception:
        return ""
