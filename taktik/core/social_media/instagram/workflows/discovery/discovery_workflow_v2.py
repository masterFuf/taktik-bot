"""
Instagram Discovery Workflow V2

Orchestrateur principal pour le scraping intelligent de prospects.

Internal structure (SRP split):
- models.py              — Dataclasses and enums (ScrapingPhase, SourceType, ProgressState, etc.)
- session_management.py  — Campaign/session/progress DB operations, Instagram restart
- source_processing.py   — Target, hashtag, and post URL processing
- likers_scraping.py     — Likers scraping with optional enrichment
- comments_scraping.py   — Comments scraping with optional enrichment
- helpers.py             — Post navigation, enrichment, saving, summary

Fonctionnalités:
1. Système de reprise: peut reprendre là où il s'est arrêté
2. Ordre d'exécution: profil → posts → likers → commentaires → post suivant
3. Tracking de progression par source et par post
4. Stockage complet des commentaires avec réponses
"""

import time
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
from loguru import logger
from rich.console import Console
from rich.panel import Panel

from taktik.core.social_media.instagram.actions.core.device import DeviceManager
from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
from taktik.core.social_media.instagram.actions.atomic.scroll import ScrollActions
from taktik.core.social_media.instagram.actions.atomic.detection import DetectionActions
from taktik.core.social_media.instagram.actions.business.management.profile import ProfileBusiness
from taktik.core.social_media.instagram.ui.extractors import InstagramUIExtractors
from taktik.core.database.local.service import get_local_database

# Re-export models for backward compatibility
from .models import (
    ScrapingPhase, SourceType, ProgressState,
    ScrapedProfile, ScrapedComment, PostData
)
from .session_management import DiscoverySessionMixin
from .source_processing import DiscoverySourceProcessingMixin
from .likers_scraping import DiscoveryLikersScrapingMixin
from .comments_scraping import DiscoveryCommentsScrapingMixin
from .helpers import DiscoveryHelpersMixin


console = Console()


class DiscoveryWorkflowV2(
    DiscoverySessionMixin,
    DiscoverySourceProcessingMixin,
    DiscoveryLikersScrapingMixin,
    DiscoveryCommentsScrapingMixin,
    DiscoveryHelpersMixin
):
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
