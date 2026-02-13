"""Post navigation helpers, enrichment, saving, and summary for the Discovery workflow."""

import re
import json
import time
from typing import Dict, Any, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from taktik.core.social_media.instagram.ui.selectors import DETECTION_SELECTORS, POST_SELECTORS
from .models import PostData

console = Console()


class DiscoveryHelpersMixin:
    """Mixin: post navigation, enrichment, saving results, summary."""

    def _open_first_post(self) -> bool:
        """Open the first post of a profile (same logic as ScrapingWorkflow)."""
        try:
            self.logger.info("Opening first post of profile...")
            console.print(f"[dim]📸 Looking for first post...[/dim]")
            
            # Use the same selector as ScrapingWorkflow
            posts = self.device.xpath(DETECTION_SELECTORS.post_thumbnail_selectors[0]).all()
            
            if not posts:
                # Try alternative selector
                posts = self.device.xpath(POST_SELECTORS.first_post_grid).all()
            
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
                posts = self.device.xpath(POST_SELECTORS.first_post_grid).all()
            
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
            author_elem = self.device.xpath(POST_SELECTORS.post_author_username_selectors[0])
            if author_elem.exists:
                author = author_elem.get_text() or ""
            
            # Stats from carousel
            carousel = self.device.xpath(POST_SELECTORS.carousel_indicators[2])
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
