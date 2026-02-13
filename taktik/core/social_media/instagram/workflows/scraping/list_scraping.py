"""List scraping, hashtag scraping, and post URL scraping for the Scraping workflow."""

import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from taktik.core.social_media.instagram.ui.detectors.scroll_end import ScrollEndDetector
from ..common.post_navigation import open_likers_list

console = Console()


class ScrapingListMixin:
    """Mixin: generic list scraping, hashtag scraping, post URL scraping."""

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
                            
                            # Use get_complete_profile_info with enrich=True for full data
                            enriched_data = self.profile_manager.get_complete_profile_info(
                                username=username,
                                navigate_if_needed=False,
                                enrich=True
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
                                profile_data['business_category'] = enriched_data.get('business_category', '')
                                profile_data['website'] = enriched_data.get('website', '')
                                profile_data['linked_accounts'] = enriched_data.get('linked_accounts', [])
                                profile_data['date_joined'] = enriched_data.get('date_joined', '')
                                profile_data['account_based_in'] = enriched_data.get('account_based_in', '')
                                
                                self.logger.debug(f"✅ Enriched @{username}: {profile_data['followers_count']} followers, category={profile_data.get('business_category')}")
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
                    self._save_profile_immediately(profile_data)
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
                        profile_data = {
                            'username': author,
                            'source_type': 'HASHTAG_AUTHOR',
                            'source_name': hashtag,
                            'scraped_at': datetime.now().isoformat()
                        }
                        self.scraped_profiles.append(profile_data)
                        self._save_profile_immediately(profile_data)
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
            self._save_profile_immediately(profile_data)
        
        return {
            "success": True,
            "total_scraped": len(self.scraped_profiles)
        }

    def _open_likers_list(self) -> bool:
        """Open the likers list by clicking on like count (for hashtag scraping)."""
        return open_likers_list(self.device, self.ui_extractors, self.logger)
