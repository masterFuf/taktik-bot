"""
Instagram Scraping Workflow

This module provides scraping functionality to extract profiles from:
- Target followers/following
- Hashtag posts (authors or likers)
- Post URL likers
"""

import time
import csv
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from taktik.core.social_media.instagram.actions.core.device_manager import DeviceManager
from taktik.core.social_media.instagram.actions.atomic.navigation_actions import NavigationActions
from taktik.core.social_media.instagram.actions.atomic.detection_actions import DetectionActions
from taktik.core.social_media.instagram.actions.atomic.scroll_actions import ScrollActions
from taktik.core.social_media.instagram.actions.business.management.profile import ProfileBusiness
from taktik.core.social_media.instagram.ui.detectors.scroll_end import ScrollEndDetector
from taktik.core.social_media.instagram.ui.extractors import InstagramUIExtractors
from taktik.core.database import get_db_service
from taktik.core.database.local_database import get_local_database


console = Console()


class ScrapingWorkflow:
    """
    Workflow for scraping Instagram profiles without interaction.
    
    Supports:
    - Target scraping: Extract followers/following from target accounts
    - Hashtag scraping: Extract post authors or likers from hashtag
    - URL scraping: Extract likers from a specific post
    """
    
    def __init__(self, device_manager: DeviceManager, config: Dict[str, Any]):
        """
        Initialize the scraping workflow.
        
        Args:
            device_manager: Connected device manager
            config: Scraping configuration from CLI
        """
        self.device_manager = device_manager
        self.device = device_manager.device
        self.config = config
        self.logger = logger.bind(module="scraping-workflow")
        
        # Initialize actions
        self.nav_actions = NavigationActions(self.device)
        self.detection_actions = DetectionActions(self.device)
        self.scroll_actions = ScrollActions(self.device)
        self.profile_manager = ProfileBusiness(self.device)
        self.ui_extractors = InstagramUIExtractors(self.device)
        
        # Stats
        self.scraped_profiles: List[Dict[str, Any]] = []
        self.start_time = None
        self.session_duration_minutes = config.get('session_duration_minutes', 60)
        self.scraping_session_id: Optional[int] = None
        self.csv_export_path: Optional[str] = None
        
    def run(self) -> Dict[str, Any]:
        """
        Execute the scraping workflow based on configuration.
        
        Returns:
            Dict with scraping results
        """
        self.start_time = datetime.now()
        scraping_type = self.config.get('type', 'target')
        
        console.print(f"\n[bold blue]🔍 Starting {scraping_type.upper()} scraping...[/bold blue]\n")
        
        # Create scraping session in database
        self._create_scraping_session()
        
        try:
            if scraping_type == 'target':
                result = self._scrape_target()
            elif scraping_type == 'hashtag':
                result = self._scrape_hashtag()
            elif scraping_type == 'post_url':
                result = self._scrape_post_url()
            else:
                self.logger.error(f"Unknown scraping type: {scraping_type}")
                self._complete_scraping_session(error_message=f"Unknown scraping type: {scraping_type}")
                return {"success": False, "error": f"Unknown scraping type: {scraping_type}"}
            
            # Note: If enrich_profiles is enabled, enrichment is done on-the-fly in _scrape_list
            # No separate enrichment step needed anymore
            
            # Export results
            if self.config.get('export_csv', True) and self.scraped_profiles:
                self._export_to_csv()
            
            # Save to database
            if self.config.get('save_to_db', True) and self.scraped_profiles:
                self._save_to_database()
            
            # Display final stats
            self._display_final_stats()
            
            # Complete scraping session
            self._complete_scraping_session()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Scraping error: {e}")
            console.print(f"[red]❌ Scraping error: {e}[/red]")
            self._complete_scraping_session(error_message=str(e))
            return {"success": False, "error": str(e)}
    
    def _should_continue(self) -> bool:
        """Check if scraping should continue based on time limit."""
        if not self.start_time:
            return True
        
        elapsed = (datetime.now() - self.start_time).total_seconds() / 60
        return elapsed < self.session_duration_minutes
    
    def _scrape_target(self) -> Dict[str, Any]:
        """Scrape followers or following from target accounts."""
        target_usernames = self.config.get('target_usernames', [])
        scrape_type = self.config.get('scrape_type', 'followers')
        max_profiles_requested = self.config.get('max_profiles', 500)
        
        total_scraped = 0
        targets_info = []  # Store info about each target
        
        for target in target_usernames:
            if not self._should_continue():
                self.logger.info("⏱️ Session time limit reached")
                break
            
            if total_scraped >= max_profiles_requested:
                self.logger.info(f"✅ Reached max profiles limit ({max_profiles_requested})")
                break
            
            console.print(f"\n[cyan]📍 Navigating to @{target}...[/cyan]")
            
            # Navigate to target profile
            if not self.nav_actions.navigate_to_profile(target):
                self.logger.warning(f"Failed to navigate to @{target}")
                continue
            
            time.sleep(1.5)
            
            # Get profile info to know the real count (navigate_if_needed=False since we already navigated)
            console.print(f"[dim]📊 Getting profile info...[/dim]")
            profile_info = self.profile_manager.get_complete_profile_info(username=target, navigate_if_needed=False)
            
            if profile_info:
                if scrape_type == 'followers':
                    available_count = profile_info.get('followers_count', 0)
                else:
                    available_count = profile_info.get('following_count', 0)
                
                # Adjust max to what's actually available
                remaining_to_scrape = max_profiles_requested - total_scraped
                
                # If count detection failed (0), use requested max and try anyway
                if available_count == 0:
                    console.print(f"[yellow]⚠️ Could not detect {scrape_type} count for @{target}, trying anyway...[/yellow]")
                    actual_max = remaining_to_scrape
                    available_count = remaining_to_scrape  # Use requested as fallback
                else:
                    actual_max = min(remaining_to_scrape, available_count)
                    console.print(f"[green]✅ @{target}: {available_count:,} {scrape_type} available[/green]")
                    
                    if actual_max < remaining_to_scrape:
                        console.print(f"[dim]   Adjusting target: {actual_max:,} (instead of {remaining_to_scrape:,})[/dim]")
                
                targets_info.append({
                    'username': target,
                    'available': available_count,
                    'to_scrape': actual_max
                })
            else:
                self.logger.warning(f"Could not get profile info for @{target}")
                actual_max = max_profiles_requested - total_scraped
                available_count = actual_max  # Unknown, use requested
            
            # Open followers/following list
            console.print(f"[cyan]📍 Opening {scrape_type} list...[/cyan]")
            if scrape_type == 'followers':
                if not self.nav_actions.open_followers_list():
                    self.logger.warning(f"Failed to open followers list of @{target}")
                    continue
            else:
                if not self.nav_actions.open_following_list():
                    self.logger.warning(f"Failed to open following list of @{target}")
                    continue
            
            time.sleep(1.5)
            
            # Check if followers list is limited (Meta Verified / Business accounts)
            is_limited = self.detection_actions.is_followers_list_limited()
            if is_limited:
                console.print(f"[yellow]⚠️ @{target}: Limited followers list (Meta Verified/Business account)[/yellow]")
                console.print(f"[dim]   Instagram restricts access to full followers list for this account.[/dim]")
                console.print(f"[dim]   Only a portion of followers will be scraped.[/dim]")
                self.logger.warning(f"Limited followers list detected for @{target}")
            
            # Scrape the list with the adjusted max
            enrich_profiles = self.config.get('enrich_profiles', False)
            profiles_from_target = self._scrape_list(
                max_count=actual_max,
                source_type=scrape_type.upper(),
                source_name=target,
                total_available=available_count,
                enrich_on_the_fly=enrich_profiles
            )
            
            total_scraped += len(profiles_from_target)
            console.print(f"[green]✅ Scraped {len(profiles_from_target):,}/{available_count:,} {scrape_type} from @{target}[/green]")
            
            # Go back
            self.device.press("back")
            time.sleep(1)
        
        return {
            "success": True,
            "total_scraped": total_scraped,
            "targets_processed": len(target_usernames),
            "targets_info": targets_info
        }
    
    def _scrape_hashtag(self) -> Dict[str, Any]:
        """Scrape profiles from hashtag posts."""
        hashtag = self.config.get('hashtag', '')
        scrape_type = self.config.get('scrape_type', 'authors')
        max_profiles = self.config.get('max_profiles', 200)
        max_posts = self.config.get('max_posts', 50)
        
        console.print(f"\n[cyan]📍 Navigating to #{hashtag}...[/cyan]")
        
        # Navigate to hashtag
        if not self.nav_actions.navigate_to_hashtag(hashtag):
            self.logger.error(f"Failed to navigate to #{hashtag}")
            return {"success": False, "error": f"Failed to navigate to #{hashtag}"}
        
        time.sleep(2)
        
        total_scraped = 0
        posts_checked = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task(f"[cyan]Scraping #{hashtag}...", total=max_profiles)
            
            while total_scraped < max_profiles and posts_checked < max_posts and self._should_continue():
                # Click on a post
                if not self._click_next_post():
                    self.logger.info("No more posts to check")
                    break
                
                posts_checked += 1
                time.sleep(1.5)
                
                if scrape_type == 'authors':
                    # Get post author
                    author = self._get_post_author()
                    if author and author not in [p['username'] for p in self.scraped_profiles]:
                        self.scraped_profiles.append({
                            'username': author,
                            'source_type': 'HASHTAG_AUTHOR',
                            'source_name': hashtag,
                            'scraped_at': datetime.now().isoformat()
                        })
                        total_scraped += 1
                        progress.update(task, advance=1)
                else:
                    # Scrape likers
                    if self._open_likers_list():
                        time.sleep(1)
                        enrich_profiles = self.config.get('enrich_profiles', False)
                        likers = self._scrape_list(
                            max_count=min(20, max_profiles - total_scraped),
                            source_type='HASHTAG_LIKER',
                            source_name=hashtag,
                            enrich_on_the_fly=enrich_profiles
                        )
                        total_scraped += len(likers)
                        progress.update(task, advance=len(likers))
                        self.device.press("back")
                        time.sleep(0.5)
                
                # Go back to hashtag grid
                self.device.press("back")
                time.sleep(1)
        
        return {
            "success": True,
            "total_scraped": total_scraped,
            "posts_checked": posts_checked
        }
    
    def _scrape_post_url(self) -> Dict[str, Any]:
        """Scrape likers from a specific post URL."""
        post_url = self.config.get('post_url', '')
        max_profiles = self.config.get('max_profiles', 200)
        post_id = self.config.get('post_id', 'unknown')
        
        console.print(f"\n[cyan]📍 Navigating to post...[/cyan]")
        
        # Navigate to post via deep link
        if not self.nav_actions.navigate_to_post_url(post_url):
            self.logger.error(f"Failed to navigate to post: {post_url}")
            return {"success": False, "error": "Failed to navigate to post"}
        
        time.sleep(2)
        
        # Extract post metadata (likes count)
        console.print(f"[dim]📊 Getting post info...[/dim]")
        likes_count = self.ui_extractors.extract_likes_count_from_ui()
        
        if likes_count:
            console.print(f"[green]✅ Post has {likes_count:,} likes[/green]")
            # Adjust max if needed
            if likes_count < max_profiles:
                console.print(f"[dim]   Adjusting target: {likes_count:,} (instead of {max_profiles:,})[/dim]")
                max_profiles = likes_count
        else:
            self.logger.warning("Could not extract likes count, proceeding anyway")
        
        # Detect if it's a Reel or regular post
        is_reel = self._is_reel_post()
        
        if is_reel:
            console.print("[cyan]📍 Reel detected - opening likers list...[/cyan]")
            likers = self._extract_likers_from_reel(max_profiles)
        else:
            console.print("[cyan]📍 Regular post - opening likers list...[/cyan]")
            likers = self._extract_likers_from_regular_post(max_profiles)
        
        if not likers:
            self.logger.error("Failed to extract likers")
            return {"success": False, "error": "Failed to extract likers"}
        
        # Convert to our profile format and add to scraped_profiles
        console.print(f"[cyan]📍 Processing {len(likers)} likers...[/cyan]")
        
        for username in likers[:max_profiles]:
            profile_data = {
                'username': username,
                'source_type': 'POST_LIKER',
                'source_name': post_id,
                'scraped_at': datetime.now().isoformat()
            }
            self.scraped_profiles.append(profile_data)
        
        return {
            "success": True,
            "total_scraped": len(self.scraped_profiles)
        }
    
    def _is_reel_post(self) -> bool:
        """Check if current post is a Reel."""
        reel_indicators = [
            '//*[contains(@content-desc, "Reel")]',
            '//*[@resource-id="com.instagram.android:id/clips_viewer_view_pager"]',
            '//*[contains(@resource-id, "reel")]'
        ]
        
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
            reel_like_selectors = [
                '//android.widget.TextView[contains(@text, "like") or contains(@text, "j\'aime")]',
                '//*[@resource-id="com.instagram.android:id/like_count"]',
                '//android.widget.Button[contains(@content-desc, "like")]'
            ]
            
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
    
    def _scrape_list(self, max_count: int, source_type: str, source_name: str, total_available: int = None, enrich_on_the_fly: bool = False) -> List[Dict[str, Any]]:
        """
        Scrape usernames from a visible list (followers, following, likers).
        
        Args:
            max_count: Maximum profiles to scrape
            source_type: Type of source (FOLLOWER, FOLLOWING, LIKER, etc.)
            source_name: Name of the source (target username, hashtag, etc.)
            total_available: Total profiles available (for accurate progress display)
            enrich_on_the_fly: If True, click on each profile to get detailed info (followers, following, posts, bio)
            
        Returns:
            List of scraped profile data
        """
        scraped = []
        scroll_detector = ScrollEndDetector(repeats_to_end=5, device=self.device)
        seen_usernames = set()
        no_new_users_count = 0
        max_no_new_users = 5  # Stop after 5 consecutive scrolls with no new users
        
        # Use actual available count for progress bar if provided
        progress_total = min(max_count, total_available) if total_available else max_count
        
        # Description for progress bar
        action_desc = "Scraping enrichi" if enrich_on_the_fly else "Scraping"
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            # Show realistic progress info
            task = progress.add_task(
                f"[cyan]Scraping {source_type.lower()} (0/{progress_total:,})...", 
                total=progress_total
            )
            
            suggestions_check_count = 0  # Count consecutive suggestions detections
            min_profiles_before_suggestions_check = 50  # Don't check suggestions until we have some profiles
            
            while len(scraped) < max_count and self._should_continue():
                # Only check suggestions section after collecting some profiles
                # This prevents false positives when suggestions are visible but we haven't scrolled yet
                if len(scraped) >= min_profiles_before_suggestions_check:
                    if self.detection_actions.is_in_suggestions_section():
                        suggestions_check_count += 1
                        # Require 2 consecutive detections to confirm we're really in suggestions
                        if suggestions_check_count >= 2:
                            self.logger.info("📋 Reached suggestions section - end of real followers list")
                            progress.update(
                                task,
                                description=f"[green]Completed {source_type.lower()} ({len(scraped):,}/{len(scraped):,}) - end of list[/green]"
                            )
                            break
                    else:
                        suggestions_check_count = 0  # Reset if not in suggestions
                
                # Get visible usernames
                visible = self.detection_actions.get_visible_followers_with_elements()
                
                if not visible:
                    # Try scrolling - wait for Instagram to load
                    self.scroll_actions.scroll_followers_list_down()
                    time.sleep(1.5)
                    
                    if scroll_detector.is_the_end():
                        self.logger.info("Reached end of list")
                        break
                    continue
                
                new_count = 0
                for follower in visible:
                    username = follower.get('username')
                    element = follower.get('element')
                    if not username or username in seen_usernames:
                        continue
                    
                    seen_usernames.add(username)
                    
                    profile_data = {
                        'username': username,
                        'source_type': source_type,
                        'source_name': source_name,
                        'scraped_at': datetime.now().isoformat()
                    }
                    
                    # If enriching on the fly, click on profile to get details
                    if enrich_on_the_fly and element:
                        try:
                            # Click on the profile element to navigate
                            element.click()
                            time.sleep(1.5)
                            
                            # Use get_complete_profile_info (same as automation workflows)
                            enriched_data = self.profile_manager.get_complete_profile_info(
                                username=username,
                                navigate_if_needed=False
                            )
                            
                            if enriched_data:
                                profile_data['followers_count'] = enriched_data.get('followers_count', 0)
                                profile_data['following_count'] = enriched_data.get('following_count', 0)
                                profile_data['posts_count'] = enriched_data.get('posts_count', 0)
                                profile_data['is_private'] = enriched_data.get('is_private', False)
                                profile_data['biography'] = enriched_data.get('biography', '')
                                profile_data['full_name'] = enriched_data.get('full_name', '')
                                profile_data['is_verified'] = enriched_data.get('is_verified', False)
                                profile_data['is_business'] = enriched_data.get('is_business', False)
                                
                                self.logger.debug(f"✅ Enriched @{username}: {profile_data['followers_count']} followers, {profile_data['following_count']} following")
                            else:
                                self.logger.warning(f"Could not get profile info for @{username}")
                            
                            # Go back to the list
                            self.device.press("back")
                            time.sleep(1)
                            
                        except Exception as e:
                            self.logger.warning(f"Failed to enrich @{username}: {e}")
                            # Try to go back anyway
                            try:
                                self.device.press("back")
                                time.sleep(0.5)
                            except:
                                pass
                    
                    scraped.append(profile_data)
                    self.scraped_profiles.append(profile_data)
                    new_count += 1
                    
                    # Update progress with current count
                    progress.update(
                        task, 
                        advance=1,
                        description=f"[cyan]{action_desc} {source_type.lower()} ({len(scraped):,}/{progress_total:,})..."
                    )
                    
                    if len(scraped) >= max_count:
                        break
                
                # Notify scroll detector
                scroll_detector.notify_new_page(list(seen_usernames))
                
                if new_count == 0:
                    no_new_users_count += 1
                    self.logger.debug(f"No new users found ({no_new_users_count}/{max_no_new_users})")
                    
                    # Check suggestions only after collecting enough profiles
                    if len(scraped) >= min_profiles_before_suggestions_check:
                        if self.detection_actions.is_in_suggestions_section():
                            suggestions_check_count += 1
                            if suggestions_check_count >= 2:
                                self.logger.info("📋 Reached suggestions section - stopping")
                                break
                        else:
                            suggestions_check_count = 0
                    
                    if no_new_users_count >= max_no_new_users:
                        self.logger.info(f"🏁 No new users after {max_no_new_users} scrolls - assuming end of list")
                        break
                    
                    # Get current visible usernames before scroll
                    current_usernames = set(f.get('username') for f in visible if f.get('username'))
                    
                    # Scroll to find more
                    self.scroll_actions.scroll_followers_list_down()
                    
                    # Wait for content to actually change (not just a fixed delay)
                    max_wait_attempts = 5
                    for wait_attempt in range(max_wait_attempts):
                        time.sleep(1.0)  # Wait 1s between checks
                        new_visible = self.detection_actions.get_visible_followers_with_elements()
                        new_usernames = set(f.get('username') for f in new_visible if f.get('username'))
                        
                        # Check if we have new usernames (content loaded)
                        if new_usernames != current_usernames and len(new_usernames - seen_usernames) > 0:
                            self.logger.debug(f"✅ New content loaded after {wait_attempt + 1}s")
                            break
                        
                        if wait_attempt == max_wait_attempts - 1:
                            self.logger.debug(f"⏳ Content unchanged after {max_wait_attempts}s")
                    
                    if scroll_detector.is_the_end():
                        self.logger.info("Reached end of list")
                        break
                    
                    # Check for "And X others" indicator (limited list end)
                    if self.detection_actions.is_followers_list_end_reached():
                        self.logger.info("📋 Reached 'And X others' - end of accessible followers")
                        break
                    
                    # Check for suggestions section
                    if self.detection_actions.is_suggestions_section_visible():
                        self.logger.info("📋 Reached suggestions section - end of real followers")
                        break
                else:
                    # Reset counter when we find new users
                    no_new_users_count = 0
                    # Scroll down to reveal more followers
                    self.scroll_actions.scroll_followers_list_down()
                    
                    # Wait for Instagram to finish loading (detect spinner)
                    max_loading_wait = 10  # Max 10 seconds waiting for loading
                    for _ in range(max_loading_wait):
                        time.sleep(1.0)
                        if not self.detection_actions.is_loading_spinner_visible():
                            self.logger.debug("✅ Loading complete, continuing...")
                            break
                    else:
                        self.logger.debug("⏳ Loading timeout, continuing anyway...")
        
        # Log final count vs expected
        if total_available and len(scraped) < total_available:
            self.logger.info(f"📊 Scraped {len(scraped)}/{total_available} ({len(scraped)*100//total_available}%) - some may be hidden/private")
        
        return scraped
    
    def _click_next_post(self) -> bool:
        """Click on the next post in a grid. Returns False if no more posts."""
        # Try to find and click a post thumbnail
        selectors = [
            '//*[@resource-id="com.instagram.android:id/image_button"]',
            '//android.widget.ImageView[contains(@resource-id, "image")]'
        ]
        
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
        selectors = [
            '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_name"]',
            '//android.widget.TextView[contains(@resource-id, "profile_name")]'
        ]
        
        for selector in selectors:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    return element.get_text().strip().lstrip('@')
            except Exception:
                continue
        
        return None
    
    def _enrich_scraped_profiles(self):
        """
        Visit each scraped profile to get detailed information.
        This includes: followers count, following count, posts count, bio, is_private.
        """
        if not self.scraped_profiles:
            return
        
        console.print(f"\n[bold blue]🔍 Enriching {len(self.scraped_profiles)} profiles...[/bold blue]")
        console.print("[dim]This will visit each profile to get detailed information[/dim]\n")
        
        enriched_count = 0
        failed_count = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task(
                f"[cyan]Enriching profiles (0/{len(self.scraped_profiles)})...", 
                total=len(self.scraped_profiles)
            )
            
            for i, profile in enumerate(self.scraped_profiles):
                if not self._should_continue():
                    self.logger.info("⏱️ Session time limit reached during enrichment")
                    break
                
                username = profile.get('username')
                if not username:
                    continue
                
                progress.update(
                    task,
                    description=f"[cyan]Enriching @{username} ({i+1}/{len(self.scraped_profiles)})..."
                )
                
                # Navigate to profile
                if self.nav_actions.navigate_to_profile(username, deep_link_usage_percentage=0, force_search=False):
                    time.sleep(1)
                    
                    # Extract profile info
                    try:
                        # Get counts
                        followers_count = self.detection_actions.get_followers_count() or 0
                        following_count = self.detection_actions.get_following_count() or 0
                        posts_count = self.detection_actions.get_posts_count() or 0
                        
                        # Check if private
                        is_private = self.detection_actions.is_private_account()
                        
                        # Get bio
                        bio = self._get_profile_bio() or ""
                        
                        # Get full name
                        full_name = self._get_profile_full_name() or ""
                        
                        # Update profile data
                        profile['followers_count'] = followers_count
                        profile['following_count'] = following_count
                        profile['posts_count'] = posts_count
                        profile['is_private'] = is_private
                        profile['biography'] = bio
                        profile['full_name'] = full_name
                        
                        enriched_count += 1
                        self.logger.debug(f"✅ Enriched @{username}: {followers_count} followers, {following_count} following, {posts_count} posts")
                        
                    except Exception as e:
                        self.logger.warning(f"Failed to extract info for @{username}: {e}")
                        failed_count += 1
                    
                    # Go back to prepare for next profile
                    self.device.press("back")
                    time.sleep(0.5)
                else:
                    self.logger.warning(f"Failed to navigate to @{username}")
                    failed_count += 1
                
                progress.update(task, advance=1)
                
                # Small delay between profiles to avoid rate limiting
                time.sleep(0.3)
        
        console.print(f"\n[green]✅ Enriched {enriched_count}/{len(self.scraped_profiles)} profiles[/green]")
        if failed_count > 0:
            console.print(f"[yellow]⚠️ Failed to enrich {failed_count} profiles[/yellow]")
    
    def _get_profile_bio(self) -> Optional[str]:
        """Extract biography from current profile screen."""
        bio_selectors = [
            '//*[@resource-id="com.instagram.android:id/profile_header_bio_text"]',
            '//*[@resource-id="com.instagram.android:id/biography"]',
            '//android.widget.TextView[contains(@resource-id, "bio")]'
        ]
        
        for selector in bio_selectors:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    return element.get_text().strip()
            except Exception:
                continue
        
        return None
    
    def _get_profile_full_name(self) -> Optional[str]:
        """Extract full name from current profile screen."""
        name_selectors = [
            '//*[@resource-id="com.instagram.android:id/profile_header_full_name"]',
            '//*[@resource-id="com.instagram.android:id/full_name"]'
        ]
        
        for selector in name_selectors:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    return element.get_text().strip()
            except Exception:
                continue
        
        return None
    
    def _export_to_csv(self):
        """Export scraped profiles to CSV file."""
        if not self.scraped_profiles:
            return
        
        # Create exports directory
        exports_dir = os.path.join(os.getcwd(), 'exports')
        os.makedirs(exports_dir, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        scraping_type = self.config.get('type', 'unknown')
        filename = f"scraping_{scraping_type}_{timestamp}.csv"
        filepath = os.path.join(exports_dir, filename)
        
        # Determine fieldnames based on whether profiles are enriched
        is_enriched = self.config.get('enrich_profiles', False)
        if is_enriched:
            fieldnames = ['username', 'full_name', 'followers_count', 'following_count', 'posts_count', 
                         'is_private', 'biography', 'source_type', 'source_name', 'scraped_at']
        else:
            fieldnames = ['username', 'source_type', 'source_name', 'scraped_at']
        
        # Write CSV
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(self.scraped_profiles)
        
        # Store path for session completion
        self.csv_export_path = filepath
        
        console.print(f"\n[green]📁 Exported {len(self.scraped_profiles)} profiles to:[/green]")
        console.print(f"   [cyan]{filepath}[/cyan]")
    
    def _save_to_database(self):
        """Save scraped profiles to local database."""
        if not self.scraped_profiles:
            return
        
        try:
            local_db = get_local_database()
            saved_count = 0
            updated_count = 0
            
            for profile in self.scraped_profiles:
                try:
                    username = profile['username']
                    
                    # Use enriched data if available, otherwise use defaults
                    profile_data = {
                        'username': username,
                        'followers_count': profile.get('followers_count', 0),
                        'following_count': profile.get('following_count', 0),
                        'posts_count': profile.get('posts_count', 0),
                        'is_private': profile.get('is_private', False),
                        'biography': profile.get('biography', ''),
                        'full_name': profile.get('full_name', ''),
                        'notes': f"Scraped from {profile['source_type']}: {profile['source_name']}"
                    }
                    
                    # Save or update profile in local database
                    result = local_db.save_profile(profile_data)
                    
                    if result:
                        if result.get('created'):
                            saved_count += 1
                        else:
                            updated_count += 1
                            
                except Exception as e:
                    self.logger.debug(f"Error saving @{profile.get('username', 'unknown')}: {e}")
            
            if updated_count > 0:
                console.print(f"[green]💾 Saved {saved_count} new profiles, updated {updated_count} existing profiles[/green]")
            else:
                console.print(f"[green]💾 Saved {saved_count}/{len(self.scraped_profiles)} profiles to database[/green]")
            
        except Exception as e:
            self.logger.error(f"Database save error: {e}")
            console.print(f"[yellow]⚠️ Could not save to database: {e}[/yellow]")
    
    def _display_final_stats(self):
        """Display final scraping statistics."""
        elapsed = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        elapsed_min = int(elapsed / 60)
        elapsed_sec = int(elapsed % 60)
        
        console.print("\n")
        console.print("=" * 60)
        console.print("[bold blue]🔍 SCRAPING COMPLETED[/bold blue]")
        console.print("=" * 60)
        
        table = Table(show_header=False, box=None)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="yellow")
        
        table.add_row("⏱️  Duration", f"{elapsed_min}m {elapsed_sec}s")
        table.add_row("👤 Profiles scraped", str(len(self.scraped_profiles)))
        table.add_row("📊 Rate", f"{len(self.scraped_profiles) / (elapsed / 60):.1f} profiles/min" if elapsed > 0 else "N/A")
        
        # Count by source type
        source_counts = {}
        for p in self.scraped_profiles:
            source = p.get('source_type', 'UNKNOWN')
            source_counts[source] = source_counts.get(source, 0) + 1
        
        if source_counts:
            table.add_row("", "")
            table.add_row("[bold]By source:[/bold]", "")
            for source, count in source_counts.items():
                table.add_row(f"   {source}", str(count))
        
        console.print(table)
        console.print("=" * 60)
    
    def _create_scraping_session(self) -> None:
        """Create a scraping session in the database."""
        try:
            local_db = get_local_database()
            
            # Determine source type and name
            scraping_type = self.config.get('type', 'target')
            scrape_type = self.config.get('scrape_type', 'followers')
            
            if scraping_type == 'target':
                source_type = 'TARGET'
                targets = self.config.get('target_usernames', [])
                source_name = ', '.join([f"@{t}" for t in targets[:3]])
                if len(targets) > 3:
                    source_name += f" (+{len(targets) - 3} more)"
            elif scraping_type == 'hashtag':
                source_type = 'HASHTAG'
                source_name = f"#{self.config.get('hashtag', 'unknown')}"
            elif scraping_type == 'post_url':
                source_type = 'POST_URL'
                source_name = self.config.get('post_url', 'unknown')[:100]
            else:
                source_type = 'UNKNOWN'
                source_name = 'unknown'
            
            self.scraping_session_id = local_db.create_scraping_session(
                scraping_type=scrape_type,
                source_type=source_type,
                source_name=source_name,
                max_profiles=self.config.get('max_profiles', 500),
                export_csv=self.config.get('export_csv', True),
                save_to_db=self.config.get('save_to_db', True),
                config=self.config
            )
            
            if self.scraping_session_id:
                self.logger.info(f"Created scraping session: {self.scraping_session_id}")
            
        except Exception as e:
            self.logger.warning(f"Could not create scraping session: {e}")
    
    def _complete_scraping_session(self, error_message: Optional[str] = None) -> None:
        """Complete the scraping session in the database."""
        if not self.scraping_session_id:
            return
        
        try:
            local_db = get_local_database()
            local_db.complete_scraping_session(
                scraping_id=self.scraping_session_id,
                total_scraped=len(self.scraped_profiles),
                csv_path=self.csv_export_path,
                error_message=error_message
            )
            
            status = 'ERROR' if error_message else 'COMPLETED'
            self.logger.info(f"Scraping session {self.scraping_session_id} {status}: {len(self.scraped_profiles)} profiles")
            
        except Exception as e:
            self.logger.warning(f"Could not complete scraping session: {e}")
