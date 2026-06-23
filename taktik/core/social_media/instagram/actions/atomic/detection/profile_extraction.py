"""Profile detection, extraction, and enrichment (XML-based)."""

import re
from typing import Optional, Dict, Any, List
from loguru import logger

from ...core.base_action import BaseAction
from ....ui.selectors.surfaces.profile import PROFILE_SELECTORS
from taktik.core.shared.vision import locate_text_on_screen

_BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


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
                            # Truncation is flagged by the trailing ellipsis (language-neutral:
                            # "… more" EN, "… plus"/"… suite" FR). A false positive is harmless —
                            # click_bio_more_button no-ops when OCR finds no expander word.
                            if '…' in text or '...' in text:
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
        """Extract a profile picture (screenshot + crop of the header avatar).

        Use for VISITED profiles. For our own connected account prefer
        `extract_own_avatar_from_tab()` — the header avatar is polluted by the story
        ring and the "Ajouter à la story" (+) badge.

        Args:
            xml_content: Pre-fetched XML dump (optional, will fetch if None)

        Returns:
            Base64 data URL string (data:image/jpeg;base64,...) or None if failed
        """
        return self._extract_avatar_base64(
            PROFILE_SELECTORS.profile_picture_imageview, xml_content=xml_content
        )

    def extract_own_avatar_from_tab(self, xml_content: Optional[str] = None) -> Optional[str]:
        """Extract OUR connected account's avatar from the bottom-bar profile tab.

        The bottom-bar avatar is overlay-free (no story ring, no "+" add-to-story
        badge) so it gives a clean picture of the logged-in user. It is small
        (~83 px), so it is upscaled x2 (~166 px) for a sharper thumbnail.

        Args:
            xml_content: Pre-fetched XML dump (optional, will fetch if None)

        Returns:
            Base64 data URL string (data:image/jpeg;base64,...) or None if failed
        """
        return self._extract_avatar_base64(
            PROFILE_SELECTORS.tab_profile_avatar, scale=2, xml_content=xml_content
        )

    def _extract_avatar_base64(
        self,
        selectors: list,
        *,
        scale: int = 1,
        xml_content: Optional[str] = None,
    ) -> Optional[str]:
        """Find the first matching avatar ImageView, crop it from a screenshot and
        return it as a JPEG base64 data URL. `scale` upsamples the crop (Lanczos)."""
        import base64
        import io
        from lxml import etree
        from PIL import Image

        try:
            if not xml_content:
                xml_content = self.device.get_xml_dump()
            if not xml_content:
                return None

            tree = etree.fromstring(xml_content.encode('utf-8'))

            # Find the avatar ImageView bounds
            bounds = None
            for selector in selectors:
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
                self.logger.debug("Avatar ImageView not found in XML")
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
            cropped = screenshot.crop(crop_box).convert('RGB')

            if scale and scale > 1:
                cropped = cropped.resize(
                    (cropped.size[0] * scale, cropped.size[1] * scale),
                    resample=Image.LANCZOS,
                )

            # Convert to JPEG base64
            buffer = io.BytesIO()
            cropped.save(buffer, format='JPEG', quality=85)
            b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

            self.logger.debug(f"📸 Avatar extracted ({cropped.size[0]}x{cropped.size[1]}, {len(b64) // 1024}KB)")
            return f"data:image/jpeg;base64,{b64}"

        except Exception as e:
            self.logger.debug(f"Failed to extract avatar: {e}")
            return None

    def _truncated_bio_region(self) -> Optional[tuple]:
        """Bounds (x1,y1,x2,y2) of the truncated bio TextView, or None.

        Language-neutral: finds the bio TextView (resource-id based) whose text carries
        the truncation ellipsis "…"/"...". Used as the OCR region to locate the expander.
        """
        from lxml import etree
        xml = self.device.get_xml_dump()
        if not xml:
            return None
        try:
            tree = etree.fromstring(xml.encode("utf-8"))
        except Exception:
            return None
        for selector in PROFILE_SELECTORS.enrichment_bio_selectors:
            try:
                elements = tree.xpath(selector)
            except Exception:
                continue
            for element in elements:
                text = element.get("text", "") or ""
                if "…" in text or "..." in text:  # truncated bio
                    match = _BOUNDS_RE.search(element.get("bounds", "") or "")
                    if match:
                        return tuple(int(g) for g in match.groups())
        return None

    def click_bio_more_button(self) -> bool:
        """Expand a truncated biography by OCR-locating its '… more' / '… plus' expander
        and tapping its REAL position.

        The expander is a ClickableSpan inside a single non-clickable TextView — it has no
        accessibility node, so its position can't be read from the dump (the previous
        coordinate estimate missed, and the old text="more" selector failed on FR "plus").
        Instead we OCR the bio TextView's region (its real bounds, language-neutral) and
        tap the located word. No-op (returns False) if the bio isn't truncated or OCR is
        unavailable — the bio simply stays as-is.
        """
        try:
            region = self._truncated_bio_region()
            if region is None:
                return False
            matches = locate_text_on_screen(self.device, PROFILE_SELECTORS.bio_more_words, region=region)
            if not matches:
                self.logger.debug("Bio 'more': no OCR match (truncated bio not expanded)")
                return False
            # The expander is on the LAST line of the bio -> the lowest match.
            point = max(matches, key=lambda m: m.top).center
            self.logger.debug(f"Bio 'more' expander located by OCR @ {point} (region={region})")
            self.device.click_coordinates(point[0], point[1])
            self._human_like_delay('click')
            return True
        except Exception as e:
            self.logger.error(f"Error expanding bio: {e}")
            return False
