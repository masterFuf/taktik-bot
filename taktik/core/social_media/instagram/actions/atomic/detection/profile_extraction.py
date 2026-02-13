"""Profile detection, extraction, and enrichment (XML-based)."""

from typing import Optional, Dict, Any, List
from loguru import logger

from ...core.base_action import BaseAction
from ....ui.selectors import DETECTION_SELECTORS, PROFILE_SELECTORS, POST_SELECTORS


class ProfileExtractionMixin(BaseAction):
    """Mixin: profile flags, text extraction, enriched data (XML batch), bio more button."""

    # === Profile flags ===

    def is_private_account(self) -> bool:
        return self._detect_element(self.detection_selectors.private_account_indicators, "Private account", log_found=True)
    
    def is_verified_account(self) -> bool:
        return self._detect_element(self.detection_selectors.verified_account_indicators, "Verified account")
    
    def is_business_account(self) -> bool:
        return self._detect_element(self.detection_selectors.business_account_indicators, "Business account")

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

    # === Simple text extraction ===

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

    # === Batch text extraction (XML) ===

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

    # === Enriched profile extraction (XML) ===

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
            username_selectors = PROFILE_SELECTORS.enrichment_username_selectors
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
            full_name_selectors = PROFILE_SELECTORS.enrichment_full_name_selectors
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
            category_selectors = PROFILE_SELECTORS.enrichment_category_selectors
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
            bio_selectors = PROFILE_SELECTORS.enrichment_bio_selectors
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
            website_selectors = PROFILE_SELECTORS.enrichment_website_selectors
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
            banner_selectors = PROFILE_SELECTORS.enrichment_banner_selectors
            for selector in banner_selectors:
                try:
                    elements = tree.xpath(selector)
                    for elem in elements:
                        # Get the title (account name)
                        title_elem = elem.xpath(PROFILE_SELECTORS.enrichment_banner_title_selector)
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
            more_selectors = PROFILE_SELECTORS.enrichment_bio_more_selectors
            
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
