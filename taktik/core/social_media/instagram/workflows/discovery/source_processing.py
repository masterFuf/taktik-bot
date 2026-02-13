"""Source processing: targets, hashtags, and post URLs for the Discovery workflow."""

import time
from typing import Dict, Any
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .models import ScrapedProfile

console = Console()


class DiscoverySourceProcessingMixin:
    """Mixin: process target accounts, hashtags, and post URLs."""

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

    def _scrape_target_profile(self, username: str, progress) -> bool:
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
        
        # Note: navigate_to_hashtag() handles navigation to search screen internally
        # No need to navigate_to_home() first - same approach as HashtagBusiness workflow
        
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
