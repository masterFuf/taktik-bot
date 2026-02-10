"""
Instagram Discovery Workflow

Intelligent prospect discovery workflow that:
1. Collects profiles from hashtags, competitor accounts, and post URLs
2. Tracks engagement (likes, comments) across multiple sources
3. Enriches profiles with bio, website, stats
4. Scores profiles using AI based on niche relevance and business signals
5. Generates personalized personas and DM templates
"""

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
from taktik.core.social_media.instagram.actions.atomic.detection_actions import DetectionActions
from taktik.core.social_media.instagram.actions.atomic.scroll_actions import ScrollActions
from taktik.core.social_media.instagram.actions.business.management.profile import ProfileBusiness
from taktik.core.social_media.instagram.ui.detectors.scroll_end import ScrollEndDetector
from taktik.core.social_media.instagram.ui.extractors import InstagramUIExtractors
from taktik.core.social_media.instagram.ui.selectors import DETECTION_SELECTORS, POST_SELECTORS
from taktik.core.database.local.service import get_local_database


console = Console()


@dataclass
class DiscoveredProfile:
    """Represents a discovered profile with engagement data."""
    username: str
    profile_id: Optional[int] = None
    
    # Engagement tracking
    interactions: List[Dict[str, Any]] = field(default_factory=list)
    total_likes: int = 0
    total_comments: int = 0
    comment_contents: List[str] = field(default_factory=list)
    sources: Set[str] = field(default_factory=set)
    
    # Profile data (after enrichment)
    bio: Optional[str] = None
    website: Optional[str] = None
    followers_count: int = 0
    following_count: int = 0
    posts_count: int = 0
    is_business: bool = False
    category: Optional[str] = None
    is_private: bool = False
    
    # AI scoring
    ai_score: Optional[int] = None
    score_breakdown: Optional[Dict[str, int]] = None
    
    # AI persona
    persona: Optional[Dict[str, Any]] = None
    dm_templates: Optional[List[Dict[str, str]]] = None
    
    discovered_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def add_interaction(self, interaction_type: str, source_type: str, source_name: str, 
                       post_id: Optional[str] = None, comment_content: Optional[str] = None):
        """Add an interaction to this profile."""
        self.interactions.append({
            'type': interaction_type,
            'source_type': source_type,
            'source_name': source_name,
            'post_id': post_id,
            'comment_content': comment_content,
            'detected_at': datetime.now().isoformat()
        })
        
        if interaction_type == 'LIKE':
            self.total_likes += 1
        elif interaction_type == 'COMMENT':
            self.total_comments += 1
            if comment_content:
                self.comment_contents.append(comment_content)
        
        self.sources.add(f"{source_type}:{source_name}")
    
    @property
    def engagement_score(self) -> int:
        """Calculate raw engagement score."""
        # Comments are worth more than likes
        return self.total_likes + (self.total_comments * 3) + (len(self.sources) * 5)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['sources'] = list(self.sources)
        return data


class DiscoveryWorkflow:
    """
    Workflow for intelligent prospect discovery.
    
    Supports:
    - Hashtag discovery: Find engaged users on hashtag posts
    - Account discovery: Find engaged users on competitor posts
    - Post URL discovery: Find likers/commenters on specific posts
    - Multi-source tracking: Track users seen across multiple sources
    - AI scoring and persona generation
    """
    
    def __init__(self, device_manager: DeviceManager, config: Dict[str, Any]):
        """
        Initialize the discovery workflow.
        
        Args:
            device_manager: Connected device manager
            config: Discovery configuration
        """
        self.device_manager = device_manager
        self.device = device_manager.device
        self.config = config
        self.logger = logger.bind(module="discovery-workflow")
        
        # Initialize actions
        self.nav_actions = NavigationActions(self.device)
        self.detection_actions = DetectionActions(self.device)
        self.scroll_actions = ScrollActions(self.device)
        self.profile_manager = ProfileBusiness(self.device)
        self.ui_extractors = InstagramUIExtractors(self.device)
        
        # Discovery state
        self.discovered_profiles: Dict[str, DiscoveredProfile] = {}  # username -> profile
        self.campaign_id: Optional[int] = None
        self.start_time: Optional[datetime] = None
        
        # Config
        self.session_duration_minutes = config.get('session_duration_minutes', 60)
        self.max_profiles = config.get('max_profiles', 500)
        self.enrich_profiles = config.get('enrich_profiles', True)
        self.score_profiles = config.get('score_profiles', True)
        self.niche_keywords = config.get('niche_keywords', [])
        self.min_score_threshold = config.get('min_score_threshold', 60)
        
        # Database
        self.db = get_local_database()
    
    def run(self) -> Dict[str, Any]:
        """
        Execute the discovery workflow.
        
        Returns:
            Dict with discovery results
        """
        self.start_time = datetime.now()
        
        console.print("\n[bold blue]🔍 Starting Discovery Workflow...[/bold blue]\n")
        
        # Create campaign in database
        self._create_campaign()
        
        try:
            # Phase 1: Collect profiles from all sources
            console.print("[bold cyan]📥 Phase 1: Collecting profiles...[/bold cyan]")
            self._collect_phase()
            
            # Phase 2: Deduplicate and merge
            console.print(f"\n[bold cyan]🔄 Phase 2: Deduplicating {len(self.discovered_profiles)} profiles...[/bold cyan]")
            # Already deduplicated by using dict with username as key
            
            # Phase 3: Enrich profiles
            if self.enrich_profiles:
                console.print(f"\n[bold cyan]📊 Phase 3: Enriching profiles...[/bold cyan]")
                self._enrich_phase()
            
            # Phase 4: Score profiles with AI
            if self.score_profiles:
                console.print(f"\n[bold cyan]🤖 Phase 4: AI Scoring...[/bold cyan]")
                self._score_phase()
            
            # Phase 5: Save to database
            console.print(f"\n[bold cyan]💾 Phase 5: Saving to database...[/bold cyan]")
            self._save_to_database()
            
            # Display results
            self._display_results()
            
            # Update campaign stats
            self._update_campaign_stats()
            
            return {
                "success": True,
                "campaign_id": self.campaign_id,
                "total_discovered": len(self.discovered_profiles),
                "qualified_count": sum(1 for p in self.discovered_profiles.values() 
                                      if p.ai_score and p.ai_score >= self.min_score_threshold),
                "duration_seconds": (datetime.now() - self.start_time).total_seconds()
            }
            
        except Exception as e:
            self.logger.error(f"Discovery error: {e}")
            console.print(f"[red]❌ Discovery error: {e}[/red]")
            return {"success": False, "error": str(e)}
    
    def _should_continue(self) -> bool:
        """Check if discovery should continue based on time and profile limits."""
        if not self.start_time:
            return True
        
        elapsed = (datetime.now() - self.start_time).total_seconds() / 60
        if elapsed >= self.session_duration_minutes:
            return False
        
        if len(self.discovered_profiles) >= self.max_profiles:
            return False
        
        return True
    
    def _create_campaign(self):
        """Create a discovery campaign in the database."""
        try:
            campaign_name = self.config.get('campaign_name', f"Discovery {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            account_id = self.config.get('account_id', 1)
            
            self.db.execute("""
                INSERT INTO discovery_campaigns (
                    account_id, name, description, niche_keywords,
                    target_hashtags, target_accounts, target_post_urls,
                    min_score_threshold, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE')
            """, (
                account_id,
                campaign_name,
                self.config.get('description', ''),
                json.dumps(self.niche_keywords),
                json.dumps(self.config.get('hashtags', [])),
                json.dumps(self.config.get('target_accounts', [])),
                json.dumps(self.config.get('post_urls', [])),
                self.min_score_threshold
            ))
            
            self.campaign_id = self.db.cursor.lastrowid
            self.logger.info(f"Created discovery campaign {self.campaign_id}: {campaign_name}")
            console.print(f"[green]✅ Campaign created: {campaign_name}[/green]")
            
        except Exception as e:
            self.logger.error(f"Error creating campaign: {e}")
    
    def _collect_phase(self):
        """Collect profiles from all configured sources."""
        
        # Collect from hashtags
        hashtags = self.config.get('hashtags', [])
        for hashtag in hashtags:
            if not self._should_continue():
                break
            self._collect_from_hashtag(hashtag)
        
        # Collect from target accounts
        target_accounts = self.config.get('target_accounts', [])
        for account in target_accounts:
            if not self._should_continue():
                break
            self._collect_from_account(account)
        
        # Collect from specific post URLs
        post_urls = self.config.get('post_urls', [])
        for url in post_urls:
            if not self._should_continue():
                break
            self._collect_from_post_url(url)
    
    def _collect_from_hashtag(self, hashtag: str):
        """Collect profiles from a hashtag's posts."""
        hashtag = hashtag.lstrip('#')
        console.print(f"\n[cyan]#️⃣ Collecting from #{hashtag}...[/cyan]")
        
        # Navigate to hashtag
        if not self.nav_actions.navigate_to_hashtag(hashtag):
            self.logger.warning(f"Failed to navigate to #{hashtag}")
            return
        
        time.sleep(2)
        
        max_posts = self.config.get('max_posts_per_source', 10)
        posts_checked = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task(f"[cyan]#{hashtag}", total=max_posts)
            
            while posts_checked < max_posts and self._should_continue():
                # Click on a post
                if not self._click_next_post(posts_checked):
                    self.logger.info("No more posts to check")
                    break
                
                posts_checked += 1
                time.sleep(1.5)
                
                # Get post author
                author = self._get_post_author()
                if author:
                    self._add_discovered_profile(author, 'LIKE', 'hashtag', f"#{hashtag}")
                
                # Scrape likers
                likers = self._scrape_post_likers(max_count=20)
                for liker in likers:
                    self._add_discovered_profile(liker, 'LIKE', 'hashtag', f"#{hashtag}")
                
                # Scrape commenters with their comments
                commenters = self._scrape_post_commenters(max_count=10)
                for commenter in commenters:
                    self._add_discovered_profile(
                        commenter['username'], 
                        'COMMENT', 
                        'hashtag', 
                        f"#{hashtag}",
                        comment_content=commenter.get('content')
                    )
                
                progress.update(task, advance=1)
                
                # Go back to hashtag grid
                self.device.press("back")
                time.sleep(1)
        
        console.print(f"[green]✅ #{hashtag}: {posts_checked} posts checked[/green]")
    
    def _collect_from_account(self, account: str):
        """Collect profiles from a target account's posts."""
        account = account.lstrip('@')
        console.print(f"\n[cyan]👤 Collecting from @{account}...[/cyan]")
        
        # Navigate to account
        if not self.nav_actions.navigate_to_profile(account):
            self.logger.warning(f"Failed to navigate to @{account}")
            return
        
        time.sleep(2)
        
        max_posts = self.config.get('max_posts_per_source', 5)
        posts_checked = 0
        
        # Open first post
        if not self._open_first_post_of_profile():
            self.logger.warning(f"Could not open posts for @{account}")
            return
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task(f"[cyan]@{account}", total=max_posts)
            
            while posts_checked < max_posts and self._should_continue():
                posts_checked += 1
                
                # Scrape likers
                likers = self._scrape_post_likers(max_count=30)
                for liker in likers:
                    if liker != account:  # Don't add the account owner
                        self._add_discovered_profile(liker, 'LIKE', 'account', f"@{account}")
                
                # Scrape commenters
                commenters = self._scrape_post_commenters(max_count=15)
                for commenter in commenters:
                    if commenter['username'] != account:
                        self._add_discovered_profile(
                            commenter['username'],
                            'COMMENT',
                            'account',
                            f"@{account}",
                            comment_content=commenter.get('content')
                        )
                
                progress.update(task, advance=1)
                
                # Swipe to next post
                if posts_checked < max_posts:
                    self.scroll_actions.scroll_down()
                    time.sleep(1.5)
        
        # Go back
        self.device.press("back")
        time.sleep(1)
        
        console.print(f"[green]✅ @{account}: {posts_checked} posts checked[/green]")
    
    def _collect_from_post_url(self, post_url: str):
        """Collect profiles from a specific post URL."""
        console.print(f"\n[cyan]🔗 Collecting from post URL...[/cyan]")
        
        # Navigate to post
        if not self.nav_actions.navigate_to_post_url(post_url):
            self.logger.warning(f"Failed to navigate to post: {post_url}")
            return
        
        time.sleep(2)
        
        # Scrape likers
        likers = self._scrape_post_likers(max_count=50)
        for liker in likers:
            self._add_discovered_profile(liker, 'LIKE', 'post_url', post_url)
        
        # Scrape commenters
        commenters = self._scrape_post_commenters(max_count=30)
        for commenter in commenters:
            self._add_discovered_profile(
                commenter['username'],
                'COMMENT',
                'post_url',
                post_url,
                comment_content=commenter.get('content')
            )
        
        console.print(f"[green]✅ Post URL: {len(likers)} likers, {len(commenters)} commenters[/green]")
    
    def _add_discovered_profile(self, username: str, interaction_type: str, 
                                source_type: str, source_name: str,
                                post_id: Optional[str] = None,
                                comment_content: Optional[str] = None):
        """Add or update a discovered profile."""
        if not username:
            return
        
        username = username.strip().lstrip('@')
        
        if username not in self.discovered_profiles:
            self.discovered_profiles[username] = DiscoveredProfile(username=username)
        
        self.discovered_profiles[username].add_interaction(
            interaction_type=interaction_type,
            source_type=source_type,
            source_name=source_name,
            post_id=post_id,
            comment_content=comment_content
        )
    
    def _enrich_phase(self):
        """Enrich discovered profiles with full profile data."""
        # Sort by engagement score to prioritize most engaged profiles
        sorted_profiles = sorted(
            self.discovered_profiles.values(),
            key=lambda p: p.engagement_score,
            reverse=True
        )
        
        max_to_enrich = self.config.get('max_profiles_to_enrich', 100)
        enriched_count = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Enriching profiles...", total=min(len(sorted_profiles), max_to_enrich))
            
            for profile in sorted_profiles[:max_to_enrich]:
                if not self._should_continue():
                    break
                
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
                            profile.is_business = info.get('is_business', False)
                            profile.category = info.get('category', '')
                            profile.is_private = info.get('is_private', False)
                            
                            enriched_count += 1
                        
                        # Go back
                        self.device.press("back")
                        time.sleep(0.5)
                    
                except Exception as e:
                    self.logger.warning(f"Error enriching @{profile.username}: {e}")
                
                progress.update(task, advance=1)
        
        console.print(f"[green]✅ Enriched {enriched_count} profiles[/green]")
    
    def _score_phase(self):
        """Score profiles using AI."""
        # Only score enriched profiles
        profiles_to_score = [
            p for p in self.discovered_profiles.values()
            if p.bio is not None  # Has been enriched
        ]
        
        console.print(f"[dim]Scoring {len(profiles_to_score)} enriched profiles...[/dim]")
        
        for profile in profiles_to_score:
            score, breakdown = self._calculate_score(profile)
            profile.ai_score = score
            profile.score_breakdown = breakdown
            
            # Generate persona for qualified profiles
            if score >= self.min_score_threshold:
                profile.persona = self._generate_persona(profile)
                profile.dm_templates = self._generate_dm_templates(profile)
        
        qualified_count = sum(1 for p in profiles_to_score if p.ai_score and p.ai_score >= self.min_score_threshold)
        console.print(f"[green]✅ {qualified_count} profiles qualified (score >= {self.min_score_threshold})[/green]")
    
    def _calculate_score(self, profile: DiscoveredProfile) -> tuple[int, Dict[str, int]]:
        """
        Calculate a score for the profile based on multiple criteria.
        
        Returns:
            Tuple of (total_score, breakdown_dict)
        """
        breakdown = {}
        
        # 1. Business Signal (25%)
        business_score = 0
        if profile.website:
            business_score += 40
        if profile.bio:
            bio_lower = profile.bio.lower()
            business_keywords = ['dm', 'collab', 'business', 'brand', 'shop', 'store', 'link', 
                               'email', 'booking', 'order', 'service', 'agency', 'founder', 'ceo']
            for kw in business_keywords:
                if kw in bio_lower:
                    business_score += 10
        if profile.is_business:
            business_score += 20
        breakdown['business_signal'] = min(business_score, 100)
        
        # 2. Engagement Quality (20%)
        engagement_score = 0
        if profile.total_comments > 0:
            engagement_score += 50  # Commenting is high-intent
        engagement_score += min(profile.total_likes * 5, 30)
        engagement_score += min(len(profile.sources) * 10, 20)  # Multi-source bonus
        breakdown['engagement'] = min(engagement_score, 100)
        
        # 3. Profile Completeness (15%)
        completeness_score = 0
        if profile.bio and len(profile.bio) > 20:
            completeness_score += 30
        if profile.posts_count > 10:
            completeness_score += 30
        if profile.followers_count > 100:
            completeness_score += 20
        if not profile.is_private:
            completeness_score += 20
        breakdown['completeness'] = min(completeness_score, 100)
        
        # 4. Niche Relevance (25%)
        relevance_score = 0
        if profile.bio and self.niche_keywords:
            bio_lower = profile.bio.lower()
            for keyword in self.niche_keywords:
                if keyword.lower() in bio_lower:
                    relevance_score += 25
        # Check comments for relevance
        for comment in profile.comment_contents:
            comment_lower = comment.lower()
            for keyword in self.niche_keywords:
                if keyword.lower() in comment_lower:
                    relevance_score += 10
        breakdown['niche_relevance'] = min(relevance_score, 100)
        
        # 5. Follower Ratio (15%)
        ratio_score = 50  # Default
        if profile.following_count > 0:
            ratio = profile.followers_count / profile.following_count
            if ratio > 2:
                ratio_score = 100  # Good ratio
            elif ratio > 1:
                ratio_score = 75
            elif ratio > 0.5:
                ratio_score = 50
            else:
                ratio_score = 25  # Might be a bot or mass follower
        breakdown['follower_ratio'] = ratio_score
        
        # Calculate weighted total
        weights = {
            'business_signal': 0.25,
            'engagement': 0.20,
            'completeness': 0.15,
            'niche_relevance': 0.25,
            'follower_ratio': 0.15
        }
        
        total_score = sum(breakdown[k] * weights[k] for k in weights)
        
        return int(total_score), breakdown
    
    def _generate_persona(self, profile: DiscoveredProfile) -> Dict[str, Any]:
        """Generate a persona for the profile based on available data."""
        persona = {
            'interests': [],
            'pain_points': [],
            'communication_style': 'professional',
            'best_approach': '',
            'ice_breaker': ''
        }
        
        # Extract interests from bio
        if profile.bio:
            bio_lower = profile.bio.lower()
            
            interest_keywords = {
                'growth': ['growth', 'grow', 'scale', 'scaling'],
                'marketing': ['marketing', 'marketer', 'ads', 'advertising'],
                'content': ['content', 'creator', 'influencer', 'ugc'],
                'ecommerce': ['shop', 'store', 'ecommerce', 'dropship'],
                'coaching': ['coach', 'mentor', 'consulting', 'consultant'],
                'fitness': ['fitness', 'gym', 'workout', 'health'],
                'food': ['food', 'chef', 'restaurant', 'recipe'],
                'travel': ['travel', 'nomad', 'adventure'],
                'tech': ['tech', 'developer', 'startup', 'saas'],
                'fashion': ['fashion', 'style', 'clothing', 'boutique']
            }
            
            for interest, keywords in interest_keywords.items():
                if any(kw in bio_lower for kw in keywords):
                    persona['interests'].append(interest)
        
        # Infer pain points based on interests
        pain_point_map = {
            'growth': 'Needs to scale engagement efficiently',
            'marketing': 'Looking for better ROI on social efforts',
            'content': 'Wants to grow audience faster',
            'ecommerce': 'Needs more traffic and sales',
            'coaching': 'Wants to attract more clients'
        }
        
        for interest in persona['interests']:
            if interest in pain_point_map:
                persona['pain_points'].append(pain_point_map[interest])
        
        # Determine communication style
        if profile.is_business or profile.category:
            persona['communication_style'] = 'professional'
        elif any(emoji in (profile.bio or '') for emoji in ['😂', '🔥', '💯', '😎']):
            persona['communication_style'] = 'casual'
        
        # Generate approach suggestion
        if profile.total_comments > 0:
            persona['best_approach'] = 'Reference their engagement - they are active commenters'
        elif len(profile.sources) > 1:
            persona['best_approach'] = 'Mention shared interests - seen in multiple relevant places'
        else:
            persona['best_approach'] = 'Lead with value proposition'
        
        # Generate ice breaker
        if persona['interests']:
            persona['ice_breaker'] = f"I noticed you're into {persona['interests'][0]} - me too!"
        elif profile.bio:
            persona['ice_breaker'] = "Love your profile! Quick question..."
        
        return persona
    
    def _generate_dm_templates(self, profile: DiscoveredProfile) -> List[Dict[str, str]]:
        """Generate personalized DM templates for the profile."""
        templates = []
        
        # Template 1: Direct approach
        direct_msg = "Hey! "
        if profile.persona and profile.persona.get('interests'):
            direct_msg += f"I see you're into {profile.persona['interests'][0]}. "
        direct_msg += "I built something that might help you grow faster. Mind if I share?"
        
        templates.append({
            'style': 'direct',
            'message': direct_msg
        })
        
        # Template 2: Value-first approach
        value_msg = "Hey "
        if profile.bio and 'founder' in profile.bio.lower():
            value_msg += "fellow founder! "
        else:
            value_msg += "there! "
        value_msg += "I've been helping accounts like yours grow 3x faster. Would love to show you how - no strings attached."
        
        templates.append({
            'style': 'value_first',
            'message': value_msg
        })
        
        # Template 3: Curiosity approach
        curiosity_msg = "Quick question - how do you currently handle engagement? "
        curiosity_msg += "I might have something that could save you hours."
        
        templates.append({
            'style': 'curiosity',
            'message': curiosity_msg
        })
        
        return templates
    
    def _save_to_database(self):
        """Save all discovered profiles to the database."""
        if not self.campaign_id:
            self.logger.warning("No campaign ID, skipping database save")
            return
        
        saved_count = 0
        
        for profile in self.discovered_profiles.values():
            try:
                # First, ensure profile exists in instagram_profiles
                existing = self.db.execute(
                    "SELECT profile_id FROM instagram_profiles WHERE username = ?",
                    (profile.username,)
                ).fetchone()
                
                if existing:
                    profile_id = existing[0]
                    # Update with enriched data if available
                    if profile.bio is not None:
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
                            profile_id
                        ))
                else:
                    # Insert new profile
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
                    profile_id = self.db.cursor.lastrowid
                
                profile.profile_id = profile_id
                
                # Get first source for discovery_source
                first_source = list(profile.sources)[0] if profile.sources else 'unknown:unknown'
                source_type, source_name = first_source.split(':', 1) if ':' in first_source else ('unknown', first_source)
                
                # Insert into discovered_profiles
                self.db.execute("""
                    INSERT OR REPLACE INTO discovered_profiles (
                        campaign_id, profile_id, discovery_source, source_name,
                        total_interactions, like_count, comment_count, unique_sources,
                        ai_score, score_breakdown, ai_persona, dm_templates, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.campaign_id,
                    profile_id,
                    source_type,
                    source_name,
                    len(profile.interactions),
                    profile.total_likes,
                    profile.total_comments,
                    len(profile.sources),
                    profile.ai_score,
                    json.dumps(profile.score_breakdown) if profile.score_breakdown else None,
                    json.dumps(profile.persona) if profile.persona else None,
                    json.dumps(profile.dm_templates) if profile.dm_templates else None,
                    'QUALIFIED' if profile.ai_score and profile.ai_score >= self.min_score_threshold else 'NEW'
                ))
                
                discovered_profile_id = self.db.cursor.lastrowid
                
                # Save interactions
                for interaction in profile.interactions:
                    self.db.execute("""
                        INSERT INTO discovery_interactions (
                            discovered_profile_id, interaction_type, source_type,
                            source_name, comment_content, detected_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        discovered_profile_id,
                        interaction['type'],
                        interaction['source_type'],
                        interaction['source_name'],
                        interaction.get('comment_content'),
                        interaction['detected_at']
                    ))
                
                saved_count += 1
                
            except Exception as e:
                self.logger.warning(f"Error saving profile @{profile.username}: {e}")
        
        self.db.commit()
        console.print(f"[green]✅ Saved {saved_count} profiles to database[/green]")
    
    def _update_campaign_stats(self):
        """Update campaign statistics."""
        if not self.campaign_id:
            return
        
        qualified_count = sum(
            1 for p in self.discovered_profiles.values()
            if p.ai_score and p.ai_score >= self.min_score_threshold
        )
        
        try:
            self.db.execute("""
                UPDATE discovery_campaigns SET
                    total_discovered = ?,
                    total_qualified = ?,
                    status = 'COMPLETED',
                    updated_at = datetime('now')
                WHERE campaign_id = ?
            """, (len(self.discovered_profiles), qualified_count, self.campaign_id))
            self.db.commit()
        except Exception as e:
            self.logger.error(f"Error updating campaign stats: {e}")
    
    def _display_results(self):
        """Display discovery results in a nice table."""
        # Sort by score
        sorted_profiles = sorted(
            [p for p in self.discovered_profiles.values() if p.ai_score is not None],
            key=lambda p: p.ai_score or 0,
            reverse=True
        )
        
        if not sorted_profiles:
            console.print("[yellow]No scored profiles to display[/yellow]")
            return
        
        table = Table(title="🎯 Top Discovered Profiles")
        table.add_column("Username", style="cyan")
        table.add_column("Score", justify="center")
        table.add_column("Engagement", justify="center")
        table.add_column("Followers", justify="right")
        table.add_column("Sources", justify="center")
        table.add_column("Status", justify="center")
        
        for profile in sorted_profiles[:20]:
            score_color = "green" if profile.ai_score >= 70 else "yellow" if profile.ai_score >= 50 else "red"
            status = "✅ Qualified" if profile.ai_score >= self.min_score_threshold else "⏳ Review"
            
            table.add_row(
                f"@{profile.username}",
                f"[{score_color}]{profile.ai_score}[/{score_color}]",
                f"❤️{profile.total_likes} 💬{profile.total_comments}",
                f"{profile.followers_count:,}" if profile.followers_count else "-",
                str(len(profile.sources)),
                status
            )
        
        console.print(table)
        
        # Summary
        total = len(self.discovered_profiles)
        qualified = sum(1 for p in self.discovered_profiles.values() 
                       if p.ai_score and p.ai_score >= self.min_score_threshold)
        
        console.print(f"\n[bold]📊 Summary:[/bold]")
        console.print(f"   Total discovered: {total}")
        console.print(f"   Qualified (score >= {self.min_score_threshold}): {qualified}")
        console.print(f"   Conversion rate: {qualified/total*100:.1f}%" if total > 0 else "   Conversion rate: 0%")
    
    # ==========================================
    # Helper methods for scraping
    # ==========================================
    
    def _click_next_post(self, index: int = 0) -> bool:
        """Click on the next post in a grid."""
        try:
            posts = self.device.xpath(DETECTION_SELECTORS.post_thumbnail_selectors[0]).all()
            if not posts:
                posts = self.device.xpath('//*[@resource-id="com.instagram.android:id/image_button"]').all()
            
            if index < len(posts):
                posts[index].click()
                time.sleep(2)
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error clicking post: {e}")
            return False
    
    def _open_first_post_of_profile(self) -> bool:
        """Open the first post of the current profile."""
        try:
            posts = self.device.xpath(DETECTION_SELECTORS.post_thumbnail_selectors[0]).all()
            if not posts:
                posts = self.device.xpath('//*[@resource-id="com.instagram.android:id/image_button"]').all()
            
            if posts:
                posts[0].click()
                time.sleep(2)
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error opening first post: {e}")
            return False
    
    def _get_post_author(self) -> Optional[str]:
        """Get the author username of the current post."""
        try:
            author_selectors = [
                '//*[@resource-id="com.instagram.android:id/row_feed_photo_profile_name"]',
                '//android.widget.TextView[@resource-id="com.instagram.android:id/row_feed_photo_profile_name"]',
            ]
            
            for selector in author_selectors:
                element = self.device.xpath(selector)
                if element.exists:
                    return element.get_text().strip().lstrip('@')
            
            return None
        except Exception as e:
            self.logger.error(f"Error getting post author: {e}")
            return None
    
    def _scrape_post_likers(self, max_count: int = 20) -> List[str]:
        """Scrape likers from the current post."""
        likers = []
        
        try:
            # Try to open likers list
            liked_by_selectors = [
                '//*[starts-with(@text, "Liked by")]',
                '//*[starts-with(@text, "Aimé par")]',
                '//*[contains(@text, " likes")]',
                '//*[contains(@text, " like")]',
                '//*[@resource-id="com.instagram.android:id/row_feed_textview_likes"]',
            ]
            
            likers_opened = False
            for selector in liked_by_selectors:
                element = self.device.xpath(selector)
                if element.exists:
                    element.click()
                    time.sleep(2)
                    likers_opened = True
                    break
            
            if not likers_opened:
                return likers
            
            # Extract usernames from likers list
            seen = set()
            scroll_attempts = 0
            
            while len(likers) < max_count and scroll_attempts < 5:
                username_elements = self.device.xpath(
                    '//android.widget.TextView[@resource-id="com.instagram.android:id/row_user_primary_name"]'
                ).all()
                
                found_new = False
                for elem in username_elements:
                    try:
                        username = elem.get_text().strip().lstrip('@')
                        if username and username not in seen:
                            seen.add(username)
                            likers.append(username)
                            found_new = True
                            if len(likers) >= max_count:
                                break
                    except:
                        continue
                
                if not found_new:
                    scroll_attempts += 1
                
                if len(likers) < max_count:
                    self.scroll_actions.scroll_down()
                    time.sleep(0.5)
            
            # Go back
            self.device.press("back")
            time.sleep(1)
            
        except Exception as e:
            self.logger.error(f"Error scraping likers: {e}")
        
        return likers
    
    def _scrape_post_commenters(self, max_count: int = 10) -> List[Dict[str, str]]:
        """Scrape commenters and their comments from the current post."""
        commenters = []
        
        try:
            # Click comment button
            comment_selectors = [
                '//*[@resource-id="com.instagram.android:id/row_feed_button_comment"]',
                '//*[@content-desc="Comment"]',
            ]
            
            comments_opened = False
            for selector in comment_selectors:
                element = self.device.xpath(selector)
                if element.exists:
                    element.click()
                    time.sleep(2)
                    comments_opened = True
                    break
            
            if not comments_opened:
                return commenters
            
            # Extract comments
            seen = set()
            scroll_attempts = 0
            
            while len(commenters) < max_count and scroll_attempts < 3:
                # Find comment containers
                comment_containers = self.device.xpath(
                    '//*[@resource-id="com.instagram.android:id/row_comment_textview_comment_container"]'
                ).all()
                
                found_new = False
                for container in comment_containers:
                    try:
                        # Get username from button inside container
                        username_btn = container.xpath('.//android.widget.Button').get()
                        if username_btn:
                            username = username_btn.attrib.get('content-desc', '').strip().lstrip('@')
                            
                            if username and username not in seen:
                                seen.add(username)
                                
                                # Try to get comment text
                                comment_text = ''
                                text_views = container.xpath('.//android.widget.TextView').all()
                                for tv in text_views:
                                    text = tv.get_text() if hasattr(tv, 'get_text') else ''
                                    if text and text != username:
                                        comment_text = text
                                        break
                                
                                commenters.append({
                                    'username': username,
                                    'content': comment_text
                                })
                                found_new = True
                                
                                if len(commenters) >= max_count:
                                    break
                    except:
                        continue
                
                if not found_new:
                    scroll_attempts += 1
                
                if len(commenters) < max_count:
                    self.scroll_actions.scroll_down()
                    time.sleep(0.5)
            
            # Go back
            self.device.press("back")
            time.sleep(1)
            
        except Exception as e:
            self.logger.error(f"Error scraping commenters: {e}")
        
        return commenters
