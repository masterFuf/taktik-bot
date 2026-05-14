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

    def extract_profile_image(self, xml_content: Optional[str] = None) -> Optional[str]:
        """
        Extract profile picture via screenshot + crop.
        Uses XML dump to find the avatar ImageView bounds, then crops from a screenshot.
        
        Args:
            xml_content: Pre-fetched XML dump (optional, will fetch if None)
        
        Returns:
            Base64 data URL string (data:image/jpeg;base64,...) or None if failed
        """
        import base64
        import io
        from lxml import etree
        
        try:
            if not xml_content:
                xml_content = self.device.get_xml_dump()
            if not xml_content:
                return None
            
            tree = etree.fromstring(xml_content.encode('utf-8'))
            
            # Find profile picture ImageView bounds
            bounds = None
            for selector in PROFILE_SELECTORS.profile_picture_imageview:
                try:
                    elements = tree.xpath(selector)
                    if elements:
                        bounds_str = elements[0].get('bounds', '')
                        if bounds_str:
                            parts = bounds_str.replace('][', ',').replace('[', '').replace(']', '').split(',')
                            if len(parts) == 4:
                                bounds = {
                                    'left': int(parts[0]),
                                    'top': int(parts[1]),
                                    'right': int(parts[2]),
                                    'bottom': int(parts[3])
                                }
                                break
                except Exception:
                    continue
            
            if not bounds:
                self.logger.debug("Profile picture ImageView not found in XML")
                return None
            
            # Take screenshot and crop
            screenshot = self.device.screenshot_pil()
            if screenshot is None:
                return None
            
            padding = 2
            crop_box = (
                max(0, bounds['left'] - padding),
                max(0, bounds['top'] - padding),
                min(screenshot.size[0], bounds['right'] + padding),
                min(screenshot.size[1], bounds['bottom'] + padding)
            )
            cropped = screenshot.crop(crop_box)
            
            # Convert to JPEG base64
            buffer = io.BytesIO()
            cropped.convert('RGB').save(buffer, format='JPEG', quality=85)
            b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            self.logger.debug(f"📸 Profile image extracted ({cropped.size[0]}x{cropped.size[1]}, {len(b64) // 1024}KB)")
            return f"data:image/jpeg;base64,{b64}"
            
        except Exception as e:
            self.logger.debug(f"Failed to extract profile image: {e}")
            return None

    def click_bio_more_button(self) -> bool:
        """
        Click on '… more' in bio to expand truncated biography.

        Instagram renders the full bio + '… more' in a single non-clickable
        TextView.  The '… more' is ALWAYS on the last line, so we:
          1. Read the element text to count the actual number of lines.
          2. Derive the line height dynamically: height / num_lines.
          3. Click the center of the last line (Y) at the left quarter (X),
             where '… more' starts regardless of screen resolution or bio length.

        Returns:
            True if button was found and clicked, False otherwise
        """
        try:
            more_selectors = PROFILE_SELECTORS.enrichment_bio_more_selectors

            for selector in more_selectors:
                element = self.device.xpath(selector)
                if not element.exists:
                    continue

                info = element.info
                bounds = info.get('bounds', {})
                text = info.get('text', '')

                if not bounds:
                    # No bounds info — fall back to element center click
                    element.click()
                    self.logger.debug("Clicked 'more' (no bounds, center fallback)")
                    return True

                left   = bounds.get('left', 0)
                right  = bounds.get('right', 0)
                top    = bounds.get('top', 0)
                bottom = bounds.get('bottom', 0)

                # Count lines from actual text (strip to ignore leading/trailing \n)
                num_lines = max(len(text.strip().split('\n')), 1)
                height = bottom - top
                line_height = height / num_lines

                # '… more' is the last line → click its vertical center
                click_y = int(bottom - line_height / 2)
                # '… more' starts near the left edge of the last line
                click_x = left + int((right - left) * 0.25)

                self.logger.debug(
                    f"Clicking '… more': ({click_x}, {click_y}), "
                    f"bounds=[{left},{top}][{right},{bottom}], "
                    f"lines={num_lines}, line_height={line_height:.0f}px"
                )
                self.device.click_coordinates(click_x, click_y)
                self._human_like_delay('click')
                return True

            return False

        except Exception as e:
            self.logger.error(f"Error clicking bio more button: {e}")
            return False
