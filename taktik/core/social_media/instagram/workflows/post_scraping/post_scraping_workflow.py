"""
Instagram Post Scraping Workflow

Comprehensive workflow to scrape engagement data from Instagram posts:
1. Extract post stats (likes, comments, shares, saves)
2. Scrape likers with profile enrichment
3. Scrape comments with replies
4. Navigate to profiles for enrichment (bio, website, threads, etc.)

Internal structure (SRP split):
- post_scraping_models.py  — Dataclasses (PostStats, CommentData, ScrapedProfile)
- engagement_scraping.py   — Likers/comments scraping, comment sort, expand replies
- post_persistence.py      — Profile enrichment, DB save, summary
- post_scraping_workflow.py — Orchestrator (this file)
"""

import re
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import asdict
from loguru import logger
from rich.console import Console

from taktik.core.social_media.instagram.actions.core.device_manager import DeviceManager
from taktik.core.social_media.instagram.actions.atomic.navigation_actions import NavigationActions
from taktik.core.social_media.instagram.actions.atomic.scroll_actions import ScrollActions
from taktik.core.social_media.instagram.actions.business.management.profile import ProfileBusiness
from taktik.core.database.local.service import get_local_database
from taktik.core.social_media.instagram.ui.selectors import POST_SELECTORS

# Re-export models for backward compatibility
from .post_scraping_models import PostStats, CommentData, ScrapedProfile
from .engagement_scraping import PostEngagementScrapingMixin
from .post_persistence import PostPersistenceMixin


console = Console()


class PostScrapingWorkflow(
    PostEngagementScrapingMixin,
    PostPersistenceMixin
):
    """
    Workflow to scrape engagement data from Instagram posts.
    
    Features:
    - Extract post stats (likes, comments, shares, saves)
    - Scrape likers list with profile navigation
    - Scrape comments with replies (View more replies)
    - Comment sorting (For You, Most Recent, Meta Verified)
    - Profile enrichment (bio, website, threads, stats)
    """
    
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
            author_elem = self.device.xpath(POST_SELECTORS.post_author_username_selectors[0])
            if author_elem.exists:
                author = author_elem.get_text() or ""
            
            # Try to get stats from carousel content-desc
            carousel = self.device.xpath(POST_SELECTORS.carousel_indicators[2])
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
