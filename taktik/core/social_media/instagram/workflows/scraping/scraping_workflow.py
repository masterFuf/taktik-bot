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
        
    def run(self) -> Dict[str, Any]:
        """
        Execute the scraping workflow based on configuration.
        
        Returns:
            Dict with scraping results
        """
        self.start_time = datetime.now()
        scraping_type = self.config.get('type', 'target')
        
        console.print(f"\n[bold blue]🔍 Starting {scraping_type.upper()} scraping...[/bold blue]\n")
        
        try:
            if scraping_type == 'target':
                result = self._scrape_target()
            elif scraping_type == 'hashtag':
                result = self._scrape_hashtag()
            elif scraping_type == 'post_url':
                result = self._scrape_post_url()
            else:
                self.logger.error(f"Unknown scraping type: {scraping_type}")
                return {"success": False, "error": f"Unknown scraping type: {scraping_type}"}
            
            # Export results
            if self.config.get('export_csv', True) and self.scraped_profiles:
                self._export_to_csv()
            
            # Save to database
            if self.config.get('save_to_db', True) and self.scraped_profiles:
                self._save_to_database()
            
            # Display final stats
            self._display_final_stats()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Scraping error: {e}")
            console.print(f"[red]❌ Scraping error: {e}[/red]")
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
                actual_max = min(remaining_to_scrape, available_count)
                
                console.print(f"[green]✅ @{target}: {available_count:,} {scrape_type} available[/green]")
                
                if available_count == 0:
                    console.print(f"[yellow]⚠️ No {scrape_type} to scrape from @{target}[/yellow]")
                    continue
                
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
            
            # Scrape the list with the adjusted max
            profiles_from_target = self._scrape_list(
                max_count=actual_max,
                source_type=scrape_type.upper(),
                source_name=target,
                total_available=available_count
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
                        likers = self._scrape_list(
                            max_count=min(20, max_profiles - total_scraped),
                            source_type='HASHTAG_LIKER',
                            source_name=hashtag
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
    
    def _scrape_list(self, max_count: int, source_type: str, source_name: str, total_available: int = None) -> List[Dict[str, Any]]:
        """
        Scrape usernames from a visible list (followers, following, likers).
        
        Args:
            max_count: Maximum profiles to scrape
            source_type: Type of source (FOLLOWER, FOLLOWING, LIKER, etc.)
            source_name: Name of the source (target username, hashtag, etc.)
            total_available: Total profiles available (for accurate progress display)
            
        Returns:
            List of scraped profile data
        """
        scraped = []
        scroll_detector = ScrollEndDetector(repeats_to_end=5, device=self.device)
        seen_usernames = set()
        no_new_users_count = 0
        max_no_new_users = 3  # Stop after 3 consecutive scrolls with no new users
        
        # Use actual available count for progress bar if provided
        progress_total = min(max_count, total_available) if total_available else max_count
        
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
            
            while len(scraped) < max_count and self._should_continue():
                # Check if we're in suggestions section (end of real followers)
                if self.detection_actions.is_in_suggestions_section():
                    self.logger.info("📋 Reached suggestions section - end of real followers list")
                    # Update progress to show we're done
                    progress.update(
                        task,
                        description=f"[green]Completed {source_type.lower()} ({len(scraped):,}/{len(scraped):,}) - end of list[/green]"
                    )
                    break
                
                # Get visible usernames
                visible = self.detection_actions.get_visible_followers_with_elements()
                
                if not visible:
                    # Try scrolling
                    self.scroll_actions.scroll_followers_list_down()
                    time.sleep(1)
                    
                    if scroll_detector.is_the_end():
                        self.logger.info("Reached end of list")
                        break
                    continue
                
                new_count = 0
                for follower in visible:
                    username = follower.get('username')
                    if not username or username in seen_usernames:
                        continue
                    
                    seen_usernames.add(username)
                    
                    profile_data = {
                        'username': username,
                        'source_type': source_type,
                        'source_name': source_name,
                        'scraped_at': datetime.now().isoformat()
                    }
                    
                    scraped.append(profile_data)
                    self.scraped_profiles.append(profile_data)
                    new_count += 1
                    
                    # Update progress with current count
                    progress.update(
                        task, 
                        advance=1,
                        description=f"[cyan]Scraping {source_type.lower()} ({len(scraped):,}/{progress_total:,})..."
                    )
                    
                    if len(scraped) >= max_count:
                        break
                
                # Notify scroll detector
                scroll_detector.notify_new_page(list(seen_usernames))
                
                if new_count == 0:
                    no_new_users_count += 1
                    self.logger.debug(f"No new users found ({no_new_users_count}/{max_no_new_users})")
                    
                    # Check suggestions before scrolling more
                    if self.detection_actions.is_in_suggestions_section():
                        self.logger.info("📋 Reached suggestions section - stopping")
                        break
                    
                    if no_new_users_count >= max_no_new_users:
                        self.logger.info(f"🏁 No new users after {max_no_new_users} scrolls - assuming end of list")
                        break
                    
                    # Scroll to find more
                    self.scroll_actions.scroll_followers_list_down()
                    time.sleep(0.8)
                    
                    if scroll_detector.is_the_end():
                        self.logger.info("Reached end of list")
                        break
                else:
                    # Reset counter when we find new users
                    no_new_users_count = 0
                    # Small delay before next batch
                    time.sleep(0.3)
        
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
        
        # Write CSV
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['username', 'source_type', 'source_name', 'scraped_at'])
            writer.writeheader()
            writer.writerows(self.scraped_profiles)
        
        console.print(f"\n[green]📁 Exported {len(self.scraped_profiles)} profiles to:[/green]")
        console.print(f"   [cyan]{filepath}[/cyan]")
    
    def _save_to_database(self):
        """Save scraped profiles to database."""
        if not self.scraped_profiles:
            return
        
        try:
            db_service = get_db_service()
            saved_count = 0
            
            for profile in self.scraped_profiles:
                try:
                    # Create minimal profile in database
                    profile_data = {
                        'username': profile['username'],
                        'followers_count': 0,
                        'following_count': 0,
                        'posts_count': 0,
                        'is_private': False,
                        'notes': f"Scraped from {profile['source_type']}: {profile['source_name']}"
                    }
                    
                    result = db_service.api_client.create_profile(profile_data)
                    if result:
                        saved_count += 1
                except Exception as e:
                    self.logger.debug(f"Error saving @{profile['username']}: {e}")
            
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
