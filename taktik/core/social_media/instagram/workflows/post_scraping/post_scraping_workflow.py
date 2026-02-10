"""
Instagram Post Scraping Workflow

Comprehensive workflow to scrape engagement data from Instagram posts:
1. Extract post stats (likes, comments, shares, saves)
2. Scrape likers with profile enrichment
3. Scrape comments with replies
4. Navigate to profiles for enrichment (bio, website, threads, etc.)
"""

import re
import time
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field, asdict
from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from taktik.core.social_media.instagram.actions.core.device_manager import DeviceManager
from taktik.core.social_media.instagram.actions.atomic.navigation_actions import NavigationActions
from taktik.core.social_media.instagram.actions.atomic.scroll_actions import ScrollActions
from taktik.core.social_media.instagram.actions.business.management.profile import ProfileBusiness
from taktik.core.database.local.service import get_local_database


console = Console()


@dataclass
class PostStats:
    """Statistics for a post."""
    post_url: str
    author_username: str
    likes_count: int = 0
    comments_count: int = 0
    shares_count: int = 0
    saves_count: int = 0
    caption: str = ""
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class CommentData:
    """Represents a comment with its replies."""
    username: str
    content: str
    likes_count: int = 0
    is_author_reply: bool = False
    parent_comment_id: Optional[int] = None
    replies: List['CommentData'] = field(default_factory=list)
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass 
class ScrapedProfile:
    """Profile data scraped from a liker or commenter."""
    username: str
    source_type: str  # 'liker' or 'commenter'
    source_post_url: str
    
    # Profile data
    bio: Optional[str] = None
    website: Optional[str] = None
    threads_username: Optional[str] = None
    followers_count: int = 0
    following_count: int = 0
    posts_count: int = 0
    is_private: bool = False
    is_verified: bool = False
    is_business: bool = False
    category: Optional[str] = None
    
    # Engagement context
    comment_content: Optional[str] = None
    comment_likes: int = 0
    
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())


class PostScrapingWorkflow:
    """
    Workflow to scrape engagement data from Instagram posts.
    
    Features:
    - Extract post stats (likes, comments, shares, saves)
    - Scrape likers list with profile navigation
    - Scrape comments with replies (View more replies)
    - Comment sorting (For You, Most Recent, Meta Verified)
    - Profile enrichment (bio, website, threads, stats)
    """
    
    # UI Selectors
    SELECTORS = {
        # Post page
        'post_author': 'com.instagram.android:id/row_feed_photo_profile_name',
        'like_button': 'com.instagram.android:id/row_feed_button_like',
        'comment_button': 'com.instagram.android:id/row_feed_button_comment',
        'share_button': 'com.instagram.android:id/row_feed_button_share',
        'save_button': 'com.instagram.android:id/row_feed_button_save',
        'carousel_media': 'com.instagram.android:id/carousel_video_media_group',
        
        # Comments page
        'comments_title': 'com.instagram.android:id/title_text_view',
        'comments_list': 'com.instagram.android:id/sticky_header_list',
        'comment_input': 'com.instagram.android:id/layout_comment_thread_edittext',
        'sort_menu': 'com.instagram.android:id/context_menu_options_list',
        'sort_menu_item': 'com.instagram.android:id/context_menu_item',
        
        # Navigation
        'back_button': 'com.instagram.android:id/action_bar_button_back',
    }
    
    def __init__(self, device_id: str, config: Dict[str, Any]):
        """
        Initialize the workflow.
        
        Args:
            device_id: ADB device ID
            config: Configuration dict with:
                - post_url: URL of the post to scrape
                - scrape_likers: bool (default True)
                - scrape_comments: bool (default True)
                - max_likers: int (default 50)
                - max_comments: int (default 100)
                - enrich_profiles: bool (default True)
                - max_profiles_to_enrich: int (default 30)
                - comment_sort: 'for_you' | 'most_recent' | 'meta_verified' (default 'most_recent')
        """
        self.device_id = device_id
        self.config = config
        self.logger = logger.bind(workflow="post_scraping")
        
        # Initialize device and actions
        self.device_manager = DeviceManager(device_id)
        self.device = self.device_manager.device
        self.nav_actions = NavigationActions(self.device)
        self.scroll_actions = ScrollActions(self.device)
        self.profile_manager = ProfileBusiness(self.device)
        
        # Database
        self.db = get_local_database()
        
        # Results
        self.post_stats: Optional[PostStats] = None
        self.likers: List[ScrapedProfile] = []
        self.comments: List[CommentData] = []
        self.enriched_profiles: List[ScrapedProfile] = []
        
        # Config defaults
        self.post_url = config.get('post_url', '')
        self.scrape_likers = config.get('scrape_likers', True)
        self.scrape_comments = config.get('scrape_comments', True)
        self.max_likers = config.get('max_likers', 50)
        self.max_comments = config.get('max_comments', 100)
        self.enrich_profiles = config.get('enrich_profiles', True)
        self.max_profiles_to_enrich = config.get('max_profiles_to_enrich', 30)
        self.comment_sort = config.get('comment_sort', 'most_recent')
        
    def run(self) -> Dict[str, Any]:
        """
        Execute the post scraping workflow.
        
        Returns:
            Dict with results and stats
        """
        self.logger.info(f"Starting post scraping workflow for: {self.post_url}")
        console.print(f"\n[bold cyan]🔍 Post Scraping Workflow[/bold cyan]")
        console.print(f"[dim]Post: {self.post_url}[/dim]\n")
        
        start_time = datetime.now()
        
        try:
            # Step 1: Navigate to post
            if not self._navigate_to_post():
                return {"success": False, "error": "Failed to navigate to post"}
            
            # Step 2: Extract post stats
            self._extract_post_stats()
            
            # Step 3: Scrape likers
            if self.scrape_likers:
                self._scrape_likers()
            
            # Step 4: Scrape comments
            if self.scrape_comments:
                self._scrape_comments()
            
            # Step 5: Enrich profiles
            if self.enrich_profiles:
                self._enrich_profiles()
            
            # Step 6: Save to database
            self._save_to_database()
            
            # Summary
            duration = (datetime.now() - start_time).total_seconds()
            self._print_summary(duration)
            
            return {
                "success": True,
                "post_stats": asdict(self.post_stats) if self.post_stats else None,
                "likers_count": len(self.likers),
                "comments_count": len(self.comments),
                "enriched_profiles_count": len(self.enriched_profiles),
                "duration_seconds": duration
            }
            
        except Exception as e:
            self.logger.error(f"Post scraping error: {e}")
            console.print(f"[red]❌ Error: {e}[/red]")
            return {"success": False, "error": str(e)}
    
    def _navigate_to_post(self) -> bool:
        """Navigate to the post URL."""
        console.print("[cyan]📍 Navigating to post...[/cyan]")
        
        if not self.post_url:
            self.logger.error("No post URL provided")
            return False
        
        # Use navigation actions to open post URL
        success = self.nav_actions.navigate_to_post_url(self.post_url)
        if success:
            time.sleep(2)
            console.print("[green]✅ Navigated to post[/green]")
        else:
            console.print("[red]❌ Failed to navigate to post[/red]")
        
        return success
    
    def _extract_post_stats(self):
        """Extract post statistics from the current view."""
        console.print("[cyan]📊 Extracting post stats...[/cyan]")
        
        author = ""
        likes = 0
        comments = 0
        shares = 0
        saves = 0
        caption = ""
        
        try:
            # Try to get author username
            author_elem = self.device.xpath(f'//*[@resource-id="{self.SELECTORS["post_author"]}"]')
            if author_elem.exists:
                author = author_elem.get_text() or ""
            
            # Try to get stats from carousel content-desc
            carousel = self.device.xpath(f'//*[@resource-id="{self.SELECTORS["carousel_media"]}"]')
            if carousel.exists:
                desc = carousel.info.get('contentDescription', '')
                # Parse "Photo X of Y by Author, N likes, M comments"
                match = re.search(r'(\d+)\s*likes?,\s*(\d+)\s*comments?', desc)
                if match:
                    likes = int(match.group(1))
                    comments = int(match.group(2))
            
            # Get individual counts from buttons
            buttons = self.device.xpath('//android.widget.Button').all()
            for i, btn in enumerate(buttons):
                text = btn.get_text() if hasattr(btn, 'get_text') else ''
                if text and text.isdigit():
                    count = int(text)
                    # Check previous button to determine type
                    if i > 0:
                        prev_desc = buttons[i-1].info.get('contentDescription', '')
                        if 'Like' in prev_desc and likes == 0:
                            likes = count
                        elif 'Comment' in prev_desc and comments == 0:
                            comments = count
                        elif 'Send' in prev_desc or 'Share' in prev_desc:
                            shares = count
                        elif 'Save' in prev_desc:
                            saves = count
            
            # Get caption
            caption_elem = self.device.xpath('//com.instagram.ui.widget.textview.IgTextLayoutView')
            if caption_elem.exists:
                caption = caption_elem.get_text() or ""
            
            self.post_stats = PostStats(
                post_url=self.post_url,
                author_username=author,
                likes_count=likes,
                comments_count=comments,
                shares_count=shares,
                saves_count=saves,
                caption=caption
            )
            
            console.print(f"[green]✅ Stats: {likes} likes, {comments} comments, {shares} shares, {saves} saves[/green]")
            
        except Exception as e:
            self.logger.error(f"Error extracting post stats: {e}")
            self.post_stats = PostStats(post_url=self.post_url, author_username="unknown")
    
    def _scrape_likers(self):
        """Scrape likers from the post."""
        console.print(f"\n[cyan]❤️ Scraping likers (max {self.max_likers})...[/cyan]")
        
        try:
            # Find and click like count button
            like_count_clicked = False
            buttons = self.device.xpath('//android.widget.Button').all()
            
            for i, btn in enumerate(buttons):
                if i > 0:
                    prev_info = buttons[i-1].info
                    if 'Like' in prev_info.get('contentDescription', ''):
                        text = btn.get_text() if hasattr(btn, 'get_text') else ''
                        if text and text.isdigit():
                            btn.click()
                            like_count_clicked = True
                            time.sleep(2)
                            break
            
            if not like_count_clicked:
                console.print("[yellow]⚠️ Could not find like count button[/yellow]")
                return
            
            # Scrape likers list
            seen_usernames = set()
            scroll_attempts = 0
            max_scroll_attempts = 10
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                task = progress.add_task("[cyan]Scraping likers...", total=self.max_likers)
                
                while len(self.likers) < self.max_likers and scroll_attempts < max_scroll_attempts:
                    # Find username buttons
                    found_new = False
                    
                    # Look for profile buttons/usernames in the list
                    elements = self.device.xpath('//android.widget.Button').all()
                    for elem in elements:
                        text = elem.get_text() if hasattr(elem, 'get_text') else ''
                        desc = elem.info.get('contentDescription', '')
                        
                        # Skip non-username elements
                        if not text or text in ['Follow', 'Following', 'Remove']:
                            continue
                        
                        # Check if it looks like a username
                        if text and text not in seen_usernames and not text.isdigit():
                            # Validate it's a username (no spaces, reasonable length)
                            if ' ' not in text and len(text) <= 30:
                                seen_usernames.add(text)
                                self.likers.append(ScrapedProfile(
                                    username=text,
                                    source_type='liker',
                                    source_post_url=self.post_url
                                ))
                                found_new = True
                                progress.update(task, completed=len(self.likers))
                                
                                if len(self.likers) >= self.max_likers:
                                    break
                    
                    if not found_new:
                        scroll_attempts += 1
                    else:
                        scroll_attempts = 0
                    
                    # Scroll down
                    if len(self.likers) < self.max_likers:
                        self.scroll_actions.scroll_down()
                        time.sleep(0.5)
            
            # Go back to post
            self.device.press("back")
            time.sleep(1)
            
            console.print(f"[green]✅ Scraped {len(self.likers)} likers[/green]")
            
        except Exception as e:
            self.logger.error(f"Error scraping likers: {e}")
            console.print(f"[red]❌ Error scraping likers: {e}[/red]")
    
    def _scrape_comments(self):
        """Scrape comments from the post."""
        console.print(f"\n[cyan]💬 Scraping comments (max {self.max_comments})...[/cyan]")
        
        try:
            # Click comment button or count
            comment_btn = self.device.xpath(f'//*[@resource-id="{self.SELECTORS["comment_button"]}"]')
            if comment_btn.exists:
                comment_btn.click()
                time.sleep(2)
            else:
                # Try clicking comment count
                buttons = self.device.xpath('//android.widget.Button').all()
                for i, btn in enumerate(buttons):
                    if i > 0:
                        prev_info = buttons[i-1].info
                        if 'Comment' in prev_info.get('contentDescription', ''):
                            btn.click()
                            time.sleep(2)
                            break
            
            # Verify we're on comments page
            title = self.device.xpath(f'//*[@resource-id="{self.SELECTORS["comments_title"]}"]')
            if not title.exists or title.get_text() != 'Comments':
                console.print("[yellow]⚠️ Could not open comments[/yellow]")
                return
            
            # Change sort if needed
            self._change_comment_sort()
            
            # Scrape comments
            seen_comments = set()
            scroll_attempts = 0
            max_scroll_attempts = 15
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                task = progress.add_task("[cyan]Scraping comments...", total=self.max_comments)
                
                while len(self.comments) < self.max_comments and scroll_attempts < max_scroll_attempts:
                    found_new = False
                    
                    # Find comment containers
                    view_groups = self.device.xpath('//android.view.ViewGroup').all()
                    
                    for vg in view_groups:
                        try:
                            desc = vg.info.get('contentDescription', '')
                            
                            # Skip empty or non-comment elements
                            if not desc or len(desc) < 3:
                                continue
                            
                            # Check if this looks like a comment (username + content)
                            # Format: "username content" or "username   content"
                            if desc not in seen_comments:
                                # Try to find username button inside
                                username = None
                                
                                # Look for child buttons
                                children = vg.child('android.widget.Button')
                                if children.exists:
                                    for child in children.all() if hasattr(children, 'all') else [children]:
                                        text = child.get_text() if hasattr(child, 'get_text') else ''
                                        if text and ' ' not in text and len(text) <= 30:
                                            username = text
                                            break
                                
                                if username:
                                    # Extract comment content from desc
                                    content = desc.replace(username, '').strip()
                                    
                                    # Get likes from sibling button
                                    likes = 0
                                    like_btn = vg.sibling('android.widget.Button')
                                    if like_btn.exists:
                                        like_desc = like_btn.info.get('contentDescription', '')
                                        match = re.search(r'(\d+)\s*likes?', like_desc)
                                        if match:
                                            likes = int(match.group(1))
                                    
                                    seen_comments.add(desc)
                                    self.comments.append(CommentData(
                                        username=username,
                                        content=content,
                                        likes_count=likes
                                    ))
                                    found_new = True
                                    progress.update(task, completed=len(self.comments))
                                    
                                    if len(self.comments) >= self.max_comments:
                                        break
                        except:
                            continue
                    
                    # Check for "View X more reply" buttons
                    self._expand_replies()
                    
                    if not found_new:
                        scroll_attempts += 1
                    else:
                        scroll_attempts = 0
                    
                    # Scroll down
                    if len(self.comments) < self.max_comments:
                        self.scroll_actions.scroll_down()
                        time.sleep(0.5)
            
            # Go back to post
            self.device.press("back")
            time.sleep(1)
            
            console.print(f"[green]✅ Scraped {len(self.comments)} comments[/green]")
            
        except Exception as e:
            self.logger.error(f"Error scraping comments: {e}")
            console.print(f"[red]❌ Error scraping comments: {e}[/red]")
    
    def _change_comment_sort(self):
        """Change comment sorting if needed."""
        if self.comment_sort == 'for_you':
            return  # Default, no change needed
        
        try:
            # Click on sort button (e.g., "For you")
            sort_btn = self.device.xpath('//*[@content-desc="For you"]')
            if sort_btn.exists:
                sort_btn.click()
                time.sleep(1)
                
                # Select the desired sort option
                sort_map = {
                    'most_recent': 'Most recent',
                    'meta_verified': 'Meta Verified'
                }
                
                target = sort_map.get(self.comment_sort, 'Most recent')
                option = self.device.xpath(f'//*[@content-desc="{target}"]')
                if option.exists:
                    option.click()
                    time.sleep(1)
                    console.print(f"[dim]Sorted by: {target}[/dim]")
                else:
                    # Click outside to close menu
                    self.device.press("back")
                    
        except Exception as e:
            self.logger.warning(f"Could not change comment sort: {e}")
    
    def _expand_replies(self):
        """Click on 'View X more reply' buttons to expand replies."""
        try:
            # Find "View X more reply" elements
            reply_btns = self.device.xpath('//*[contains(@content-desc, "View") and contains(@content-desc, "more repl")]')
            if reply_btns.exists:
                for btn in reply_btns.all()[:3]:  # Limit to avoid infinite loops
                    try:
                        btn.click()
                        time.sleep(0.5)
                    except:
                        pass
        except:
            pass
    
    def _enrich_profiles(self):
        """Enrich profiles with full profile data."""
        # Combine likers and commenters, prioritize commenters
        profiles_to_enrich = []
        
        # Add commenters first (they have more engagement signal)
        for comment in self.comments[:self.max_profiles_to_enrich]:
            profiles_to_enrich.append(ScrapedProfile(
                username=comment.username,
                source_type='commenter',
                source_post_url=self.post_url,
                comment_content=comment.content,
                comment_likes=comment.likes_count
            ))
        
        # Fill remaining with likers
        remaining = self.max_profiles_to_enrich - len(profiles_to_enrich)
        if remaining > 0:
            for liker in self.likers[:remaining]:
                if liker.username not in [p.username for p in profiles_to_enrich]:
                    profiles_to_enrich.append(liker)
        
        if not profiles_to_enrich:
            return
        
        console.print(f"\n[cyan]👤 Enriching {len(profiles_to_enrich)} profiles...[/cyan]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Enriching profiles...", total=len(profiles_to_enrich))
            
            for profile in profiles_to_enrich:
                try:
                    # Navigate to profile
                    if self.nav_actions.navigate_to_profile(profile.username):
                        time.sleep(1.5)
                        
                        # Get profile info
                        info = self.profile_manager.get_complete_profile_info(
                            username=profile.username,
                            navigate_if_needed=False
                        )
                        
                        if info:
                            profile.bio = info.get('biography', '')
                            profile.website = info.get('external_url', '')
                            profile.followers_count = info.get('followers_count', 0)
                            profile.following_count = info.get('following_count', 0)
                            profile.posts_count = info.get('posts_count', 0)
                            profile.is_private = info.get('is_private', False)
                            profile.is_verified = info.get('is_verified', False)
                            profile.is_business = info.get('is_business', False)
                            profile.category = info.get('category', '')
                            
                            # Check for Threads link
                            if profile.bio and 'threads' in profile.bio.lower():
                                profile.threads_username = profile.username
                            
                            self.enriched_profiles.append(profile)
                        
                        # Go back
                        self.device.press("back")
                        time.sleep(0.5)
                        
                except Exception as e:
                    self.logger.warning(f"Error enriching @{profile.username}: {e}")
                
                progress.update(task, advance=1)
        
        console.print(f"[green]✅ Enriched {len(self.enriched_profiles)} profiles[/green]")
    
    def _save_to_database(self):
        """Save scraped data to the database."""
        console.print("\n[cyan]💾 Saving to database...[/cyan]")
        
        try:
            # Save profiles
            for profile in self.enriched_profiles:
                # Check if profile exists
                existing = self.db.execute(
                    "SELECT profile_id FROM instagram_profiles WHERE username = ?",
                    (profile.username,)
                ).fetchone()
                
                if existing:
                    # Update
                    self.db.execute("""
                        UPDATE instagram_profiles SET
                            biography = ?,
                            followers_count = ?,
                            following_count = ?,
                            posts_count = ?,
                            is_private = ?,
                            updated_at = datetime('now')
                        WHERE profile_id = ?
                    """, (
                        profile.bio,
                        profile.followers_count,
                        profile.following_count,
                        profile.posts_count,
                        1 if profile.is_private else 0,
                        existing[0]
                    ))
                else:
                    # Insert
                    self.db.execute("""
                        INSERT INTO instagram_profiles (
                            username, biography, followers_count, following_count,
                            posts_count, is_private
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        profile.username,
                        profile.bio or '',
                        profile.followers_count,
                        profile.following_count,
                        profile.posts_count,
                        1 if profile.is_private else 0
                    ))
            
            self.db.commit()
            console.print(f"[green]✅ Saved {len(self.enriched_profiles)} profiles[/green]")
            
        except Exception as e:
            self.logger.error(f"Error saving to database: {e}")
            console.print(f"[red]❌ Database error: {e}[/red]")
    
    def _print_summary(self, duration: float):
        """Print a summary of the scraping results."""
        console.print("\n" + "="*50)
        console.print("[bold green]📊 Scraping Complete![/bold green]")
        console.print("="*50)
        
        table = Table(show_header=False, box=None)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        
        if self.post_stats:
            table.add_row("Post Author", f"@{self.post_stats.author_username}")
            table.add_row("Likes", str(self.post_stats.likes_count))
            table.add_row("Comments", str(self.post_stats.comments_count))
            table.add_row("Shares", str(self.post_stats.shares_count))
            table.add_row("Saves", str(self.post_stats.saves_count))
        
        table.add_row("", "")
        table.add_row("Likers Scraped", str(len(self.likers)))
        table.add_row("Comments Scraped", str(len(self.comments)))
        table.add_row("Profiles Enriched", str(len(self.enriched_profiles)))
        table.add_row("", "")
        table.add_row("Duration", f"{duration:.1f}s")
        
        console.print(table)
        console.print("="*50 + "\n")
