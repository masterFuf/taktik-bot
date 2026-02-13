"""Campaign, session, and progress management for the Discovery workflow."""

import json
import subprocess
import time
from datetime import datetime
from typing import Dict, Any, Optional
from rich.console import Console

from .models import ProgressState
from ..common.session import should_continue_session

console = Console()


class DiscoverySessionMixin:
    """Mixin: campaign/session creation, progress load/save, Instagram restart."""

    def _restart_instagram(self):
        """Force restart Instagram to ensure clean state.
        
        This is called at the beginning of each workflow to ensure
        Instagram starts from a known state (home feed).
        Uses deep link approach (like navigate_to_profile) which properly waits for app to load.
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
                
                # Relaunch Instagram using deep link to home feed (same approach as navigate_to_profile)
                # Using -W flag to wait for app to fully load, and VIEW intent to properly open Instagram
                self.logger.info("🚀 Relaunching Instagram...")
                launch_cmd = f'adb -s {device_serial} shell am start -W -a android.intent.action.VIEW -d "https://www.instagram.com/" com.instagram.android'
                result = subprocess.run(launch_cmd, shell=True, capture_output=True, text=True, timeout=15)
                self.logger.info(f"✅ Instagram relaunched: {result.stdout.strip() if result.stdout else 'OK'}")
                
                # Small additional wait for UI to stabilize
                time.sleep(2)
                console.print("[green]✅ Instagram restarted[/green]")
            else:
                self.logger.warning("⚠️ Could not get device serial, skipping restart")
                
        except Exception as e:
            self.logger.error(f"❌ Error restarting Instagram: {e}")
            # Try to continue anyway

    def _should_continue(self) -> bool:
        """Check if we should continue based on time limit."""
        return should_continue_session(self.start_time, self.session_duration_minutes)

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
