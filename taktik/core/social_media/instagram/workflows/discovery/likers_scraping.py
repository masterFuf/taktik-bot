"""Likers scraping for the Discovery workflow."""

import time
from typing import Dict, Any, Optional
from rich.console import Console

from taktik.core.social_media.instagram.ui.detectors.scroll_end import ScrollEndDetector
from taktik.core.social_media.instagram.ui.selectors import POPUP_SELECTORS
from .models import ScrapedProfile

console = Console()


class DiscoveryLikersScrapingMixin:
    """Mixin: scrape likers from posts with optional on-the-fly enrichment."""

    def _scrape_post_likers(self, post_url: str, source_type: str, source_value: str,
                           progress, max_count: int):
        """Scrape likers from current post with optional on-the-fly enrichment."""
        enrich_mode = "with enrichment" if self.enrich_profiles else "usernames only"
        console.print(f"[dim]    ❤️ Scraping likers ({enrich_mode})...[/dim]")
        self.logger.info(f"Starting likers scraping - max: {max_count}, enrich: {self.enrich_profiles}")
        
        # Click on like count to open likers list
        if not self._open_likers_list():
            console.print(f"[yellow]    ⚠️ Could not open likers list[/yellow]")
            return
        
        time.sleep(1.5)
        
        seen_usernames = set()
        scroll_detector = ScrollEndDetector(repeats_to_end=5, device=self.device)
        no_new_users_count = 0
        max_no_new_users = 5
        
        # Resume from last position if available
        start_count = progress.likers_scraped
        enriched_count = 0
        
        while progress.likers_scraped < max_count and no_new_users_count < max_no_new_users:
            # Use detection_actions to get visible usernames with elements for clicking
            visible = self.detection_actions.get_visible_followers_with_elements()
            
            if not visible:
                # Try scrolling - wait for Instagram to load
                self.scroll_actions.scroll_down()
                time.sleep(1.5)
                
                if scroll_detector.is_the_end():
                    self.logger.info(f"Reached end of likers list after {len(seen_usernames)} users")
                    console.print(f"[dim]    📍 End of list reached ({len(seen_usernames)} total)[/dim]")
                    break
                continue
            
            new_count = 0
            for follower in visible:
                username = follower.get('username')
                element = follower.get('element')
                
                if not username or username in seen_usernames:
                    continue
                
                seen_usernames.add(username)
                
                # Check if already scraped recently (to skip enrichment, not the profile itself)
                already_scraped = self._is_profile_recently_scraped(username)
                
                # Create profile object (always record the interaction)
                profile = ScrapedProfile(
                    username=username,
                    source_type=source_type,
                    source_value=source_value,
                    interaction_type='liker',
                    post_url=post_url
                )
                
                # If already scraped, skip enrichment but still record the interaction
                if already_scraped:
                    self._skipped_already_scraped += 1
                    # Log with INFO level so it appears in Live Panel (parsable format)
                    self.logger.info(f"⏭️ SKIP @{username} | reason=already_scraped | days={self.skip_recently_scraped_days}")
                    # Still add to scraped profiles to track the interaction
                    self.scraped_profiles.append(profile)
                    progress.likers_scraped += 1
                    if progress.likers_scraped >= max_count:
                        break
                    continue
                
                # Log for Live Panel
                self.logger.info(f"👤 Liker [{progress.likers_scraped + 1}/{max_count}]: @{username}")
                
                # Enrich on-the-fly if enabled (only for new profiles)
                if self.enrich_profiles and element and enriched_count < self.max_profiles_to_enrich:
                    try:
                        console.print(f"[dim]      → Enriching @{username}...[/dim]")
                        element.click()
                        time.sleep(1.5)
                        
                        # Get enriched profile data
                        info = self.profile_manager.get_complete_profile_info(
                            username=username,
                            navigate_if_needed=False,
                            enrich=True
                        )
                        
                        if info:
                            profile.bio = info.get('biography', '')
                            profile.website = info.get('website', '')
                            profile.followers_count = info.get('followers_count', 0)
                            profile.following_count = info.get('following_count', 0)
                            profile.posts_count = info.get('posts_count', 0)
                            profile.is_private = info.get('is_private', False)
                            profile.is_verified = info.get('is_verified', False)
                            profile.is_business = info.get('is_business', False)
                            profile.category = info.get('business_category', '')
                            
                            # Extract linked accounts
                            linked = info.get('linked_accounts', [])
                            for account in linked:
                                if 'thread' in account.get('name', '').lower():
                                    profile.threads_username = account.get('name', '')
                            
                            enriched_count += 1
                            # Log detailed profile info for Live Panel parsing
                            # Replace newlines in bio with \\n to avoid breaking line-by-line parsing
                            bio_escaped = (profile.bio or '').replace('\n', '\\n')[:500]
                            self.logger.info(f"✅ PROFILE @{username} | followers={profile.followers_count} | posts={profile.posts_count} | following={profile.following_count} | category={profile.category} | website={profile.website or ''} | bio={bio_escaped} | private={profile.is_private} | verified={profile.is_verified} | business={profile.is_business}")
                            console.print(f"[dim]      ✅ {profile.followers_count} followers, {profile.posts_count} posts[/dim]")
                        
                        # Go back to likers list
                        self.device.press("back")
                        time.sleep(1)
                        
                    except Exception as e:
                        self.logger.warning(f"Failed to enrich @{username}: {e}")
                        try:
                            self.device.press("back")
                            time.sleep(0.5)
                        except:
                            pass
                
                self.scraped_profiles.append(profile)
                progress.likers_scraped += 1
                new_count += 1
                
                if progress.likers_scraped >= max_count:
                    break
            
            # Notify scroll detector
            scroll_detector.notify_new_page(list(seen_usernames))
            
            if new_count == 0:
                no_new_users_count += 1
            else:
                no_new_users_count = 0
            
            # Log progress
            self.logger.debug(f"Likers progress: {progress.likers_scraped}/{max_count} (seen: {len(seen_usernames)}, enriched: {enriched_count})")
            
            # Scroll to load more users
            if progress.likers_scraped < max_count:
                self.scroll_actions.scroll_down()
                time.sleep(1)
        
        # Go back from likers list
        self.device.press("back")
        time.sleep(1)
        
        scraped = progress.likers_scraped - start_count
        self.logger.info(f"Likers scraping complete: {scraped} scraped, {enriched_count} enriched")
        console.print(f"[dim]    ✅ {scraped} likers scraped ({enriched_count} enriched)[/dim]")

    def _open_likers_list(self) -> bool:
        """Open the likers list by clicking on like count."""
        try:
            like_count_element = self.ui_extractors.find_like_count_element(logger_instance=self.logger)
            
            if not like_count_element:
                self.logger.warning("No like counter found")
                return False
            
            like_count_element.click()
            time.sleep(1.5)
            
            # Verify likers popup opened
            if self._is_likers_popup_open():
                self.logger.debug("Likers popup opened successfully")
                return True
            
            self.logger.warning("Could not verify likers popup opened")
            return False
        except Exception as e:
            self.logger.error(f"Error opening likers list: {e}")
            return False

    def _is_likers_popup_open(self) -> bool:
        """Check if likers popup is open."""
        try:
            # Look for typical likers popup indicators
            indicators = POPUP_SELECTORS.likers_popup_indicators
            for selector in indicators:
                if self.device.xpath(selector).exists:
                    return True
        except:
            pass
        return False
