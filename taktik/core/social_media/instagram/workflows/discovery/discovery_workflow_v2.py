"""
Instagram Discovery Workflow V2

Orchestrateur principal pour le scraping intelligent de prospects.
Architecture modulaire avec sous-modules spécialisés:
- TargetScrapingModule: Scrape un profil cible et ses posts
- PostScrapingModule: Scrape likers et commentaires d'un post
- HashtagScrapingModule: Scrape les posts d'un hashtag

Fonctionnalités:
1. Système de reprise: peut reprendre là où il s'est arrêté
2. Ordre d'exécution: profil → posts → likers → commentaires → post suivant
3. Tracking de progression par source et par post
4. Stockage complet des commentaires avec réponses
"""

import re
import time
import json
import subprocess
from datetime import datetime
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.panel import Panel

from taktik.core.social_media.instagram.actions.core.device_manager import DeviceManager
from taktik.core.social_media.instagram.actions.atomic.navigation_actions import NavigationActions
from taktik.core.social_media.instagram.actions.atomic.scroll_actions import ScrollActions
from taktik.core.social_media.instagram.actions.atomic.detection_actions import DetectionActions
from taktik.core.social_media.instagram.actions.business.management.profile import ProfileBusiness
from taktik.core.social_media.instagram.ui.extractors import InstagramUIExtractors
from taktik.core.social_media.instagram.ui.selectors import DETECTION_SELECTORS, POST_SELECTORS
from taktik.core.social_media.instagram.ui.detectors.scroll_end import ScrollEndDetector
from taktik.core.database.local_database import get_local_database


console = Console()


class ScrapingPhase(Enum):
    """Phases du scraping d'un post."""
    PROFILE = "profile"
    LIKERS = "likers"
    COMMENTS = "comments"
    DONE = "done"


class SourceType(Enum):
    """Types de sources pour le discovery."""
    TARGET = "target"
    HASHTAG = "hashtag"
    POST_URL = "post_url"


@dataclass
class ProgressState:
    """État de progression pour une source."""
    source_type: str
    source_value: str
    current_post_index: int = 0
    total_posts: int = 0
    current_phase: str = "profile"
    likers_scraped: int = 0
    likers_total: int = 0
    comments_scraped: int = 0
    comments_total: int = 0
    last_scroll_position: Dict = field(default_factory=dict)
    status: str = "in_progress"


@dataclass
class ScrapedProfile:
    """Profil scrapé avec toutes ses données."""
    username: str
    source_type: str
    source_value: str
    interaction_type: str  # 'liker' | 'commenter' | 'target'
    
    # Données du profil
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
    
    # Contexte d'engagement
    post_url: Optional[str] = None
    comment_content: Optional[str] = None
    comment_likes: int = 0
    
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ScrapedComment:
    """Commentaire scrapé avec réponses."""
    username: str
    content: str
    likes_count: int = 0
    is_reply: bool = False
    parent_username: Optional[str] = None
    replies: List['ScrapedComment'] = field(default_factory=list)


@dataclass
class PostData:
    """Données d'un post."""
    post_url: str
    author_username: str
    likes_count: int = 0
    comments_count: int = 0
    shares_count: int = 0
    saves_count: int = 0
    caption: str = ""


class DiscoveryWorkflowV2:
    """
    Orchestrateur principal pour le Discovery.
    
    Gère l'exécution séquentielle:
    1. Pour chaque target/hashtag
    2. Récupérer les infos du profil cible
    3. Pour chaque post:
       a. Extraire les stats
       b. Scraper tous les likers
       c. Scraper tous les commentaires avec réponses
       d. Passer au post suivant
    4. Enrichir les profils collectés
    5. Scorer avec l'IA
    """
    
    # UI Selectors
    SELECTORS = {
        # Post
        'post_author': 'com.instagram.android:id/row_feed_photo_profile_name',
        'like_button': 'com.instagram.android:id/row_feed_button_like',
        'comment_button': 'com.instagram.android:id/row_feed_button_comment',
        'carousel_media': 'com.instagram.android:id/carousel_video_media_group',
        
        # Comments
        'comments_title': 'com.instagram.android:id/title_text_view',
        'comments_list': 'com.instagram.android:id/sticky_header_list',
        'sort_menu_item': 'com.instagram.android:id/context_menu_item',
        
        # Profile
        'profile_name': 'com.instagram.android:id/action_bar_title',
        
        # Navigation
        'back_button': 'com.instagram.android:id/action_bar_button_back',
    }
    
    def __init__(self, device_id: str, config: Dict[str, Any]):
        """
        Initialize the workflow.
        
        Args:
            device_id: ADB device ID
            config: Configuration avec:
                - campaign_name: Nom de la campagne
                - targets: Liste de @usernames
                - hashtags: Liste de #hashtags
                - post_urls: Liste d'URLs de posts
                - max_posts_per_source: Nombre max de posts par source
                - max_likers_per_post: Nombre max de likers par post
                - max_comments_per_post: Nombre max de commentaires par post
                - enrich_profiles: Enrichir les profils (bool)
                - max_profiles_to_enrich: Limite d'enrichissement
                - comment_sort: 'for_you' | 'most_recent' | 'meta_verified'
                - resume: Reprendre une campagne existante (bool)
                - campaign_id: ID de campagne à reprendre
        """
        self.device_id = device_id
        self.config = config
        self.logger = logger.bind(workflow="discovery-v2")
        
        # Device & Actions - must connect first
        self.device_manager = DeviceManager(device_id)
        if not self.device_manager.connect():
            raise ValueError(f"Failed to connect to device {device_id}")
        self.device = self.device_manager.device
        self.nav_actions = NavigationActions(self.device)
        self.scroll_actions = ScrollActions(self.device)
        self.detection_actions = DetectionActions(self.device)
        self.profile_manager = ProfileBusiness(self.device)
        self.ui_extractors = InstagramUIExtractors(self.device)
        
        # Database - get raw connection for direct SQL
        self._db_service = get_local_database()
        self._db_conn = self._db_service._get_connection()
        
        # State
        self.campaign_id: Optional[int] = config.get('campaign_id')
        self.scraping_session_id: Optional[int] = None  # For scraping_sessions table
        self.progress_states: Dict[str, ProgressState] = {}
        self.scraped_profiles: List[ScrapedProfile] = []
        self.scraped_comments: List[ScrapedComment] = []
        self.start_time: Optional[datetime] = None
        self._recently_scraped_usernames: Set[str] = set()  # Cache of recently scraped usernames
        self._skipped_already_scraped: int = 0  # Counter for skipped profiles
        
        # Config defaults
        self.max_posts_per_source = config.get('max_posts_per_source', 5)
        self.max_likers_per_post = config.get('max_likers_per_post', 100)
        self.max_comments_per_post = config.get('max_comments_per_post', 200)
        self.enrich_profiles = config.get('enrich_profiles', True)
        self.max_profiles_to_enrich = config.get('max_profiles_to_enrich', 50)
        self.comment_sort = config.get('comment_sort', 'most_recent')
        self.session_duration_minutes = config.get('session_duration_minutes', 60)
        self.skip_recently_scraped = config.get('skip_recently_scraped', True)  # Skip profiles scraped in last X days
        self.skip_recently_scraped_days = config.get('skip_recently_scraped_days', 7)  # Days to consider as "recent"
        
    def run(self) -> Dict[str, Any]:
        """Execute the discovery workflow."""
        self.start_time = datetime.now()
        
        console.print(Panel.fit(
            "[bold cyan]🔍 Discovery Workflow V2[/bold cyan]\n"
            f"[dim]Targets: {len(self.config.get('targets', []))} | "
            f"Hashtags: {len(self.config.get('hashtags', []))} | "
            f"Posts: {len(self.config.get('post_urls', []))}[/dim]",
            border_style="cyan"
        ))
        
        try:
            # Force restart Instagram to ensure clean state
            self._restart_instagram()
            
            # Load recently scraped usernames to avoid re-visiting
            if self.skip_recently_scraped:
                self._load_recently_scraped_usernames()
            
            # Create or resume campaign
            if self.config.get('resume') and self.campaign_id:
                self._load_progress()
                console.print("[yellow]📂 Resuming previous campaign...[/yellow]")
            else:
                self._create_campaign()
            
            # Create scraping session for History tracking
            self._create_scraping_session()
            
            # Process each source type (enrichment happens on-the-fly if enabled)
            self._process_targets()
            self._process_hashtags()
            self._process_post_urls()
            
            # Save results
            self._save_results()
            
            # Mark campaign as COMPLETED
            self._update_campaign_status('COMPLETED')
            
            # Update scraping session as completed
            self._update_scraping_session('COMPLETED')
            
            # Summary
            duration = (datetime.now() - self.start_time).total_seconds()
            self._print_summary(duration)
            
            return {
                "success": True,
                "campaign_id": self.campaign_id,
                "profiles_scraped": len(self.scraped_profiles),
                "comments_scraped": len(self.scraped_comments),
                "duration_seconds": duration
            }
            
        except Exception as e:
            self.logger.error(f"Discovery error: {e}")
            console.print(f"[red]❌ Error: {e}[/red]")
            self._save_progress()  # Save progress for resume
            # Mark campaign as STOPPED on error
            self._update_campaign_status('STOPPED')
            # Update scraping session as error
            self._update_scraping_session('ERROR', str(e))
            return {"success": False, "error": str(e)}
    
    def _restart_instagram(self):
        """Force restart Instagram to ensure clean state.
        
        This is called at the beginning of each workflow to ensure
        Instagram starts from a known state (home feed).
        Same approach as TikTok workflows.
        """
        self.logger.info("🔄 Restarting Instagram for clean state...")
        console.print("[dim]🔄 Restarting Instagram...[/dim]")
        
        try:
            device_serial = self.device_id
            
            if device_serial:
                # Force stop Instagram
                self.logger.info("🛑 Force stopping Instagram...")
                stop_cmd = f'adb -s {device_serial} shell am force-stop com.instagram.android'
                subprocess.run(stop_cmd, shell=True, capture_output=True, timeout=10)
                self.logger.info("✅ Instagram stopped")
                
                # Wait a bit for clean shutdown
                time.sleep(1.5)
                
                # Relaunch Instagram
                self.logger.info("🚀 Relaunching Instagram...")
                launch_cmd = f'adb -s {device_serial} shell am start -n com.instagram.android/com.instagram.mainactivity.MainActivity'
                subprocess.run(launch_cmd, shell=True, capture_output=True, timeout=10)
                self.logger.info("✅ Instagram relaunched")
                
                # Wait for app to fully load
                time.sleep(4)
                console.print("[green]✅ Instagram restarted[/green]")
            else:
                self.logger.warning("⚠️ Could not get device serial, skipping restart")
                
        except Exception as e:
            self.logger.error(f"❌ Error restarting Instagram: {e}")
            # Try to continue anyway
    
    def _should_continue(self) -> bool:
        """Check if we should continue based on time limit."""
        if not self.start_time:
            return True
        elapsed = (datetime.now() - self.start_time).total_seconds() / 60
        return elapsed < self.session_duration_minutes
    
    def _create_campaign(self):
        """Create a new campaign in the database."""
        campaign_name = self.config.get('campaign_name', f"Discovery {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        cursor = self._db_conn.cursor()
        cursor.execute("""
            INSERT INTO discovery_campaigns (
                account_id, name, niche_keywords, target_hashtags, 
                target_accounts, target_post_urls, status
            ) VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE')
        """, (
            self.config.get('account_id', 1),
            campaign_name,
            json.dumps(self.config.get('niche_keywords', [])),
            json.dumps(self.config.get('hashtags', [])),
            json.dumps(self.config.get('targets', [])),
            json.dumps(self.config.get('post_urls', [])),
        ))
        self._db_conn.commit()
        self.campaign_id = cursor.lastrowid
        console.print(f"[green]✅ Campaign created: {campaign_name} (ID: {self.campaign_id})[/green]")
    
    def _update_campaign_status(self, status: str):
        """Update campaign status in database."""
        if not self.campaign_id:
            return
        try:
            cursor = self._db_conn.cursor()
            cursor.execute("""
                UPDATE discovery_campaigns 
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, self.campaign_id))
            self._db_conn.commit()
            self.logger.info(f"Campaign {self.campaign_id} status updated to {status}")
        except Exception as e:
            self.logger.error(f"Failed to update campaign status: {e}")
    
    def _create_scraping_session(self):
        """Create a scraping session entry for History tracking."""
        try:
            # Determine source name from config
            targets = self.config.get('targets', [])
            hashtags = self.config.get('hashtags', [])
            post_urls = self.config.get('post_urls', [])
            
            if targets:
                source_type = 'TARGET'
                source_name = f"@{targets[0]}" if len(targets) == 1 else f"@{targets[0]} +{len(targets)-1}"
            elif hashtags:
                source_type = 'HASHTAG'
                source_name = f"#{hashtags[0]}" if len(hashtags) == 1 else f"#{hashtags[0]} +{len(hashtags)-1}"
            elif post_urls:
                source_type = 'POST_URL'
                source_name = post_urls[0][:50] if len(post_urls) == 1 else f"{post_urls[0][:30]}... +{len(post_urls)-1}"
            else:
                source_type = 'DISCOVERY'
                source_name = 'Discovery Campaign'
            
            self.scraping_session_id = self._db_service.create_scraping_session(
                scraping_type='DISCOVERY',
                source_type=source_type,
                source_name=source_name,
                max_profiles=self.max_profiles_to_enrich,
                export_csv=False,
                save_to_db=True,
                account_id=self.config.get('account_id', 1),
                config=self.config
            )
            
            if self.scraping_session_id:
                self.logger.info(f"Created scraping session {self.scraping_session_id} for History tracking")
        except Exception as e:
            self.logger.warning(f"Failed to create scraping session: {e}")
    
    def _update_scraping_session(self, status: str, error_message: Optional[str] = None):
        """Update the scraping session with final status."""
        if not self.scraping_session_id:
            return
        try:
            duration = int((datetime.now() - self.start_time).total_seconds()) if self.start_time else 0
            
            self._db_service.update_scraping_session(
                self.scraping_session_id,
                status=status,
                total_scraped=len(self.scraped_profiles),
                end_time=datetime.now().isoformat(),
                duration_seconds=duration,
                error_message=error_message
            )
            self.logger.info(f"Updated scraping session {self.scraping_session_id}: {status}, {len(self.scraped_profiles)} profiles")
        except Exception as e:
            self.logger.warning(f"Failed to update scraping session: {e}")
    
    def _load_recently_scraped_usernames(self):
        """Load usernames of profiles that were recently scraped to avoid re-visiting."""
        try:
            self._recently_scraped_usernames = self._db_service.get_recently_scraped_usernames(
                days=self.skip_recently_scraped_days
            )
            count = len(self._recently_scraped_usernames)
            if count > 0:
                self.logger.info(f"📋 Loaded {count} recently scraped usernames (last {self.skip_recently_scraped_days} days)")
                console.print(f"[dim]📋 Skipping {count} profiles already scraped in last {self.skip_recently_scraped_days} days[/dim]")
            else:
                self.logger.info("No recently scraped profiles found in database")
        except Exception as e:
            self.logger.warning(f"Failed to load recently scraped usernames: {e}")
            self._recently_scraped_usernames = set()
    
    def _is_profile_recently_scraped(self, username: str) -> bool:
        """Check if a profile was recently scraped (using cached set for performance)."""
        if not self.skip_recently_scraped:
            return False
        return username in self._recently_scraped_usernames
    
    def _load_progress(self):
        """Load progress state from database."""
        cursor = self._db_conn.cursor()
        cursor.execute("""
            SELECT source_type, source_value, current_post_index, total_posts,
                   current_phase, likers_scraped, likers_total, 
                   comments_scraped, comments_total, last_scroll_position, status
            FROM discovery_progress
            WHERE campaign_id = ? AND status != 'completed'
        """, (self.campaign_id,))
        rows = cursor.fetchall()
        
        for row in rows:
            key = f"{row[0]}:{row[1]}"
            self.progress_states[key] = ProgressState(
                source_type=row[0],
                source_value=row[1],
                current_post_index=row[2],
                total_posts=row[3],
                current_phase=row[4],
                likers_scraped=row[5],
                likers_total=row[6],
                comments_scraped=row[7],
                comments_total=row[8],
                last_scroll_position=json.loads(row[9] or '{}'),
                status=row[10]
            )
        
        console.print(f"[dim]Loaded {len(self.progress_states)} progress states[/dim]")
    
    def _save_progress(self):
        """Save current progress to database."""
        cursor = self._db_conn.cursor()
        for key, state in self.progress_states.items():
            cursor.execute("""
                INSERT OR REPLACE INTO discovery_progress (
                    campaign_id, source_type, source_value, current_post_index,
                    total_posts, current_phase, likers_scraped, likers_total,
                    comments_scraped, comments_total, last_scroll_position, 
                    status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                self.campaign_id,
                state.source_type,
                state.source_value,
                state.current_post_index,
                state.total_posts,
                state.current_phase,
                state.likers_scraped,
                state.likers_total,
                state.comments_scraped,
                state.comments_total,
                json.dumps(state.last_scroll_position),
                state.status
            ))
        self._db_conn.commit()
    
    def _get_or_create_progress(self, source_type: str, source_value: str) -> ProgressState:
        """Get existing progress or create new one."""
        key = f"{source_type}:{source_value}"
        if key not in self.progress_states:
            self.progress_states[key] = ProgressState(
                source_type=source_type,
                source_value=source_value
            )
        return self.progress_states[key]
    
    # ==========================================
    # TARGET PROCESSING
    # ==========================================
    
    def _process_targets(self):
        """Process all target accounts."""
        targets = self.config.get('targets', [])
        if not targets:
            return
        
        console.print(f"\n[bold cyan]👤 Processing {len(targets)} target accounts...[/bold cyan]")
        
        for target in targets:
            if not self._should_continue():
                break
            self._process_single_target(target.lstrip('@'))
    
    def _process_single_target(self, username: str):
        """Process a single target account."""
        self.logger.info(f"📍 Target: @{username}")
        console.print(f"\n[cyan]📍 Target: @{username}[/cyan]")
        
        progress = self._get_or_create_progress('target', username)
        
        # Phase 1: Get profile info (this navigates to profile)
        if progress.current_phase == 'profile':
            if not self._scrape_target_profile(username, progress):
                return
            progress.current_phase = 'likers'
            self._save_progress()
        else:
            # If resuming, need to navigate to profile
            if not self.nav_actions.navigate_to_profile(username):
                self.logger.warning(f"Failed to navigate to @{username}")
                return
            time.sleep(2)
        
        # Open first post
        if not self._open_first_post():
            self.logger.warning(f"No posts found for @{username}")
            return
        
        # Process posts
        post_index = progress.current_post_index
        processed_post_signatures = set()  # Track post signatures (likes, comments) to detect duplicates
        duplicate_count = 0
        max_duplicates = 5
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as prog:
            task = prog.add_task(f"[cyan]@{username} posts", total=self.max_posts_per_source)
            prog.update(task, completed=post_index)
            
            while post_index < self.max_posts_per_source and self._should_continue():
                # Get post stats and create signature
                post_data = self._get_current_post_stats()
                post_signature = (post_data.likes_count, post_data.comments_count)
                
                # Check if we've already processed this post (same likes + comments = same post)
                if post_signature in processed_post_signatures:
                    duplicate_count += 1
                    self.logger.warning(f"⚠️ Duplicate post detected ({post_data.likes_count} likes, {post_data.comments_count} comments) - attempt {duplicate_count}/{max_duplicates}")
                    
                    if duplicate_count >= max_duplicates:
                        self.logger.warning(f"Too many duplicates, ending post processing for @{username}")
                        console.print(f"[yellow]    ⚠️ Cannot find more unique posts, stopping[/yellow]")
                        break
                    
                    # Try scrolling again to find next post
                    self.scroll_actions.scroll_down()
                    time.sleep(1.5)
                    continue
                
                # New unique post found
                duplicate_count = 0
                processed_post_signatures.add(post_signature)
                post_url = f"@{username}/post/{post_index}"
                
                self.logger.info(f"📝 Post {post_index + 1}: {post_data.likes_count} likes, {post_data.comments_count} comments")
                console.print(f"[dim]  Post {post_index + 1}: {post_data.likes_count} likes, {post_data.comments_count} comments[/dim]")
                
                # Scrape likers
                if progress.current_phase == 'likers':
                    self._scrape_post_likers(
                        post_url=post_url,
                        source_type='target',
                        source_value=username,
                        progress=progress,
                        max_count=self.max_likers_per_post
                    )
                    progress.current_phase = 'comments'
                    self._save_progress()
                
                # Scrape comments
                if progress.current_phase == 'comments':
                    self._scrape_post_comments(
                        post_url=post_url,
                        source_type='target',
                        source_value=username,
                        progress=progress,
                        max_count=self.max_comments_per_post
                    )
                    progress.current_phase = 'likers'  # Reset for next post
                    progress.likers_scraped = 0
                    progress.comments_scraped = 0
                    self._save_progress()
                
                # Next post
                post_index += 1
                progress.current_post_index = post_index
                self._save_progress()
                
                prog.update(task, completed=post_index)
                
                # Swipe to next post
                if post_index < self.max_posts_per_source:
                    self.scroll_actions.scroll_down()
                    time.sleep(1.5)
        
        # Mark as done
        progress.status = 'completed'
        self._save_progress()
        
        # Go back
        self.device.press("back")
        time.sleep(1)
        
        console.print(f"[green]✅ @{username}: {post_index} posts processed[/green]")
    
    def _scrape_target_profile(self, username: str, progress: ProgressState) -> bool:
        """Scrape target profile info."""
        if not self.nav_actions.navigate_to_profile(username):
            return False
        
        time.sleep(2)
        
        try:
            info = self.profile_manager.get_complete_profile_info(
                username=username,
                navigate_if_needed=False
            )
            
            if info:
                self.scraped_profiles.append(ScrapedProfile(
                    username=username,
                    source_type='target',
                    source_value=username,
                    interaction_type='target',
                    bio=info.get('biography', ''),
                    website=info.get('external_url', ''),
                    followers_count=info.get('followers_count', 0),
                    following_count=info.get('following_count', 0),
                    posts_count=info.get('posts_count', 0),
                    is_private=info.get('is_private', False),
                    is_verified=info.get('is_verified', False),
                    is_business=info.get('is_business', False),
                    category=info.get('category', '')
                ))
                console.print(f"[dim]  Profile: {info.get('followers_count', 0)} followers, {info.get('posts_count', 0)} posts[/dim]")
                return True
        except Exception as e:
            self.logger.warning(f"Error getting profile info: {e}")
        
        return True  # Continue anyway
    
    # ==========================================
    # HASHTAG PROCESSING
    # ==========================================
    
    def _process_hashtags(self):
        """Process all hashtags."""
        hashtags = self.config.get('hashtags', [])
        if not hashtags:
            return
        
        console.print(f"\n[bold cyan]#️⃣ Processing {len(hashtags)} hashtags...[/bold cyan]")
        
        # Navigate to home first to ensure clean state for hashtag navigation
        self.nav_actions.navigate_to_home()
        time.sleep(2)
        
        for hashtag in hashtags:
            if not self._should_continue():
                break
            self._process_single_hashtag(hashtag.lstrip('#'))
    
    def _process_single_hashtag(self, hashtag: str):
        """Process a single hashtag."""
        console.print(f"\n[cyan]📍 Hashtag: #{hashtag}[/cyan]")
        
        progress = self._get_or_create_progress('hashtag', hashtag)
        
        # Navigate to hashtag
        if not self.nav_actions.navigate_to_hashtag(hashtag):
            self.logger.warning(f"Failed to navigate to #{hashtag}")
            return
        
        time.sleep(2)
        
        # Process posts (similar to targets)
        post_index = progress.current_post_index
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as prog:
            task = prog.add_task(f"[cyan]#{hashtag} posts", total=self.max_posts_per_source)
            prog.update(task, completed=post_index)
            
            while post_index < self.max_posts_per_source and self._should_continue():
                # Click on post
                if not self._click_post_in_grid(post_index):
                    break
                
                time.sleep(1.5)
                
                post_url = f"#{hashtag}/post/{post_index}"
                post_data = self._get_current_post_stats()
                
                console.print(f"[dim]  Post {post_index + 1}: {post_data.likes_count} likes, {post_data.comments_count} comments[/dim]")
                
                # Scrape likers
                if progress.current_phase in ['profile', 'likers']:
                    self._scrape_post_likers(
                        post_url=post_url,
                        source_type='hashtag',
                        source_value=hashtag,
                        progress=progress,
                        max_count=self.max_likers_per_post
                    )
                    progress.current_phase = 'comments'
                    self._save_progress()
                
                # Scrape comments
                if progress.current_phase == 'comments':
                    self._scrape_post_comments(
                        post_url=post_url,
                        source_type='hashtag',
                        source_value=hashtag,
                        progress=progress,
                        max_count=self.max_comments_per_post
                    )
                    progress.current_phase = 'likers'
                    progress.likers_scraped = 0
                    progress.comments_scraped = 0
                    self._save_progress()
                
                # Go back to grid
                self.device.press("back")
                time.sleep(1)
                
                post_index += 1
                progress.current_post_index = post_index
                self._save_progress()
                
                prog.update(task, completed=post_index)
        
        progress.status = 'completed'
        self._save_progress()
        
        console.print(f"[green]✅ #{hashtag}: {post_index} posts processed[/green]")
    
    # ==========================================
    # POST URL PROCESSING
    # ==========================================
    
    def _process_post_urls(self):
        """Process specific post URLs."""
        post_urls = self.config.get('post_urls', [])
        if not post_urls:
            return
        
        console.print(f"\n[bold cyan]🔗 Processing {len(post_urls)} post URLs...[/bold cyan]")
        
        for url in post_urls:
            if not self._should_continue():
                break
            self._process_single_post_url(url)
    
    def _process_single_post_url(self, post_url: str):
        """Process a single post URL."""
        console.print(f"\n[cyan]📍 Post URL: {post_url[:50]}...[/cyan]")
        
        progress = self._get_or_create_progress('post_url', post_url)
        
        # Navigate to post
        if not self.nav_actions.navigate_to_post_url(post_url):
            self.logger.warning(f"Failed to navigate to post")
            return
        
        time.sleep(2)
        
        post_data = self._get_current_post_stats()
        console.print(f"[dim]  Stats: {post_data.likes_count} likes, {post_data.comments_count} comments[/dim]")
        
        # Scrape likers
        if progress.current_phase in ['profile', 'likers']:
            self._scrape_post_likers(
                post_url=post_url,
                source_type='post_url',
                source_value=post_url,
                progress=progress,
                max_count=self.max_likers_per_post
            )
            progress.current_phase = 'comments'
            self._save_progress()
        
        # Scrape comments
        if progress.current_phase == 'comments':
            self._scrape_post_comments(
                post_url=post_url,
                source_type='post_url',
                source_value=post_url,
                progress=progress,
                max_count=self.max_comments_per_post
            )
        
        progress.status = 'completed'
        self._save_progress()
        
        console.print(f"[green]✅ Post processed[/green]")
    
    # ==========================================
    # LIKERS SCRAPING
    # ==========================================
    
    def _scrape_post_likers(self, post_url: str, source_type: str, source_value: str,
                           progress: ProgressState, max_count: int):
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
            indicators = [
                '//*[contains(@content-desc, "Likes")]',
                '//*[contains(@text, "Likes")]',
                '//*[@resource-id="com.instagram.android:id/row_user_container_base"]'
            ]
            for selector in indicators:
                if self.device.xpath(selector).exists:
                    return True
        except:
            pass
        return False
    
    # ==========================================
    # COMMENTS SCRAPING
    # ==========================================
    
    def _scrape_post_comments(self, post_url: str, source_type: str, source_value: str,
                             progress: ProgressState, max_count: int):
        """Scrape comments from current post with optional on-the-fly enrichment."""
        enrich_mode = "with enrichment" if self.enrich_profiles else "usernames only"
        console.print(f"[dim]    💬 Scraping comments ({enrich_mode})...[/dim]")
        self.logger.info(f"Starting comments scraping - max: {max_count}, enrich: {self.enrich_profiles}")
        
        # Open comments
        if not self._open_comments():
            console.print(f"[yellow]    ⚠️ Could not open comments[/yellow]")
            return
        
        time.sleep(1.5)
        
        # Change sort if needed
        self._change_comment_sort()
        
        seen_usernames = set()
        scroll_attempts = 0
        max_scroll_attempts = 20
        start_count = progress.comments_scraped
        enriched_count = 0
        
        while progress.comments_scraped < max_count and scroll_attempts < max_scroll_attempts:
            # Find comment author usernames from the comments list
            # Structure: sticky_header_list > ViewGroup > ViewGroup > ViewGroup (with username as text) > Button (username)
            # The username Button is the first child of a ViewGroup that has the username as text attribute
            username_selectors = [
                # Primary: Username buttons - first Button child of ViewGroup with text (the username container)
                '//*[@resource-id="com.instagram.android:id/sticky_header_list"]//android.view.ViewGroup[@text]/android.widget.Button[@text]',
                # Fallback 1: Any Button with text inside sticky_header_list
                '//*[@resource-id="com.instagram.android:id/sticky_header_list"]//android.widget.Button[@text]',
                # Fallback 2: Old selector
                '//*[@resource-id="com.instagram.android:id/row_comment_textview_comment_container"]//android.widget.Button',
            ]
            
            found_new = False
            total_elements_found = 0
            for selector in username_selectors:
                elements = self.device.xpath(selector).all()
                total_elements_found += len(elements)
                for elem in elements:
                    try:
                        # Get username from text attribute (primary) or content-desc (fallback)
                        username = elem.text or elem.attrib.get('text', '') or ''
                        
                        # Skip non-username buttons (Reply, See translation, For you, etc.)
                        skip_texts = ['Reply', 'See translation', 'For you', 'View', 'likes', 'like']
                        if any(skip in username for skip in skip_texts):
                            continue
                        
                        # Clean username
                        username = username.strip().lstrip('@')
                        
                        # Validate username format (alphanumeric, dots, underscores, max 30 chars)
                        if not username or username in seen_usernames:
                            continue
                        if len(username) > 30 or ' ' in username:
                            continue
                        # Skip if it looks like a resource ID (numeric)
                        if username.isdigit():
                            continue
                        
                        # Try to extract comment text and detect if it's a reply
                        comment_text = ''
                        is_reply = False
                        try:
                            # The comment text is in the parent ViewGroup's content-desc
                            # Format: "username comment text"
                            parent = elem.get_parent()
                            if parent:
                                parent_desc = parent.attrib.get('content-desc', '')
                                if parent_desc and username in parent_desc:
                                    # Remove username from the beginning to get comment text
                                    comment_text = parent_desc.replace(username, '', 1).strip()
                                
                                # Detect if this is a reply based on indentation (bounds)
                                # Replies start around x=100-105, main comments start at x=23
                                bounds = elem.attrib.get('bounds', '')
                                if bounds:
                                    # Parse bounds format: [x1,y1][x2,y2]
                                    import re
                                    bounds_match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                                    if bounds_match:
                                        x1 = int(bounds_match.group(1))
                                        # If x1 > 80, it's likely a reply (indented comment)
                                        is_reply = x1 > 80
                        except:
                            pass
                        
                        seen_usernames.add(username)
                        
                        # Check if already scraped recently (to skip enrichment, not the profile itself)
                        already_scraped = self._is_profile_recently_scraped(username)
                        
                        # Create profile object (always record the interaction)
                        profile = ScrapedProfile(
                            username=username,
                            source_type=source_type,
                            source_value=source_value,
                            interaction_type='commenter',
                            post_url=post_url
                        )
                        
                        # Save comment to database (with text if extracted)
                        try:
                            db = get_local_database()
                            db.save_scraped_comment(
                                username=username,
                                content=comment_text,
                                target_username=source_value,
                                post_url=post_url,
                                scraping_session_id=self._scraping_session_id if hasattr(self, '_scraping_session_id') else None,
                                is_reply=is_reply
                            )
                        except Exception as e:
                            self.logger.debug(f"Could not save comment: {e}")
                        
                        # If already scraped, skip enrichment but still record the interaction
                        if already_scraped:
                            self._skipped_already_scraped += 1
                            self.logger.info(f"⏭️ SKIP @{username} | reason=already_scraped | days={self.skip_recently_scraped_days}")
                            # Still add to scraped profiles to track the interaction
                            self.scraped_profiles.append(profile)
                            progress.comments_scraped += 1
                            found_new = True
                            if progress.comments_scraped >= max_count:
                                break
                            continue
                        
                        # Log for Live Panel with comment content
                        reply_tag = " [REPLY]" if is_reply else ""
                        comment_preview = f" | comment={comment_text[:100]}" if comment_text else ""
                        self.logger.info(f"💬 COMMENT @{username}{reply_tag}{comment_preview}")
                        
                        # Enrich on-the-fly if enabled (only for new profiles)
                        if self.enrich_profiles and enriched_count < self.max_profiles_to_enrich:
                            try:
                                console.print(f"[dim]      → Enriching @{username}...[/dim]")
                                # Click on username to navigate to profile
                                elem.click()
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
                                    # Log in parsable format for Live Panel
                                    bio_escaped = (profile.bio or '').replace('\n', '\\n')[:500]
                                    self.logger.info(f"✅ PROFILE @{username} | followers={profile.followers_count} | posts={profile.posts_count} | following={profile.following_count} | category={profile.category or ''} | website={profile.website or ''} | bio={bio_escaped} | private={profile.is_private} | verified={profile.is_verified} | business={profile.is_business}")
                                    console.print(f"[dim]      ✅ {profile.followers_count} followers, {profile.posts_count} posts[/dim]")
                                
                                # Go back to comments
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
                        progress.comments_scraped += 1
                        found_new = True
                        
                        if progress.comments_scraped >= max_count:
                            break
                    except:
                        continue
                if progress.comments_scraped >= max_count:
                    break
            
            if not found_new:
                scroll_attempts += 1
            else:
                scroll_attempts = 0
            
            # Log progress with element count for debugging
            self.logger.debug(f"Comments progress: {progress.comments_scraped}/{max_count} (seen: {len(seen_usernames)}, enriched: {enriched_count}, elements: {total_elements_found})")
            
            # Scroll to load more comments (use comments-specific scroll)
            if progress.comments_scraped < max_count:
                self.scroll_actions.scroll_comments_down()
                time.sleep(1)
        
        # Go back
        self.device.press("back")
        time.sleep(1)
        
        scraped = progress.comments_scraped - start_count
        self.logger.info(f"Comments scraping complete: {scraped} scraped, {enriched_count} enriched")
        console.print(f"[dim]    ✅ {scraped} comments scraped ({enriched_count} enriched)[/dim]")
    
    def _open_comments(self) -> bool:
        """Open comments section."""
        try:
            # Try resource-id first
            comment_btn = self.device.xpath(f'//*[@resource-id="{self.SELECTORS["comment_button"]}"]')
            if comment_btn.exists:
                comment_btn.click()
                time.sleep(1.5)
                if self._is_comments_view_open():
                    self.logger.debug("Comments opened via resource-id")
                    return True
            
            # Try content-desc selectors
            comment_selectors = [
                '//*[contains(@content-desc, "Comment")][@clickable="true"]',
                '//*[contains(@content-desc, "comment")][@clickable="true"]',
                '//android.widget.ImageView[contains(@content-desc, "Comment")]'
            ]
            
            for selector in comment_selectors:
                try:
                    elem = self.device.xpath(selector)
                    if elem.exists:
                        elem.click()
                        time.sleep(1.5)
                        if self._is_comments_view_open():
                            self.logger.debug(f"Comments opened via {selector}")
                            return True
                except:
                    continue
            
            self.logger.warning("Could not open comments")
            return False
        except Exception as e:
            self.logger.error(f"Error opening comments: {e}")
            return False
    
    def _is_comments_view_open(self) -> bool:
        """Check if comments view is open."""
        try:
            indicators = [
                f'//*[@resource-id="{self.SELECTORS["comments_list"]}"]',
                '//*[contains(@text, "Comments")]',
                '//*[contains(@content-desc, "Add a comment")]'
            ]
            for selector in indicators:
                if self.device.xpath(selector).exists:
                    return True
        except:
            pass
        return False
    
    def _change_comment_sort(self):
        """Change comment sorting."""
        if self.comment_sort == 'for_you':
            return
        
        try:
            sort_btn = self.device.xpath('//*[@content-desc="For you"]')
            if sort_btn.exists:
                sort_btn.click()
                time.sleep(1)
                
                sort_map = {
                    'most_recent': 'Most recent',
                    'meta_verified': 'Meta Verified'
                }
                target = sort_map.get(self.comment_sort, 'Most recent')
                option = self.device.xpath(f'//*[@content-desc="{target}"]')
                if option.exists:
                    option.click()
                    time.sleep(1)
                else:
                    self.device.press("back")
        except:
            pass
    
    def _expand_all_replies(self):
        """Click on all 'View X more reply' buttons."""
        try:
            reply_btns = self.device.xpath('//*[contains(@content-desc, "View") and contains(@content-desc, "more repl")]')
            if reply_btns.exists:
                for btn in reply_btns.all()[:5]:
                    try:
                        btn.click()
                        time.sleep(0.3)
                    except:
                        pass
        except:
            pass
    
    # ==========================================
    # HELPER METHODS
    # ==========================================
    
    def _open_first_post(self) -> bool:
        """Open the first post of a profile (same logic as ScrapingWorkflow)."""
        try:
            self.logger.info("Opening first post of profile...")
            console.print(f"[dim]📸 Looking for first post...[/dim]")
            
            # Use the same selector as ScrapingWorkflow
            posts = self.device.xpath(DETECTION_SELECTORS.post_thumbnail_selectors[0]).all()
            
            if not posts:
                # Try alternative selector
                posts = self.device.xpath('//*[@resource-id="com.instagram.android:id/image_button"]').all()
            
            if not posts:
                self.logger.error("No posts found in grid")
                return False
            
            first_post = posts[0]
            first_post.click()
            self.logger.debug("Clicking on first post...")
            
            time.sleep(3)  # Wait for post to load
            
            if self._is_on_post_view():
                self.logger.info("✅ First post opened successfully")
                return True
            else:
                self.logger.error("Failed to open first post")
                return False
                
        except Exception as e:
            self.logger.error(f"Error opening first post: {e}")
            return False
    
    def _is_on_post_view(self) -> bool:
        """Check if we're in a post view (same logic as ScrapingWorkflow)."""
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
    
    def _click_post_in_grid(self, index: int) -> bool:
        """Click on a post in hashtag grid (same logic as ScrapingWorkflow)."""
        try:
            # Use centralized selectors
            posts = self.device.xpath(DETECTION_SELECTORS.post_thumbnail_selectors[0]).all()
            
            if not posts:
                posts = self.device.xpath('//*[@resource-id="com.instagram.android:id/image_button"]').all()
            
            if posts and index < len(posts):
                posts[index].click()
                time.sleep(3)
                return self._is_on_post_view()
        except:
            pass
        return False
    
    def _get_current_post_stats(self) -> PostData:
        """Get stats from current post."""
        author = ""
        likes = 0
        comments = 0
        shares = 0
        saves = 0
        
        try:
            # Author
            author_elem = self.device.xpath(f'//*[@resource-id="{self.SELECTORS["post_author"]}"]')
            if author_elem.exists:
                author = author_elem.get_text() or ""
            
            # Stats from carousel
            carousel = self.device.xpath(f'//*[@resource-id="{self.SELECTORS["carousel_media"]}"]')
            if carousel.exists:
                desc = carousel.info.get('contentDescription', '')
                match = re.search(r'(\d+)\s*likes?,\s*(\d+)\s*comments?', desc)
                if match:
                    likes = int(match.group(1))
                    comments = int(match.group(2))
            
            # Individual counts
            buttons = self.device.xpath('//android.widget.Button').all()
            for i, btn in enumerate(buttons):
                text = btn.get_text() if hasattr(btn, 'get_text') else ''
                if text and text.isdigit():
                    count = int(text)
                    if i > 0:
                        prev_desc = buttons[i-1].info.get('contentDescription', '')
                        if 'Like' in prev_desc and likes == 0:
                            likes = count
                        elif 'Comment' in prev_desc and comments == 0:
                            comments = count
        except:
            pass
        
        return PostData(
            post_url="",
            author_username=author,
            likes_count=likes,
            comments_count=comments,
            shares_count=shares,
            saves_count=saves
        )
    
    # ==========================================
    # ENRICHMENT & SAVING
    # ==========================================
    
    def _enrich_profiles(self):
        """Enrich collected profiles with full data."""
        # Get unique profiles that need enrichment
        profiles_to_enrich = {}
        for p in self.scraped_profiles:
            if p.username not in profiles_to_enrich and p.interaction_type != 'target':
                profiles_to_enrich[p.username] = p
        
        # Sort by engagement (commenters first, then by comment likes)
        sorted_profiles = sorted(
            profiles_to_enrich.values(),
            key=lambda p: (p.interaction_type == 'commenter', p.comment_likes),
            reverse=True
        )[:self.max_profiles_to_enrich]
        
        if not sorted_profiles:
            return
        
        console.print(f"\n[cyan]👤 Enriching {len(sorted_profiles)} profiles...[/cyan]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as prog:
            task = prog.add_task("[cyan]Enriching...", total=len(sorted_profiles))
            
            for profile in sorted_profiles:
                if not self._should_continue():
                    break
                
                try:
                    if self.nav_actions.navigate_to_profile(profile.username):
                        time.sleep(1.5)
                        
                        # Use enrich=True to get all enriched data (bio, website, business_category, linked_accounts)
                        info = self.profile_manager.get_complete_profile_info(
                            username=profile.username,
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
                            
                            # Store linked accounts (Thread, Facebook, etc.)
                            linked = info.get('linked_accounts', [])
                            if linked:
                                for account in linked:
                                    if 'thread' in account.get('name', '').lower():
                                        profile.threads_username = account.get('name', '')
                                    # Could also extract Facebook, etc.
                        
                        self.device.press("back")
                        time.sleep(0.5)
                except Exception as e:
                    self.logger.warning(f"Error enriching @{profile.username}: {e}")
                
                prog.update(task, advance=1)
        
        console.print(f"[green]✅ Enrichment complete[/green]")
    
    def _save_results(self):
        """Save all results to database."""
        console.print(f"\n[cyan]💾 Saving results...[/cyan]")
        
        profiles_saved = 0
        comments_saved = 0
        
        try:
            cursor = self._db_conn.cursor()
            
            # Save profiles
            for profile in self.scraped_profiles:
                cursor.execute(
                    "SELECT profile_id FROM discovered_profiles WHERE campaign_id = ? AND username = ?",
                    (self.campaign_id, profile.username)
                )
                existing = cursor.fetchone()
                
                if not existing:
                    cursor.execute("""
                        INSERT INTO discovered_profiles (
                            campaign_id, username, source_type, source_name,
                            biography, followers_count, following_count, posts_count,
                            is_private, is_verified, is_business, category
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        self.campaign_id,
                        profile.username,
                        profile.source_type,
                        profile.source_value,
                        profile.bio or '',
                        profile.followers_count,
                        profile.following_count,
                        profile.posts_count,
                        1 if profile.is_private else 0,
                        1 if profile.is_verified else 0,
                        1 if profile.is_business else 0,
                        profile.category or ''
                    ))
                    profiles_saved += 1
            
            # Save comments
            for comment in self.scraped_comments:
                cursor.execute("""
                    INSERT INTO scraped_comments (
                        campaign_id, post_url, username, content, likes_count
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    self.campaign_id,
                    '',  # post_url
                    comment.username,
                    comment.content,
                    comment.likes_count
                ))
                comments_saved += 1
            
            self._db_conn.commit()
            console.print(f"[green]✅ Saved {profiles_saved} profiles, {comments_saved} comments[/green]")
            
        except Exception as e:
            self.logger.error(f"Error saving results: {e}")
            console.print(f"[red]❌ Save error: {e}[/red]")
    
    def _print_summary(self, duration: float):
        """Print final summary."""
        console.print("\n" + "="*50)
        console.print("[bold green]📊 Discovery Complete![/bold green]")
        console.print("="*50)
        
        table = Table(show_header=False, box=None)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        
        # Count by type
        likers = sum(1 for p in self.scraped_profiles if p.interaction_type == 'liker')
        commenters = sum(1 for p in self.scraped_profiles if p.interaction_type == 'commenter')
        targets = sum(1 for p in self.scraped_profiles if p.interaction_type == 'target')
        
        table.add_row("Campaign ID", str(self.campaign_id))
        table.add_row("", "")
        table.add_row("Target Profiles", str(targets))
        table.add_row("Likers Scraped", str(likers))
        table.add_row("Commenters Scraped", str(commenters))
        table.add_row("Comments Collected", str(len(self.scraped_comments)))
        if self._skipped_already_scraped > 0:
            table.add_row("Skipped (already scraped)", str(self._skipped_already_scraped))
        table.add_row("", "")
        table.add_row("Duration", f"{duration:.1f}s")
        
        console.print(table)
        console.print("="*50 + "\n")
