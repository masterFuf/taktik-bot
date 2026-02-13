"""Persistence, export, enrichment, stats, and session management for the Scraping workflow."""

import csv
import os
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from taktik.core.database.local.service import get_local_database
from taktik.core.social_media.instagram.ui.selectors import PROFILE_SELECTORS

console = Console()


class ScrapingPersistenceMixin:
    """Mixin: CSV export, DB save, session management, enrichment, stats display."""

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
                         'is_private', 'biography', 'date_joined', 'account_based_in',
                         'source_type', 'source_name', 'scraped_at']
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

    def _save_profile_immediately(self, profile: Dict[str, Any]) -> bool:
        """Save a single profile to database immediately as it's scraped."""
        if not self._save_immediately:
            return False
            
        try:
            local_db = get_local_database()
            username = profile['username']
            
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
            
            result = local_db.save_profile(profile_data)
            
            # Link profile to scraping session in junction table
            if self.scraping_session_id and result and result.get('profile_id'):
                local_db.link_profile_to_session(self.scraping_session_id, result['profile_id'])
            
            # Update session count in database
            if self.scraping_session_id:
                local_db.update_scraping_session_count(self.scraping_session_id, len(self.scraped_profiles))
            
            return True
        except Exception as e:
            self.logger.debug(f"Error saving @{profile.get('username', 'unknown')} immediately: {e}")
            return False

    def _save_to_database(self):
        """Save scraped profiles to local database (final save, handles any missed profiles)."""
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
                        # Link profile to scraping session in junction table
                        if self.scraping_session_id and result.get('profile_id'):
                            local_db.link_profile_to_session(self.scraping_session_id, result['profile_id'])
                        
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
