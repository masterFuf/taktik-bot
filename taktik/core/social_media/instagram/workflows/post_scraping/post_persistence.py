"""Profile enrichment, database persistence, and summary for the Post Scraping workflow."""

import time
from typing import Dict, Any, List
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from .post_scraping_models import ScrapedProfile

console = Console()


class PostPersistenceMixin:
    """Mixin: enrich profiles, save to DB, print summary."""

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
