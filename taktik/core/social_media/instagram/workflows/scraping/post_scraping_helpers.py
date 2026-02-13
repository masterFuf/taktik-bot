"""Post-level scraping helpers: open posts, detect reels, extract likers/commenters."""

import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from taktik.core.social_media.instagram.ui.selectors import DETECTION_SELECTORS, POST_SELECTORS, BUTTON_SELECTORS
from taktik.core.social_media.instagram.ui.detectors.scroll_end import ScrollEndDetector

console = Console()


class ScrapingPostHelpersMixin:
    """Mixin: post opening, reel detection, likers/commenters extraction."""

    def _scrape_post_likers_commenters(
        self, 
        target_username: str, 
        max_count: int,
        scrape_likers: bool = True,
        scrape_commenters: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Scrape likers and/or commenters from the first post of a target profile.
        
        Args:
            target_username: Username of the target profile (already navigated to)
            max_count: Maximum number of profiles to scrape
            scrape_likers: Whether to scrape likers
            scrape_commenters: Whether to scrape commenters
            
        Returns:
            List of scraped profiles
        """
        scraped_profiles = []
        enrich_profiles = self.config.get('enrich_profiles', False)
        
        try:
            # Open first post using the same logic as like.py
            if not self._open_first_post_of_profile():
                self.logger.warning(f"Could not open first post for @{target_username}")
                return scraped_profiles
            
            # Scrape likers if enabled
            if scrape_likers and len(scraped_profiles) < max_count:
                console.print(f"[cyan]❤️ Scraping likers...[/cyan]")
                likers = self._scrape_post_likers(
                    max_count=max_count - len(scraped_profiles),
                    source_name=target_username,
                    enrich_on_the_fly=enrich_profiles
                )
                scraped_profiles.extend(likers)
                self.logger.info(f"Scraped {len(likers)} likers from @{target_username}'s post")
            
            # Scrape commenters if enabled
            if scrape_commenters and len(scraped_profiles) < max_count:
                console.print(f"[cyan]💬 Scraping commenters...[/cyan]")
                commenters = self._scrape_post_commenters(
                    max_count=max_count - len(scraped_profiles),
                    source_name=target_username,
                    enrich_on_the_fly=enrich_profiles
                )
                # Filter out duplicates
                existing_usernames = {p['username'] for p in scraped_profiles}
                new_commenters = [c for c in commenters if c['username'] not in existing_usernames]
                scraped_profiles.extend(new_commenters)
                self.logger.info(f"Scraped {len(new_commenters)} unique commenters from @{target_username}'s post")
            
            # Go back to profile
            self.device.press("back")
            time.sleep(1)
            
        except Exception as e:
            self.logger.error(f"Error scraping post likers/commenters: {e}")
            self.device.press("back")
        
        return scraped_profiles

    def _open_first_post_of_profile(self) -> bool:
        """Open the first post of the current profile (same logic as like.py)."""
        try:
            self.logger.info("Opening first post of profile...")
            console.print(f"[dim]📸 Looking for first post...[/dim]")
            
            # Use the same selector as like.py
            posts = self.device.xpath(DETECTION_SELECTORS.post_thumbnail_selectors[0]).all()
            
            if not posts:
                # Try alternative selector
                posts = self.device.xpath(POST_SELECTORS.first_post_grid).all()
            
            if not posts:
                self.logger.error("No posts found in grid")
                return False
            
            first_post = posts[0]
            first_post.click()
            self.logger.debug("Clicking on first post...")
            
            time.sleep(3)  # Wait for post to load
            
            if self._is_in_post_view():
                self.logger.info("First post opened successfully")
                return True
            else:
                self.logger.error("Failed to open first post")
                return False
                
        except Exception as e:
            self.logger.error(f"Error opening first post: {e}")
            return False

    def _is_in_post_view(self) -> bool:
        """Check if we're in a post view (same logic as like.py)."""
        try:
            # Use both post_view_indicators and post_detail_indicators for better detection
            post_indicators = POST_SELECTORS.post_view_indicators + POST_SELECTORS.post_detail_indicators
            
            for indicator in post_indicators:
                if self.device.xpath(indicator).exists:
                    self.logger.debug(f"Post view detected via: {indicator[:50]}...")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking post view: {e}")
            return False

    def _scrape_post_likers(
        self, 
        max_count: int, 
        source_name: str,
        enrich_on_the_fly: bool = False
    ) -> List[Dict[str, Any]]:
        """Scrape likers from the current post."""
        scraped = []
        
        try:
            # Try to open likers list
            # IMPORTANT: Click on "Liked by" at the START of the phrase, NOT on the username
            # The full text is "Liked by username and others" - clicking username goes to profile
            likers_opened = False
            
            # First priority: Click on "Liked by" / "Aimé par" text at the beginning
            liked_by_selectors = POST_SELECTORS.liked_by_selectors
            
            for selector in liked_by_selectors:
                element = self.device.xpath(selector)
                if element.exists:
                    self.logger.debug(f"Found 'Liked by' element: {selector}")
                    # Click on the left side of the element (where "Liked by" is)
                    bounds = element.info.get('bounds', {})
                    if bounds:
                        # Click on the left 20% of the element to hit "Liked by"
                        left = bounds.get('left', 0)
                        top = bounds.get('top', 0)
                        bottom = bounds.get('bottom', 0)
                        click_x = left + 40  # 40 pixels from left edge
                        click_y = (top + bottom) // 2
                        self.device.click(click_x, click_y)
                        self.logger.debug(f"Clicked at ({click_x}, {click_y}) - left side of 'Liked by'")
                    else:
                        element.click()
                    time.sleep(2)
                    likers_opened = True
                    break
            
            if not likers_opened:
                # Second priority: Try clicking on the like count directly (e.g., "1,234 likes")
                like_count_selectors = POST_SELECTORS.like_count_selectors
                for selector in like_count_selectors:
                    element = self.device.xpath(selector)
                    if element.exists:
                        self.logger.debug(f"Found like count element: {selector}")
                        element.click()
                        time.sleep(2)
                        likers_opened = True
                        break
            
            if not likers_opened:
                self.logger.warning("Could not open likers list")
                return scraped
            
            # Now scrape the likers list
            scraped = self._scrape_list(
                max_count=max_count,
                source_type='POST_LIKERS',
                source_name=source_name,
                total_available=max_count,
                enrich_on_the_fly=enrich_on_the_fly
            )
            
            # Go back from likers list
            self.device.press("back")
            time.sleep(1)
            
        except Exception as e:
            self.logger.error(f"Error scraping post likers: {e}")
        
        return scraped

    def _scrape_post_commenters(
        self, 
        max_count: int, 
        source_name: str,
        enrich_on_the_fly: bool = False
    ) -> List[Dict[str, Any]]:
        """Scrape commenters from the current post."""
        scraped = []
        
        try:
            # Click on comment button to open comments
            comment_button_selectors = BUTTON_SELECTORS.comment_button
            
            comments_opened = False
            for selector in comment_button_selectors:
                element = self.device.xpath(selector)
                if element.exists:
                    element.click()
                    time.sleep(2)
                    comments_opened = True
                    break
            
            if not comments_opened:
                self.logger.warning("Could not open comments")
                return scraped
            
            # Extract commenters from the comments section
            seen_usernames = set()
            scroll_attempts = 0
            max_scroll_attempts = 20
            
            while len(scraped) < max_count and scroll_attempts < max_scroll_attempts:
                # Find comment author usernames
                username_selectors = POST_SELECTORS.comment_username_selectors
                
                found_new = False
                for selector in username_selectors:
                    elements = self.device.xpath(selector).all()
                    for elem in elements:
                        try:
                            username = elem.attrib.get('content-desc', '') or elem.text or ''
                            # Clean username
                            username = username.strip().lstrip('@')
                            if username and username not in seen_usernames and username != source_name:
                                seen_usernames.add(username)
                                profile_data = {
                                    'username': username,
                                    'source': f'POST_COMMENTERS:{source_name}',
                                    'scraped_at': datetime.now().isoformat()
                                }
                                scraped.append(profile_data)
                                self.scraped_profiles.append(profile_data)
                                self._save_profile_immediately(profile_data)
                                found_new = True
                                
                                if len(scraped) >= max_count:
                                    break
                        except:
                            continue
                    if len(scraped) >= max_count:
                        break
                
                if not found_new:
                    scroll_attempts += 1
                else:
                    scroll_attempts = 0
                
                # Scroll to load more comments
                self.scroll_actions.scroll_down()
                time.sleep(1)
            
            # Go back from comments
            self.device.press("back")
            time.sleep(1)
            
        except Exception as e:
            self.logger.error(f"Error scraping post commenters: {e}")
        
        return scraped

    def _is_reel_post(self) -> bool:
        """Check if current post is a Reel."""
        reel_indicators = POST_SELECTORS.reel_indicators
        
        for selector in reel_indicators:
            try:
                if self.device.xpath(selector).exists:
                    return True
            except Exception:
                continue
        
        return False

    def _extract_likers_from_regular_post(self, max_count: int) -> List[str]:
        """Extract likers from a regular post by clicking on likes count."""
        try:
            # Find and click on like count
            like_count_element = self.ui_extractors.find_like_count_element(logger_instance=self.logger)
            if not like_count_element:
                self.logger.warning("⚠️ Like count element not found")
                return []
            
            self.logger.debug("👆 Clicking on like count")
            like_count_element.click()
            time.sleep(2)
            
            # Extract usernames from likers popup
            likers = self._extract_usernames_from_likers_list(max_count)
            
            # Close popup
            self.device.press("back")
            
            return likers
            
        except Exception as e:
            self.logger.error(f"❌ Error extracting likers from regular post: {e}")
            return []

    def _extract_likers_from_reel(self, max_count: int) -> List[str]:
        """Extract likers from a Reel by clicking on likes count."""
        try:
            # Reel-specific selectors for like count
            reel_like_selectors = POST_SELECTORS.reel_like_selectors
            
            like_element = None
            for selector in reel_like_selectors:
                try:
                    elements = self.device.xpath(selector).all()
                    for element in elements:
                        text = element.get_text() if hasattr(element, 'get_text') else ""
                        if text and self.ui_extractors.is_like_count_text(text):
                            like_element = element
                            self.logger.info(f"✅ Reel like count found: '{text}'")
                            break
                    if like_element:
                        break
                except Exception:
                    continue
            
            if not like_element:
                self.logger.warning("⚠️ Reel like count not found")
                return []
            
            like_element.click()
            time.sleep(2)
            
            # Extract usernames from likers popup
            likers = self._extract_usernames_from_likers_list(max_count)
            
            # Close popup
            self.device.press("back")
            
            return likers
            
        except Exception as e:
            self.logger.error(f"❌ Error extracting likers from reel: {e}")
            return []

    def _extract_usernames_from_likers_list(self, max_count: int) -> List[str]:
        """Extract usernames from the likers popup/list."""
        likers = []
        seen_usernames = set()
        scroll_detector = ScrollEndDetector(repeats_to_end=3, device=self.device)
        no_new_count = 0
        
        # Wait for popup to load and show usernames
        self.logger.debug("⏳ Waiting for likers popup to load...")
        popup_loaded = False
        for attempt in range(5):
            time.sleep(1)
            visible = self.detection_actions.get_visible_followers_with_elements()
            if visible:
                self.logger.info(f"✅ Likers popup loaded with {len(visible)} visible users")
                popup_loaded = True
                break
            self.logger.debug(f"Waiting for popup... attempt {attempt + 1}/5")
        
        if not popup_loaded:
            self.logger.warning("⚠️ Likers popup did not load properly")
            return []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task(f"[cyan]Extracting likers (0/{max_count:,})...", total=max_count)
            
            while len(likers) < max_count and self._should_continue():
                # Get visible usernames
                visible = self.detection_actions.get_visible_followers_with_elements()
                
                if not visible:
                    no_new_count += 1
                    if no_new_count >= 3:
                        self.logger.info("No more likers found")
                        break
                    # Wait a bit before scrolling
                    time.sleep(0.5)
                    self.scroll_actions.scroll_followers_list_down()
                    time.sleep(1)
                    continue
                
                new_count = 0
                for follower in visible:
                    username = follower.get('username')
                    if not username or username in seen_usernames:
                        continue
                    
                    seen_usernames.add(username)
                    likers.append(username)
                    new_count += 1
                    
                    progress.update(
                        task,
                        advance=1,
                        description=f"[cyan]Extracting likers ({len(likers):,}/{max_count:,})..."
                    )
                    
                    if len(likers) >= max_count:
                        break
                
                scroll_detector.notify_new_page(list(seen_usernames))
                
                if new_count == 0:
                    no_new_count += 1
                    if no_new_count >= 3:
                        self.logger.info("No more new likers after scrolling")
                        break
                    time.sleep(0.5)
                    self.scroll_actions.scroll_followers_list_down()
                    time.sleep(1)
                else:
                    no_new_count = 0
                    time.sleep(0.3)
        
        return likers

    def _click_next_post(self) -> bool:
        """Click on the next post in a grid. Returns False if no more posts."""
        # Try to find and click a post thumbnail
        selectors = POST_SELECTORS.hashtag_post_selectors
        
        for selector in selectors:
            try:
                elements = self.device.xpath(selector).all()
                if elements:
                    elements[0].click()
                    return True
            except Exception:
                continue
        
        return False

    def _get_post_author(self) -> Optional[str]:
        """Get the username of the current post author."""
        selectors = POST_SELECTORS.post_author_username_selectors
        
        for selector in selectors:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    return element.get_text().strip().lstrip('@')
            except Exception:
                continue
        
        return None
