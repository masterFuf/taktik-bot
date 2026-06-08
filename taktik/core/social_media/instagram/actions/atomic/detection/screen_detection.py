"""Screen state detection, error detection, and popup handling."""

import time
from typing import Optional, Dict, Any, List
from loguru import logger

from ...core.base_action import BaseAction
from ....ui.selectors.surfaces.story_viewer import STORY_SELECTORS


class ScreenDetectionMixin(BaseAction):
    """Mixin: detect current screen state, errors, rate limits, popups."""

    _SCREEN_SIGNAL_CACHE_TTL_SECONDS = 0.25

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

    # === Screen state ===

    def is_on_home_screen(self) -> bool:
        signals = self._get_screen_signal_snapshot()
        if signals is not None:
            # The single XML dump is authoritative for the screens it covers:
            # trust the negative too instead of re-probing every indicator live.
            return signals.get("home") is True

        return self._detect_element(self.detection_selectors.home_screen_indicators, "Home screen")

    def is_on_search_screen(self) -> bool:
        signals = self._get_screen_signal_snapshot()
        if signals is not None:
            return signals.get("search") is True

        return self._detect_element(self.detection_selectors.search_screen_indicators, "Search screen")

    def is_on_profile_screen(self) -> bool:
        signals = self._get_screen_signal_snapshot()
        if signals is not None:
            # Authoritative from the single dump (covers home/profile_surface/profile);
            # no live re-probing on a negative.
            if signals.get("home") is True and signals.get("profile_surface") is not True:
                self.logger.debug("Feed surface detected from batched signals; not on profile screen")
                return False
            return signals.get("profile") is True

        if (
            self._is_element_present(self.detection_selectors.home_screen_indicators)
            and not self._is_element_present(self.detection_selectors.profile_surface_indicators)
        ):
            self.logger.debug("Feed surface detected; not on profile screen")
            return False

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

    def is_on_post_screen(self) -> bool:
        signals = self._get_screen_signal_snapshot()
        if signals is not None:
            return signals.get("post") is True

        return self._detect_element(self.detection_selectors.post_screen_indicators, "Post screen")
    
    def is_reel_post(self) -> bool:
        return self._detect_element(self.detection_selectors.reel_indicators, "Reel post")

    def is_post_grid_visible(self) -> bool:
        return self._detect_element(self.detection_selectors.post_grid_visibility_indicators, "Post grid")

    def is_loading_spinner_visible(self) -> bool:
        """
        Détecte si un spinner de chargement est visible (Instagram charge du contenu).
        """
        return self._detect_element(
            self.detection_selectors.loading_spinner_indicators,
            "Loading spinner"
        )

    # === Error and rate limit detection ===

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

    # === Aggregate state ===

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

    # === Story detection ===

    def is_story_viewer_open(self) -> bool:
        signals = self._get_screen_signal_snapshot()
        if signals is not None:
            return signals.get("story_viewer") is True

        return self._detect_element(self.detection_selectors.story_viewer_indicators, "Story viewer")

    def _get_screen_signal_snapshot(self) -> dict[str, bool] | None:
        """Batch common screen probes on one XML dump, with live fallbacks elsewhere."""
        now = time.monotonic()
        cached = getattr(self, "_screen_signal_snapshot_cache", None)
        if (
            isinstance(cached, dict)
            and now - cached.get("created_at", 0) <= self._SCREEN_SIGNAL_CACHE_TTL_SECONDS
        ):
            signals = cached.get("signals")
            return signals if isinstance(signals, dict) else None

        batch_xpath_check = getattr(self.device, "batch_xpath_check", None)
        if not callable(batch_xpath_check):
            return None

        selectors = {
            "home": self.detection_selectors.home_screen_indicators,
            "search": self.detection_selectors.search_screen_indicators,
            "profile_surface": self.detection_selectors.profile_surface_indicators,
            "profile": self.detection_selectors.profile_screen_indicators,
            "story_viewer": self.detection_selectors.story_viewer_indicators,
            "post": self.detection_selectors.post_screen_indicators,
        }

        try:
            signals = batch_xpath_check(selectors)
        except Exception as exc:
            self.logger.debug(f"Batched screen signal detection failed: {exc}")
            return None

        if not isinstance(signals, dict):
            return None

        normalized = {key: bool(signals.get(key)) for key in selectors}
        self._screen_signal_snapshot_cache = {
            "created_at": time.monotonic(),
            "signals": normalized,
        }
        return normalized
    
    def count_visible_stories(self) -> int:
        """Count the active profile-avatar story ring (0 or 1).

        Scoped to the profile-header avatar via `has_unseen_profile_story()`, so
        highlights (highlights_reel_tray_*) and the home feed tray
        (reels_tray_container) never inflate the count. That conflation previously
        made the bot believe a profile had a watchable story when it only had
        highlights, then fail to open anything ("No stories found").
        """
        try:
            count = 1 if self.has_unseen_profile_story() else 0
            self.logger.debug(f"{count} visible stories")
            return count

        except Exception as e:
            self.logger.debug(f"Error counting stories: {e}")
            return 0

    def count_visible_highlights(self) -> int:
        """Count currently visible highlight bubbles on a profile page."""
        try:
            elements = self.device.xpath(STORY_SELECTORS.highlight_buttons).all()
            count = len(elements or [])
            self.logger.debug(f"{count} visible highlights")
            return count
        except Exception as e:
            self.logger.debug(f"Error counting highlights: {e}")
            return 0

    def count_visible_feed_stories(self, skip_own_story: bool = True) -> int:
        """Count visible story bubbles in the home feed tray."""
        try:
            elements = self.device.xpath(STORY_SELECTORS.feed_story_buttons).all()
            if not elements:
                elements = self.device.xpath(STORY_SELECTORS.feed_unseen_story_buttons).all()

            count = len(elements or [])
            if skip_own_story and count > 0:
                count -= 1

            self.logger.debug(f"{count} visible feed stories")
            return max(0, count)
        except Exception as e:
            self.logger.debug(f"Error counting feed stories: {e}")
            return 0

    def get_feed_tray_total(self) -> int:
        """Total friends with stories, parsed from a tray bubble content-desc ('... of N ...')."""
        import re
        try:
            elements = self.device.xpath(STORY_SELECTORS.feed_story_buttons).all()
            if not elements:
                elements = self.device.xpath(STORY_SELECTORS.feed_unseen_story_buttons).all()
            for element in elements or []:
                try:
                    desc = element.attrib.get('content-desc', '') or ''
                except Exception:
                    desc = ''
                match = re.search(r'(?:of|sur)\s+(\d+)', desc, re.IGNORECASE)
                if match:
                    return int(match.group(1))
            return 0
        except Exception as e:
            self.logger.debug(f"Error reading feed tray total: {e}")
            return 0

    def has_unseen_profile_story(self) -> bool:
        """Detect the active profile-avatar story ring, excluding highlight bubbles."""
        try:
            element = self.device.xpath(STORY_SELECTORS.profile_unseen_story_avatar)
            return bool(element and element.exists)
        except Exception as e:
            self.logger.debug(f"Error checking profile story avatar: {e}")
            return False
    
    def get_story_count_from_viewer(self) -> tuple[int, int]:
        try:
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

    def get_story_viewer_metadata(self) -> Dict[str, Any]:
        """
        Extract metadata exposed by Instagram's story viewer.

        Current stories expose content-desc like:
        - "username's story, 17 hours ago"
        Highlights expose:
        - "Highlight title EVJF, story 2 of 2, May 14"
        - "Highlight title Travaux, story 3 of 56, February 6"

        Duration is not exposed in the UI dump; only progress-bar bounds are.
        """
        metadata: Dict[str, Any] = {
            'is_open': False,
            'is_highlight': False,
            'is_ad': False,
            'title': None,
            'timestamp': None,
            'current_story': 0,
            'total_stories': 0,
            'raw_content_desc': '',
        }

        try:
            element = self.device.xpath(STORY_SELECTORS.story_viewer_text_container).get()
            if not element:
                return metadata

            content_desc = element.attrib.get('content-desc', '') or ''
            metadata['is_open'] = True
            metadata['raw_content_desc'] = content_desc

            import re
            highlight_match = re.search(
                r'highlight\s+title\s+(.+?),\s*story\s+(\d+)\s+of\s+(\d+),\s*(.+)$',
                content_desc,
                re.IGNORECASE,
            )
            if highlight_match:
                metadata.update({
                    'is_highlight': True,
                    'title': highlight_match.group(1).strip(),
                    'current_story': int(highlight_match.group(2)),
                    'total_stories': int(highlight_match.group(3)),
                    'timestamp': highlight_match.group(4).strip(),
                })
                return metadata

            story_match = re.search(
                r"(.+?)'s\s+story,\s*(.+)$",
                content_desc,
                re.IGNORECASE,
            )
            if story_match:
                metadata.update({
                    'title': story_match.group(1).strip(),
                    'timestamp': story_match.group(2).strip(),
                })
                return metadata

            feed_story_match = re.search(
                r"story\s+de\s+(.+?),\s*(\d+)\s+sur\s+(\d+),\s*(.+)$",
                content_desc,
                re.IGNORECASE,
            )
            if feed_story_match:
                metadata.update({
                    'title': feed_story_match.group(1).strip(),
                    'current_story': int(feed_story_match.group(2)),
                    'total_stories': int(feed_story_match.group(3)),
                    'timestamp': feed_story_match.group(4).strip(),
                })

            # Fallback to dedicated nodes: the text_container content-desc is often EMPTY
            # (confirmed on device), while reel_viewer_title / _timestamp carry the data.
            if not metadata['title']:
                for el in self.device.xpath(STORY_SELECTORS.story_viewer_title).all() or []:
                    text = (el.attrib.get('text') or '').strip()
                    if text:
                        metadata['title'] = text
                        break
            if not metadata['timestamp']:
                ts_el = self.device.xpath(STORY_SELECTORS.story_viewer_timestamp).get()
                if ts_el:
                    metadata['timestamp'] = (ts_el.attrib.get('text') or '').strip() or None
            if not metadata['total_stories']:
                segments = self.device.xpath(STORY_SELECTORS.story_progress_bar).all() or []
                if segments:
                    metadata['total_stories'] = len(segments)

            # Sponsored story (ad): the title is a brand, not a friend. Flag it so callers
            # (and workflows) never treat it as a real user story.
            try:
                sponsored = self.device.xpath(STORY_SELECTORS.story_sponsored_label)
                metadata['is_ad'] = bool(sponsored and sponsored.exists)
            except Exception:
                pass

            return metadata
        except Exception as e:
            self.logger.debug(f"Error extracting story viewer metadata: {e}")
            return metadata

    def is_story_ad(self) -> bool:
        """Whether the current story is a sponsored ad (workflows must skip, not interact)."""
        try:
            sponsored = self.device.xpath(STORY_SELECTORS.story_sponsored_label)
            return bool(sponsored and sponsored.exists)
        except Exception as e:
            self.logger.debug(f"Error detecting story ad: {e}")
            return False
    
    def has_stories(self) -> bool:
        try:
            return self.count_visible_stories() > 0
        except Exception as e:
            self.logger.debug(f"Error checking stories: {e}")
            return False

    # === Post grid detection ===

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
