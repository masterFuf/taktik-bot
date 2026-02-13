"""
Instagram Scraping Workflow

This module provides scraping functionality to extract profiles from:
- Target followers/following
- Hashtag posts (authors or likers)
- Post URL likers

Internal structure (SRP split):
- post_scraping_helpers.py — Post opening, reel detection, likers/commenters extraction
- list_scraping.py         — Generic list scraping, hashtag scraping, post URL scraping
- persistence.py           — CSV export, DB save, session management, enrichment, stats
- scraping_workflow.py     — Orchestrator (this file)
"""

import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from loguru import logger
from rich.console import Console

from taktik.core.social_media.instagram.actions.core.device_manager import DeviceManager
from taktik.core.social_media.instagram.actions.atomic.navigation_actions import NavigationActions
from taktik.core.social_media.instagram.actions.atomic.detection_actions import DetectionActions
from taktik.core.social_media.instagram.actions.atomic.scroll_actions import ScrollActions
from taktik.core.social_media.instagram.actions.business.management.profile import ProfileBusiness
from taktik.core.social_media.instagram.ui.extractors import InstagramUIExtractors

from .post_scraping_helpers import ScrapingPostHelpersMixin
from .list_scraping import ScrapingListMixin
from .persistence import ScrapingPersistenceMixin


console = Console()


class ScrapingWorkflow(
    ScrapingPostHelpersMixin,
    ScrapingListMixin,
    ScrapingPersistenceMixin
):
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
        self._save_immediately = config.get('save_to_db', True)  # Save profiles as we scrape them
        
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
        """Scrape followers, following, or post likers/commenters from target accounts."""
        target_usernames = self.config.get('target_usernames', [])
        scrape_type = self.config.get('scrape_type', 'followers')
        max_profiles_requested = self.config.get('max_profiles', 500)
        
        # Posts scraping options
        scrape_post_likers = self.config.get('scrape_post_likers', True)
        scrape_post_commenters = self.config.get('scrape_post_commenters', False)
        
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
            
            remaining_to_scrape = max_profiles_requested - total_scraped
            
            if profile_info:
                if scrape_type == 'followers':
                    available_count = profile_info.get('followers_count', 0)
                elif scrape_type == 'following':
                    available_count = profile_info.get('following_count', 0)
                else:  # posts
                    available_count = remaining_to_scrape  # Unknown for posts
                
                # Adjust max to what's actually available
                # If count detection failed (0), use requested max and try anyway
                if available_count == 0:
                    console.print(f"[yellow]⚠️ Could not detect {scrape_type} count for @{target}, trying anyway...[/yellow]")
                    actual_max = remaining_to_scrape
                    available_count = remaining_to_scrape  # Use requested as fallback
                else:
                    actual_max = min(remaining_to_scrape, available_count)
                    if scrape_type != 'posts':
                        console.print(f"[green]✅ @{target}: {available_count:,} {scrape_type} available[/green]")
                    
                    if actual_max < remaining_to_scrape and scrape_type != 'posts':
                        console.print(f"[dim]   Adjusting target: {actual_max:,} (instead of {remaining_to_scrape:,})[/dim]")
                
                targets_info.append({
                    'username': target,
                    'available': available_count,
                    'to_scrape': actual_max
                })
            else:
                self.logger.warning(f"Could not get profile info for @{target}")
                actual_max = remaining_to_scrape
                available_count = actual_max  # Unknown, use requested
            
            # Handle posts scraping differently
            if scrape_type == 'posts':
                console.print(f"[cyan]📍 Opening first post of @{target}...[/cyan]")
                profiles_from_target = self._scrape_post_likers_commenters(
                    target_username=target,
                    max_count=actual_max,
                    scrape_likers=scrape_post_likers,
                    scrape_commenters=scrape_post_commenters
                )
                total_scraped += len(profiles_from_target)
                console.print(f"[green]✅ Scraped {len(profiles_from_target):,} profiles from @{target}'s post[/green]")
                continue
            
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
