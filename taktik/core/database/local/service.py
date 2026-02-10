"""
TAKTIK Local SQLite Database Service
Replaces API calls with local database operations for privacy
Uses Repository Pattern for clean data access
"""

import sqlite3
import os
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from loguru import logger

# Import repositories for new code
from ..repositories import (
    AccountRepository,
    ProfileRepository,
    InteractionRepository,
    SessionRepository,
    DiscoveryRepository,
    TikTokRepository
)


class LocalDatabaseService:
    """
    Local SQLite database service for storing Instagram automation data.
    Uses the same database as Electron app for shared access.
    Now includes Repository Pattern for cleaner code organization.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the database service.
        
        Args:
            db_path: Optional custom path to the database file.
                     If not provided, uses the standard APPDATA location.
        """
        if db_path:
            self.db_path = db_path
        else:
            # Use same location as Electron app
            appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
            self.db_path = os.path.join(appdata, 'taktik-desktop', 'taktik-data.db')
        
        self._connection: Optional[sqlite3.Connection] = None
        
        # Repositories (initialized after connection)
        self._accounts: Optional[AccountRepository] = None
        self._profiles: Optional[ProfileRepository] = None
        self._interactions: Optional[InteractionRepository] = None
        self._sessions: Optional[SessionRepository] = None
        self._discovery: Optional[DiscoveryRepository] = None
        self._tiktok: Optional[TikTokRepository] = None
        
        self._ensure_database()
    
    def _ensure_database(self) -> None:
        """Ensure database directory exists and create tables if needed."""
        db_dir = os.path.dirname(self.db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Created database directory: {db_dir}")
        
        # Initialize tables
        self._create_tables()
        # Run migrations for existing tables
        self._run_migrations()
        # Initialize repositories
        self._init_repositories()
        logger.info(f"✅ Local database initialized at: {self.db_path}")
    
    def _init_repositories(self) -> None:
        """Initialize all repositories with the database connection."""
        conn = self._get_connection()
        self._accounts = AccountRepository(conn)
        self._profiles = ProfileRepository(conn)
        self._interactions = InteractionRepository(conn)
        self._sessions = SessionRepository(conn)
        self._discovery = DiscoveryRepository(conn)
        self._tiktok = TikTokRepository(conn)
    
    # Repository accessors for new code
    @property
    def accounts(self) -> AccountRepository:
        """Access AccountRepository for instagram_accounts operations."""
        if not self._accounts:
            self._init_repositories()
        return self._accounts
    
    @property
    def profiles(self) -> ProfileRepository:
        """Access ProfileRepository for instagram_profiles operations."""
        if not self._profiles:
            self._init_repositories()
        return self._profiles
    
    @property
    def interactions(self) -> InteractionRepository:
        """Access InteractionRepository for interaction_history operations."""
        if not self._interactions:
            self._init_repositories()
        return self._interactions
    
    @property
    def sessions(self) -> SessionRepository:
        """Access SessionRepository for sessions operations."""
        if not self._sessions:
            self._init_repositories()
        return self._sessions
    
    @property
    def discovery(self) -> DiscoveryRepository:
        """Access DiscoveryRepository for discovery operations."""
        if not self._discovery:
            self._init_repositories()
        return self._discovery
    
    @property
    def tiktok(self) -> TikTokRepository:
        """Access TikTokRepository for TikTok operations."""
        if not self._tiktok:
            self._init_repositories()
        return self._tiktok
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get or create a database connection with WAL mode."""
        if self._connection is None:
            self._connection = sqlite3.connect(
                self.db_path,
                timeout=30.0,
                check_same_thread=False
            )
            self._connection.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrency with Electron
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA foreign_keys=ON")
        return self._connection
    
    def _create_tables(self) -> None:
        """Create all required tables if they don't exist."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Instagram Accounts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS instagram_accounts (
                account_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                is_bot INTEGER DEFAULT 1,
                user_id INTEGER,
                license_id INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        
        # Instagram Profiles
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS instagram_profiles (
                profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                full_name TEXT DEFAULT '',
                biography TEXT,
                followers_count INTEGER DEFAULT 0,
                following_count INTEGER DEFAULT 0,
                posts_count INTEGER DEFAULT 0,
                is_private INTEGER DEFAULT 0,
                is_verified INTEGER DEFAULT 0,
                is_business INTEGER DEFAULT 0,
                business_category TEXT,
                website TEXT,
                linked_accounts TEXT,
                profile_pic_path TEXT,
                notes TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        
        # Interaction History
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interaction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                account_id INTEGER NOT NULL,
                profile_id INTEGER NOT NULL,
                interaction_type TEXT NOT NULL,
                interaction_time TEXT DEFAULT (datetime('now')),
                success INTEGER DEFAULT 1,
                content TEXT,
                FOREIGN KEY (account_id) REFERENCES instagram_accounts(account_id) ON DELETE CASCADE,
                FOREIGN KEY (profile_id) REFERENCES instagram_profiles(profile_id) ON DELETE CASCADE
            )
        """)
        
        # Filtered Profiles
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS filtered_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                account_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                filtered_at TEXT DEFAULT (datetime('now')),
                reason TEXT,
                source_type TEXT DEFAULT 'GENERAL',
                source_name TEXT DEFAULT 'unknown',
                session_id INTEGER,
                FOREIGN KEY (profile_id) REFERENCES instagram_profiles(profile_id) ON DELETE CASCADE,
                FOREIGN KEY (account_id) REFERENCES instagram_accounts(account_id) ON DELETE CASCADE,
                UNIQUE(profile_id, account_id)
            )
        """)
        
        # Sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                session_name TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target TEXT NOT NULL,
                start_time TEXT DEFAULT (datetime('now')),
                end_time TEXT,
                duration_seconds INTEGER DEFAULT 0,
                config_used TEXT,
                status TEXT DEFAULT 'ACTIVE',
                error_message TEXT,
                synced_to_api INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (account_id) REFERENCES instagram_accounts(account_id) ON DELETE CASCADE
            )
        """)
        
        # Profile Stats History
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS profile_stats_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                followers_count INTEGER NOT NULL,
                following_count INTEGER NOT NULL,
                posts_count INTEGER NOT NULL,
                engagement_rate REAL,
                is_verified INTEGER,
                biography TEXT,
                external_url TEXT,
                profile_pic_url TEXT,
                recorded_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (profile_id) REFERENCES instagram_profiles(profile_id) ON DELETE CASCADE
            )
        """)
        
        # Instagram Posts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS instagram_posts (
                post_id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                account_id INTEGER,
                source TEXT DEFAULT 'SCRAPED',
                instagram_post_id TEXT UNIQUE,
                instagram_id TEXT,
                media_type TEXT NOT NULL,
                is_video INTEGER DEFAULT 0,
                caption TEXT,
                media_urls TEXT,
                thumbnail_url TEXT,
                video_url TEXT,
                likes_count INTEGER DEFAULT 0,
                comments_count INTEGER DEFAULT 0,
                views_count INTEGER DEFAULT 0,
                posted_at TEXT,
                scraped_at TEXT,
                hashtags TEXT,
                mentions TEXT,
                tagged_users TEXT,
                location TEXT,
                location_data TEXT,
                coauthors TEXT,
                status TEXT DEFAULT 'DRAFT',
                scheduled_for TEXT,
                published_at TEXT,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                dimensions TEXT,
                product_type TEXT,
                accessibility_caption TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (profile_id) REFERENCES instagram_profiles(profile_id) ON DELETE CASCADE,
                FOREIGN KEY (account_id) REFERENCES instagram_accounts(account_id) ON DELETE CASCADE
            )
        """)
        
        # Scraping Sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scraping_sessions (
                scraping_id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER,
                scraping_type TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_name TEXT NOT NULL,
                total_scraped INTEGER DEFAULT 0,
                max_profiles INTEGER DEFAULT 500,
                export_csv INTEGER DEFAULT 0,
                csv_path TEXT,
                save_to_db INTEGER DEFAULT 1,
                start_time TEXT DEFAULT (datetime('now')),
                end_time TEXT,
                duration_seconds INTEGER DEFAULT 0,
                status TEXT DEFAULT 'RUNNING',
                error_message TEXT,
                config_used TEXT,
                discovery_campaign_id INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (account_id) REFERENCES instagram_accounts(account_id) ON DELETE SET NULL,
                FOREIGN KEY (discovery_campaign_id) REFERENCES discovery_campaigns(campaign_id) ON DELETE SET NULL
            )
        """)
        
        # Processed Hashtag Posts (to avoid re-processing same posts)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_hashtag_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                hashtag TEXT NOT NULL,
                post_author TEXT NOT NULL,
                post_caption_hash TEXT,
                post_caption_preview TEXT,
                likes_count INTEGER,
                comments_count INTEGER,
                likers_processed INTEGER DEFAULT 0,
                interactions_made INTEGER DEFAULT 0,
                processed_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (account_id) REFERENCES instagram_accounts(account_id) ON DELETE CASCADE,
                UNIQUE(account_id, hashtag, post_author, post_caption_hash)
            )
        """)
        
        # Daily Stats (for API sync)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                total_likes INTEGER DEFAULT 0,
                total_follows INTEGER DEFAULT 0,
                total_unfollows INTEGER DEFAULT 0,
                total_comments INTEGER DEFAULT 0,
                total_story_views INTEGER DEFAULT 0,
                total_story_likes INTEGER DEFAULT 0,
                total_profile_visits INTEGER DEFAULT 0,
                total_sessions INTEGER DEFAULT 0,
                completed_sessions INTEGER DEFAULT 0,
                failed_sessions INTEGER DEFAULT 0,
                total_duration_seconds INTEGER DEFAULT 0,
                synced_to_api INTEGER DEFAULT 0,
                synced_at TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (account_id) REFERENCES instagram_accounts(account_id) ON DELETE CASCADE,
                UNIQUE(account_id, date)
            )
        """)
        
        # ============================================
        # TIKTOK TABLES
        # ============================================
        
        # TikTok Accounts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tiktok_accounts (
                account_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT,
                is_bot INTEGER DEFAULT 1,
                user_id INTEGER,
                license_id INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        
        # TikTok Profiles (users we interact with)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tiktok_profiles (
                profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT DEFAULT '',
                followers_count INTEGER DEFAULT 0,
                following_count INTEGER DEFAULT 0,
                likes_count INTEGER DEFAULT 0,
                videos_count INTEGER DEFAULT 0,
                is_private INTEGER DEFAULT 0,
                is_verified INTEGER DEFAULT 0,
                biography TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        
        # TikTok Interaction History
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tiktok_interaction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                account_id INTEGER NOT NULL,
                profile_id INTEGER NOT NULL,
                interaction_type TEXT NOT NULL,
                interaction_time TEXT DEFAULT (datetime('now')),
                success INTEGER DEFAULT 1,
                content TEXT,
                video_id TEXT,
                FOREIGN KEY (account_id) REFERENCES tiktok_accounts(account_id) ON DELETE CASCADE,
                FOREIGN KEY (profile_id) REFERENCES tiktok_profiles(profile_id) ON DELETE CASCADE
            )
        """)
        
        # TikTok Sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tiktok_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                session_name TEXT NOT NULL,
                workflow_type TEXT NOT NULL,
                target TEXT,
                start_time TEXT DEFAULT (datetime('now')),
                end_time TEXT,
                duration_seconds INTEGER DEFAULT 0,
                config_used TEXT,
                status TEXT DEFAULT 'ACTIVE',
                profiles_visited INTEGER DEFAULT 0,
                posts_watched INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                follows INTEGER DEFAULT 0,
                favorites INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                errors INTEGER DEFAULT 0,
                error_message TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (account_id) REFERENCES tiktok_accounts(account_id) ON DELETE CASCADE
            )
        """)
        
        # TikTok Filtered Profiles (profiles to skip)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tiktok_filtered_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                account_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                filtered_at TEXT DEFAULT (datetime('now')),
                reason TEXT,
                source_type TEXT DEFAULT 'GENERAL',
                source_name TEXT DEFAULT 'unknown',
                session_id INTEGER,
                FOREIGN KEY (profile_id) REFERENCES tiktok_profiles(profile_id) ON DELETE CASCADE,
                FOREIGN KEY (account_id) REFERENCES tiktok_accounts(account_id) ON DELETE CASCADE,
                UNIQUE(profile_id, account_id)
            )
        """)
        
        # TikTok Daily Stats
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tiktok_daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                total_likes INTEGER DEFAULT 0,
                total_follows INTEGER DEFAULT 0,
                total_favorites INTEGER DEFAULT 0,
                total_comments INTEGER DEFAULT 0,
                total_shares INTEGER DEFAULT 0,
                total_profile_visits INTEGER DEFAULT 0,
                total_posts_watched INTEGER DEFAULT 0,
                total_sessions INTEGER DEFAULT 0,
                completed_sessions INTEGER DEFAULT 0,
                failed_sessions INTEGER DEFAULT 0,
                total_duration_seconds INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (account_id) REFERENCES tiktok_accounts(account_id) ON DELETE CASCADE,
                UNIQUE(account_id, date)
            )
        """)
        
        # ============================================
        # DISCOVERY TABLES
        # ============================================
        
        # Discovery Campaigns
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discovery_campaigns (
                campaign_id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER,
                name TEXT NOT NULL,
                niche_keywords TEXT DEFAULT '[]',
                target_hashtags TEXT DEFAULT '[]',
                target_accounts TEXT DEFAULT '[]',
                target_post_urls TEXT DEFAULT '[]',
                total_discovered INTEGER DEFAULT 0,
                total_qualified INTEGER DEFAULT 0,
                status TEXT DEFAULT 'ACTIVE',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (account_id) REFERENCES instagram_accounts(account_id) ON DELETE SET NULL
            )
        """)
        
        # Discovery Progress (for resume capability)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discovery_progress (
                progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                source_type TEXT NOT NULL,
                source_value TEXT NOT NULL,
                current_post_index INTEGER DEFAULT 0,
                total_posts INTEGER DEFAULT 0,
                current_phase TEXT DEFAULT 'profile',
                likers_scraped INTEGER DEFAULT 0,
                likers_total INTEGER DEFAULT 0,
                comments_scraped INTEGER DEFAULT 0,
                comments_total INTEGER DEFAULT 0,
                last_scroll_position TEXT DEFAULT '{}',
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (campaign_id) REFERENCES discovery_campaigns(campaign_id) ON DELETE CASCADE,
                UNIQUE(campaign_id, source_type, source_value)
            )
        """)
        
        # Discovered Profiles
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discovered_profiles (
                profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                source_type TEXT,
                source_name TEXT,
                biography TEXT,
                followers_count INTEGER DEFAULT 0,
                following_count INTEGER DEFAULT 0,
                posts_count INTEGER DEFAULT 0,
                is_private INTEGER DEFAULT 0,
                is_verified INTEGER DEFAULT 0,
                is_business INTEGER DEFAULT 0,
                category TEXT,
                engagement_score REAL,
                ai_score REAL,
                status TEXT DEFAULT 'new',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (campaign_id) REFERENCES discovery_campaigns(campaign_id) ON DELETE CASCADE
            )
        """)
        
        # Scraped Profiles (junction table linking scraping sessions to profiles)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scraped_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scraping_id INTEGER NOT NULL,
                profile_id INTEGER NOT NULL,
                scraped_at TEXT DEFAULT (datetime('now')),
                ai_score INTEGER,
                ai_qualified INTEGER DEFAULT 0,
                ai_analysis TEXT,
                qualification_criteria TEXT,
                scored_at TEXT,
                FOREIGN KEY (scraping_id) REFERENCES scraping_sessions(scraping_id) ON DELETE CASCADE,
                FOREIGN KEY (profile_id) REFERENCES instagram_profiles(profile_id) ON DELETE CASCADE,
                UNIQUE(scraping_id, profile_id)
            )
        """)
        
        # Scraped Comments
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scraped_comments (
                comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                scraping_session_id INTEGER,
                profile_id INTEGER,
                target_username TEXT,
                post_url TEXT,
                username TEXT NOT NULL,
                content TEXT,
                likes_count INTEGER DEFAULT 0,
                is_reply INTEGER DEFAULT 0,
                parent_comment_id INTEGER,
                scraped_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (scraping_session_id) REFERENCES scraping_sessions(scraping_id) ON DELETE SET NULL,
                FOREIGN KEY (profile_id) REFERENCES instagram_profiles(profile_id) ON DELETE SET NULL
            )
        """)
        
        # Add index for scraped_comments (indexes created in _run_migrations after columns are added)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_accounts_username ON instagram_accounts(username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_profiles_username ON instagram_profiles(username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_interactions_session ON interaction_history(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_interactions_account ON interaction_history(account_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_interactions_time ON interaction_history(interaction_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_account ON sessions(account_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_filtered_account ON filtered_profiles(account_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_filtered_username ON filtered_profiles(username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_stats_account_date ON daily_stats(account_id, date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraping_sessions_status ON scraping_sessions(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraping_sessions_source ON scraping_sessions(source_type, source_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_processed_hashtag_posts_lookup ON processed_hashtag_posts(account_id, hashtag, post_author)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_profiles_session ON scraped_profiles(scraping_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_profiles_profile ON scraped_profiles(profile_id)")
        
        # TikTok indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tiktok_accounts_username ON tiktok_accounts(username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tiktok_profiles_username ON tiktok_profiles(username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tiktok_interactions_session ON tiktok_interaction_history(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tiktok_interactions_account ON tiktok_interaction_history(account_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tiktok_interactions_time ON tiktok_interaction_history(interaction_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tiktok_sessions_account ON tiktok_sessions(account_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tiktok_sessions_status ON tiktok_sessions(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tiktok_filtered_account ON tiktok_filtered_profiles(account_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tiktok_filtered_username ON tiktok_filtered_profiles(username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tiktok_daily_stats_account_date ON tiktok_daily_stats(account_id, date)")
        
        conn.commit()
    
    def _run_migrations(self) -> None:
        """Run migrations to add missing columns to existing tables."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Migration: Add missing columns to scraped_comments table
        try:
            cursor.execute("SELECT scraping_session_id FROM scraped_comments LIMIT 1")
        except sqlite3.OperationalError:
            # Column doesn't exist, add it
            logger.info("Migration: Adding scraping_session_id to scraped_comments")
            cursor.execute("ALTER TABLE scraped_comments ADD COLUMN scraping_session_id INTEGER")
        
        try:
            cursor.execute("SELECT profile_id FROM scraped_comments LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Migration: Adding profile_id to scraped_comments")
            cursor.execute("ALTER TABLE scraped_comments ADD COLUMN profile_id INTEGER")
        
        try:
            cursor.execute("SELECT target_username FROM scraped_comments LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Migration: Adding target_username to scraped_comments")
            cursor.execute("ALTER TABLE scraped_comments ADD COLUMN target_username TEXT")
        
        try:
            cursor.execute("SELECT is_reply FROM scraped_comments LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Migration: Adding is_reply to scraped_comments")
            cursor.execute("ALTER TABLE scraped_comments ADD COLUMN is_reply INTEGER DEFAULT 0")
        
        # Create indexes if they don't exist (safe to run multiple times)
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_comments_session ON scraped_comments(scraping_session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_comments_username ON scraped_comments(username)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_comments_target ON scraped_comments(target_username)")
        except sqlite3.OperationalError:
            pass  # Indexes might fail if columns don't exist yet
        
        # Migration: Add missing columns to instagram_profiles
        for col_name, col_def in [
            ("is_verified", "INTEGER DEFAULT 0"),
            ("is_business", "INTEGER DEFAULT 0"),
            ("business_category", "TEXT"),
            ("website", "TEXT"),
            ("linked_accounts", "TEXT"),
        ]:
            try:
                cursor.execute(f"SELECT {col_name} FROM instagram_profiles LIMIT 1")
            except sqlite3.OperationalError:
                logger.info(f"Migration: Adding {col_name} to instagram_profiles")
                cursor.execute(f"ALTER TABLE instagram_profiles ADD COLUMN {col_name} {col_def}")
        
        # Migration: Add discovery_campaign_id to scraping_sessions
        try:
            cursor.execute("SELECT discovery_campaign_id FROM scraping_sessions LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Migration: Adding discovery_campaign_id to scraping_sessions")
            cursor.execute("ALTER TABLE scraping_sessions ADD COLUMN discovery_campaign_id INTEGER")
        
        # Migration: Add AI qualification columns to scraped_profiles
        for col_name, col_def in [
            ("ai_score", "INTEGER"),
            ("ai_qualified", "INTEGER DEFAULT 0"),
            ("ai_analysis", "TEXT"),
            ("qualification_criteria", "TEXT"),
            ("scored_at", "TEXT"),
        ]:
            try:
                cursor.execute(f"SELECT {col_name} FROM scraped_profiles LIMIT 1")
            except sqlite3.OperationalError:
                logger.info(f"Migration: Adding {col_name} to scraped_profiles")
                cursor.execute(f"ALTER TABLE scraped_profiles ADD COLUMN {col_name} {col_def}")
        
        # Create indexes for AI qualification
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_profiles_qualified ON scraped_profiles(ai_qualified)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_profiles_score ON scraped_profiles(ai_score)")
        except sqlite3.OperationalError:
            pass
        
        # Migration: Migrate old tiktok_scraped_profiles data to tiktok_profiles
        # This ensures profiles scraped before the architecture change are in the main table
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tiktok_scraped_profiles'")
            if cursor.fetchone():
                # Check if old table has the old schema (with all profile data)
                cursor.execute("PRAGMA table_info(tiktok_scraped_profiles)")
                columns = [col[1] for col in cursor.fetchall()]
                
                if 'bio' in columns and 'followers_count' in columns:
                    # Old schema detected - migrate data to tiktok_profiles
                    logger.info("Migration: Migrating old tiktok_scraped_profiles data to tiktok_profiles")
                    
                    # Insert profiles that don't exist yet
                    cursor.execute("""
                        INSERT OR IGNORE INTO tiktok_profiles 
                            (username, display_name, followers_count, following_count, likes_count, 
                             videos_count, biography, is_private, is_verified)
                        SELECT DISTINCT 
                            username, display_name, followers_count, following_count, likes_count,
                            posts_count, bio, is_private, is_verified
                        FROM tiktok_scraped_profiles
                        WHERE username IS NOT NULL AND username != ''
                    """)
                    migrated = cursor.rowcount
                    if migrated > 0:
                        logger.info(f"Migration: Migrated {migrated} TikTok profiles to main table")
                    
                    # Now recreate tiktok_scraped_profiles as junction table
                    # First, backup the scraping_id -> username mappings
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS _tiktok_scraped_profiles_backup AS
                        SELECT scraping_id, username, is_enriched, scraped_at
                        FROM tiktok_scraped_profiles
                    """)
                    
                    # Drop old table
                    cursor.execute("DROP TABLE IF EXISTS tiktok_scraped_profiles")
                    
                    # Create new junction table
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS tiktok_scraped_profiles (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            scraping_id INTEGER NOT NULL,
                            profile_id INTEGER NOT NULL,
                            is_enriched INTEGER DEFAULT 0,
                            scraped_at TEXT DEFAULT (datetime('now')),
                            FOREIGN KEY (scraping_id) REFERENCES scraping_sessions(scraping_id) ON DELETE CASCADE,
                            FOREIGN KEY (profile_id) REFERENCES tiktok_profiles(profile_id) ON DELETE CASCADE,
                            UNIQUE(scraping_id, profile_id)
                        )
                    """)
                    
                    # Restore mappings using profile_id from tiktok_profiles
                    cursor.execute("""
                        INSERT OR IGNORE INTO tiktok_scraped_profiles (scraping_id, profile_id, is_enriched, scraped_at)
                        SELECT b.scraping_id, tp.profile_id, b.is_enriched, b.scraped_at
                        FROM _tiktok_scraped_profiles_backup b
                        JOIN tiktok_profiles tp ON tp.username = b.username
                        WHERE b.scraping_id IS NOT NULL
                    """)
                    
                    # Drop backup table
                    cursor.execute("DROP TABLE IF EXISTS _tiktok_scraped_profiles_backup")
                    
                    logger.info("Migration: TikTok scraped profiles table converted to junction table")
        except sqlite3.OperationalError as e:
            logger.warning(f"Migration warning (tiktok_scraped_profiles): {e}")
        
        conn.commit()
    
    def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("Database connection closed")
    
    # ============================================
    # ACCOUNTS (delegated to AccountRepository)
    # ============================================
    
    def get_or_create_account(self, username: str, is_bot: bool = True, 
                               user_id: Optional[int] = None, 
                               license_id: Optional[int] = None) -> Tuple[int, bool]:
        """Get existing account or create a new one."""
        return self.accounts.get_or_create(username, is_bot, user_id, license_id)
    
    def get_account_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get account by username."""
        return self.accounts.find_by_username(username)
    
    # ============================================
    # PROFILES (delegated to ProfileRepository)
    # ============================================
    
    def get_or_create_profile(self, profile_data: Dict[str, Any]) -> Tuple[int, bool]:
        """Get existing profile or create/update one."""
        username = profile_data.get('username')
        if not username:
            raise ValueError("Username is required")
        # Remove username from kwargs to avoid duplicate argument
        kwargs = {k: v for k, v in profile_data.items() if k != 'username'}
        return self.profiles.get_or_create(username, **kwargs)
    
    def get_profile_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get profile by username."""
        return self.profiles.find_by_username(username)
    
    def save_profile(self, profile_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Save a profile and optionally record enriched stats.
        
        Returns:
            Dict with 'profile_id' and 'created' keys
        """
        profile_id, created = self.get_or_create_profile(profile_data)
        
        # If we have enriched data (followers_count > 0 or other stats), record in profile_stats_history
        has_enriched_data = (
            profile_data.get('followers_count', 0) > 0 or
            profile_data.get('following_count', 0) > 0 or
            profile_data.get('posts_count', 0) > 0 or
            profile_data.get('biography') or
            profile_data.get('full_name')
        )
        
        if has_enriched_data and profile_id:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                
                # Insert enriched stats into profile_stats_history
                cursor.execute("""
                    INSERT INTO profile_stats_history 
                    (profile_id, followers_count, following_count, posts_count, 
                     is_verified, is_business, category, external_url, profile_pic_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    profile_id,
                    profile_data.get('followers_count', 0),
                    profile_data.get('following_count', 0),
                    profile_data.get('posts_count', 0),
                    1 if profile_data.get('is_verified') else 0,
                    1 if profile_data.get('is_business') else 0,
                    profile_data.get('category'),
                    profile_data.get('external_url'),
                    profile_data.get('profile_pic_url')
                ))
                conn.commit()
                logger.debug(f"Recorded enriched stats for profile {profile_id}")
            except Exception as e:
                logger.warning(f"Failed to record enriched stats for profile {profile_id}: {e}")
        
        return {'profile_id': profile_id, 'created': created}
    
    # ============================================
    # INTERACTIONS (delegated to InteractionRepository)
    # ============================================
    
    def record_interaction(self, account_id: int, target_username: str, 
                          interaction_type: str, success: bool = True,
                          content: Optional[str] = None, 
                          session_id: Optional[int] = None) -> bool:
        """Record an interaction with a profile."""
        try:
            profile_id, _ = self.get_or_create_profile({'username': target_username})
            interaction_id = self.interactions.record(
                account_id=account_id,
                profile_id=profile_id,
                interaction_type=interaction_type,
                success=success,
                content=content,
                session_id=session_id
            )
            # Update daily stats
            self._update_daily_stats(account_id, interaction_type)
            logger.debug(f"Recorded {interaction_type} on {target_username}")
            return interaction_id is not None
        except Exception as e:
            logger.error(f"Error recording interaction: {e}")
            return False
    
    def check_recent_interaction(self, target_username: str, account_id: int, 
                                  days: int = 7) -> bool:
        """Check if there was a recent interaction with a profile."""
        profile = self.get_profile_by_username(target_username)
        if not profile:
            return False
        return self.interactions.has_recent_interaction(account_id, profile['profile_id'], days)
    
    def get_interactions(self, account_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent interactions for an account."""
        return self.interactions.find_by_account(account_id, limit)
    
    def is_profile_recently_scraped(self, username: str, days: int = 7) -> bool:
        """
        Check if a profile was recently scraped/updated in the database.
        
        This is used by Discovery workflow to avoid re-visiting profiles
        that were already scraped in recent sessions.
        
        Args:
            username: Instagram username to check
            days: Number of days to consider as "recent" (default 7)
            
        Returns:
            True if profile exists and was updated within the time window
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT profile_id, updated_at 
            FROM instagram_profiles 
            WHERE username = ? 
            AND updated_at >= datetime('now', '-' || ? || ' days')
        """, (username, days))
        
        row = cursor.fetchone()
        return row is not None
    
    def get_recently_scraped_usernames(self, days: int = 7, limit: int = 10000) -> set:
        """
        Get a set of usernames that were recently scraped.
        
        This is used to bulk-load usernames for efficient checking
        during Discovery workflow.
        
        Args:
            days: Number of days to consider as "recent" (default 7)
            limit: Maximum number of usernames to return
            
        Returns:
            Set of usernames that were recently scraped
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT username 
            FROM instagram_profiles 
            WHERE updated_at >= datetime('now', '-' || ? || ' days')
            LIMIT ?
        """, (days, limit))
        
        return {row['username'] for row in cursor.fetchall()}
    
    # ============================================
    # FILTERED PROFILES (delegated to InteractionRepository)
    # ============================================
    
    def record_filtered_profile(self, account_id: int, username: str, reason: str,
                                 source_type: str, source_name: str,
                                 session_id: Optional[int] = None) -> bool:
        """Record a filtered (skipped) profile."""
        try:
            profile_id, _ = self.get_or_create_profile({'username': username})
            result = self.interactions.record_filtered(
                account_id=account_id,
                profile_id=profile_id,
                username=username,
                reason=reason,
                source_type=source_type,
                source_name=source_name,
                session_id=session_id
            )
            logger.debug(f"Recorded filtered profile: {username} ({reason})")
            return result
        except Exception as e:
            logger.error(f"Error recording filtered profile: {e}")
            return False
    
    def is_profile_filtered(self, username: str, account_id: int) -> bool:
        """Check if a profile is filtered for an account."""
        return self.interactions.is_filtered(username, account_id)
    
    def check_filtered_profiles_batch(self, usernames: List[str], account_id: int) -> List[str]:
        """Check multiple profiles at once, return list of filtered usernames."""
        return self.interactions.get_filtered_usernames(usernames, account_id)
    
    # ============================================
    # SESSIONS (delegated to SessionRepository)
    # ============================================
    
    def create_session(self, account_id: int, session_name: str, target_type: str,
                       target: str, config_used: Optional[Dict] = None) -> Optional[int]:
        """Create a new automation session."""
        session_id = self.sessions.create(
            account_id=account_id,
            session_name=session_name,
            target_type=target_type,
            target=target,
            config_used=config_used
        )
        if session_id:
            self._increment_daily_session_count(account_id)
            logger.info(f"Created session {session_id}: {session_name}")
        return session_id
    
    def update_session(self, session_id: int, **kwargs) -> bool:
        """Update a session. Supported kwargs: status, end_time, duration_seconds, error_message"""
        result = self.sessions.update(session_id, **kwargs)
        # Update daily stats for completed/failed sessions
        status = kwargs.get('status')
        if result and status in ('COMPLETED', 'FAILED', 'ERROR'):
            session = self.get_session(session_id)
            if session:
                self._update_daily_session_status(
                    session['account_id'], 
                    status, 
                    kwargs.get('duration_seconds', 0)
                )
        return result
    
    def get_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Get a session by ID."""
        return self.sessions.find_by_id(session_id)
    
    def get_sessions_by_account(self, account_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get sessions by account."""
        return self.sessions.find_by_account(account_id, limit)
    
    def get_session_stats(self, session_id: int) -> Optional[Dict[str, int]]:
        """Get aggregated stats for a session."""
        session = self.get_session(session_id)
        if not session:
            return None
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_interactions,
                SUM(CASE WHEN interaction_type = 'LIKE' THEN 1 ELSE 0 END) as total_likes,
                SUM(CASE WHEN interaction_type = 'FOLLOW' THEN 1 ELSE 0 END) as total_follows,
                SUM(CASE WHEN interaction_type = 'UNFOLLOW' THEN 1 ELSE 0 END) as total_unfollows,
                SUM(CASE WHEN interaction_type = 'COMMENT' THEN 1 ELSE 0 END) as total_comments,
                SUM(CASE WHEN interaction_type = 'STORY_WATCH' THEN 1 ELSE 0 END) as total_story_views,
                SUM(CASE WHEN interaction_type = 'STORY_LIKE' THEN 1 ELSE 0 END) as total_story_likes,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_interactions
            FROM interaction_history
            WHERE session_id = ?
        """, (session_id,))
        
        row = cursor.fetchone()
        
        return {
            'total_interactions': row['total_interactions'] or 0,
            'total_likes': row['total_likes'] or 0,
            'total_follows': row['total_follows'] or 0,
            'total_unfollows': row['total_unfollows'] or 0,
            'total_comments': row['total_comments'] or 0,
            'total_story_views': row['total_story_views'] or 0,
            'total_story_likes': row['total_story_likes'] or 0,
            'successful_interactions': row['successful_interactions'] or 0
        }
    
    # ============================================
    # DAILY STATS (for API sync)
    # ============================================
    
    def _update_daily_stats(self, account_id: int, interaction_type: str) -> None:
        """Update daily stats when an interaction is recorded."""
        column_map = {
            'LIKE': 'total_likes',
            'FOLLOW': 'total_follows',
            'UNFOLLOW': 'total_unfollows',
            'COMMENT': 'total_comments',
            'STORY_WATCH': 'total_story_views',
            'STORY_LIKE': 'total_story_likes',
            'PROFILE_VISIT': 'total_profile_visits'
        }
        
        column = column_map.get(interaction_type.upper())
        if not column:
            return
        
        today = datetime.now().strftime('%Y-%m-%d')
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(f"""
            INSERT INTO daily_stats (account_id, date, {column})
            VALUES (?, ?, 1)
            ON CONFLICT(account_id, date) DO UPDATE SET
                {column} = {column} + 1,
                updated_at = datetime('now')
        """, (account_id, today))
        conn.commit()
    
    def _increment_daily_session_count(self, account_id: int) -> None:
        """Increment session count for today."""
        today = datetime.now().strftime('%Y-%m-%d')
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO daily_stats (account_id, date, total_sessions)
            VALUES (?, ?, 1)
            ON CONFLICT(account_id, date) DO UPDATE SET
                total_sessions = total_sessions + 1,
                updated_at = datetime('now')
        """, (account_id, today))
        conn.commit()
    
    def _update_daily_session_status(self, account_id: int, status: str, duration: int) -> None:
        """Update daily stats when a session completes."""
        today = datetime.now().strftime('%Y-%m-%d')
        column = 'completed_sessions' if status == 'COMPLETED' else 'failed_sessions'
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(f"""
            INSERT INTO daily_stats (account_id, date, {column}, total_duration_seconds)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(account_id, date) DO UPDATE SET
                {column} = {column} + 1,
                total_duration_seconds = total_duration_seconds + ?,
                updated_at = datetime('now')
        """, (account_id, today, duration, duration))
        conn.commit()
    
    def get_unsynced_sessions(self) -> List[Dict[str, Any]]:
        """Get sessions that haven't been synced to the API."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM sessions 
            WHERE synced_to_api = 0 AND status IN ('COMPLETED', 'FAILED', 'ERROR')
        """)
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_unsynced_daily_stats(self) -> List[Dict[str, Any]]:
        """Get daily stats that haven't been synced to the API."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM daily_stats WHERE synced_to_api = 0")
        
        return [dict(row) for row in cursor.fetchall()]
    
    def mark_sessions_synced(self, session_ids: List[int]) -> None:
        """Mark sessions as synced to API."""
        if not session_ids:
            return
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        placeholders = ','.join(['?' for _ in session_ids])
        cursor.execute(f"""
            UPDATE sessions SET synced_to_api = 1 WHERE session_id IN ({placeholders})
        """, session_ids)
        conn.commit()
    
    def mark_daily_stats_synced(self, stat_ids: List[int]) -> None:
        """Mark daily stats as synced to API."""
        if not stat_ids:
            return
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        placeholders = ','.join(['?' for _ in stat_ids])
        cursor.execute(f"""
            UPDATE daily_stats SET synced_to_api = 1, synced_at = datetime('now')
            WHERE id IN ({placeholders})
        """, stat_ids)
        conn.commit()
    
    # ============================================
    # PROFILE PROCESSED CHECK
    # ============================================
    
    def check_profile_processed(self, account_id: int, username: str, 
                                 hours_limit: int = 24) -> Dict[str, Any]:
        """Check if a profile was recently processed."""
        profile = self.get_profile_by_username(username)
        if not profile:
            return {'processed': False}
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT interaction_type, interaction_time
            FROM interaction_history
            WHERE account_id = ? AND profile_id = ?
            AND interaction_time >= datetime('now', '-' || ? || ' hours')
            ORDER BY interaction_time DESC
            LIMIT 1
        """, (account_id, profile['profile_id'], hours_limit))
        
        row = cursor.fetchone()
        
        if row:
            return {
                'processed': True,
                'last_interaction': row['interaction_time'],
                'interaction_type': row['interaction_type']
            }
        
        return {'processed': False}
    
    # ============================================
    # ANALYTICS
    # ============================================
    
    def get_account_stats(self, account_id: int, days: int = 7) -> Dict[str, Any]:
        """Get aggregated stats for an account."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COALESCE(SUM(total_sessions), 0) as total_sessions,
                COALESCE(SUM(total_likes), 0) as total_likes,
                COALESCE(SUM(total_follows), 0) as total_follows,
                COALESCE(SUM(total_unfollows), 0) as total_unfollows,
                COALESCE(SUM(total_comments), 0) as total_comments,
                COALESCE(SUM(total_story_views), 0) as total_story_views,
                COALESCE(SUM(total_story_likes), 0) as total_story_likes,
                COALESCE(SUM(total_profile_visits), 0) as total_profile_visits,
                COALESCE(SUM(total_duration_seconds), 0) as total_duration,
                COALESCE(SUM(completed_sessions), 0) as completed_sessions,
                COALESCE(SUM(failed_sessions), 0) as failed_sessions
            FROM daily_stats
            WHERE account_id = ?
            AND date >= date('now', '-' || ? || ' days')
        """, (account_id, days))
        
        row = cursor.fetchone()
        return dict(row) if row else {}
    
    # ============================================
    # SCRAPING SESSIONS
    # ============================================
    
    def create_scraping_session(self, scraping_type: str, source_type: str, source_name: str,
                                 max_profiles: int = 500, export_csv: bool = False,
                                 save_to_db: bool = True, account_id: Optional[int] = None,
                                 config: Optional[Dict] = None) -> Optional[int]:
        """
        Create a new scraping session.
        
        Args:
            scraping_type: Type of scraping (followers, following, likers, authors)
            source_type: Source type (TARGET, HASHTAG, POST_URL)
            source_name: Source name (@username, #hashtag, or post URL)
            max_profiles: Maximum profiles to scrape
            export_csv: Whether to export to CSV
            save_to_db: Whether to save profiles to database
            account_id: Optional bot account ID
            config: Optional full config dict
            
        Returns:
            scraping_id or None if failed
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO scraping_sessions 
                (account_id, scraping_type, source_type, source_name, max_profiles, export_csv, save_to_db, config_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                account_id,
                scraping_type,
                source_type,
                source_name,
                max_profiles,
                1 if export_csv else 0,
                1 if save_to_db else 0,
                json.dumps(config) if config else None
            ))
            conn.commit()
            
            scraping_id = cursor.lastrowid
            logger.info(f"Created scraping session {scraping_id}: {scraping_type} from {source_type}:{source_name}")
            return scraping_id
            
        except Exception as e:
            logger.error(f"Error creating scraping session: {e}")
            return None
    
    def update_scraping_session(self, scraping_id: int, **kwargs) -> bool:
        """
        Update a scraping session.
        
        Supported kwargs: total_scraped, csv_path, end_time, duration_seconds, status, error_message
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            updates = []
            values = []
            
            if 'total_scraped' in kwargs:
                updates.append("total_scraped = ?")
                values.append(kwargs['total_scraped'])
            if 'csv_path' in kwargs:
                updates.append("csv_path = ?")
                values.append(kwargs['csv_path'])
            if 'end_time' in kwargs:
                updates.append("end_time = ?")
                values.append(kwargs['end_time'])
            if 'duration_seconds' in kwargs:
                updates.append("duration_seconds = ?")
                values.append(kwargs['duration_seconds'])
            if 'status' in kwargs:
                updates.append("status = ?")
                values.append(kwargs['status'])
            if 'error_message' in kwargs:
                updates.append("error_message = ?")
                values.append(kwargs['error_message'])
            
            if not updates:
                return True
            
            values.append(scraping_id)
            
            cursor.execute(f"UPDATE scraping_sessions SET {', '.join(updates)} WHERE scraping_id = ?", values)
            conn.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating scraping session {scraping_id}: {e}")
            return False
    
    def update_scraping_session_count(self, scraping_id: int, total_scraped: int) -> bool:
        """Update the scraped count for a session (called during scraping to save progress)."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE scraping_sessions SET total_scraped = ? WHERE scraping_id = ?",
                (total_scraped, scraping_id)
            )
            conn.commit()
            return True
        except Exception as e:
            logger.debug(f"Error updating scraping session count: {e}")
            return False
    
    def cancel_scraping_session(self, scraping_id: int, total_scraped: int) -> bool:
        """Mark a scraping session as cancelled (user stopped it)."""
        from datetime import datetime
        
        session = self.get_scraping_session(scraping_id)
        if not session:
            return False
        
        start_time = datetime.fromisoformat(session['start_time'].replace('Z', '+00:00')) if session.get('start_time') else datetime.now()
        end_time = datetime.now()
        duration = int((end_time - start_time).total_seconds())
        
        return self.update_scraping_session(
            scraping_id,
            total_scraped=total_scraped,
            end_time=end_time.isoformat(),
            duration_seconds=duration,
            status='CANCELLED'
        )
    
    def link_profile_to_session(self, scraping_id: int, profile_id: int) -> bool:
        """
        Link a profile to a scraping session in the scraped_profiles junction table.
        
        Args:
            scraping_id: The scraping session ID
            profile_id: The profile ID
            
        Returns:
            True if linked successfully
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR IGNORE INTO scraped_profiles (scraping_id, profile_id)
                VALUES (?, ?)
            """, (scraping_id, profile_id))
            conn.commit()
            return True
        except Exception as e:
            logger.debug(f"Error linking profile {profile_id} to session {scraping_id}: {e}")
            return False
    
    def cleanup_orphan_sessions(self) -> int:
        """Mark any IN_PROGRESS sessions as INTERRUPTED (app crashed/closed unexpectedly)."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Find and update orphan sessions
            cursor.execute("""
                UPDATE scraping_sessions 
                SET status = 'INTERRUPTED', 
                    end_time = datetime('now'),
                    error_message = 'Session interrupted (app closed unexpectedly)'
                WHERE status = 'IN_PROGRESS'
            """)
            
            affected = cursor.rowcount
            conn.commit()
            
            if affected > 0:
                logger.info(f"Cleaned up {affected} orphan scraping sessions")
            
            return affected
        except Exception as e:
            logger.error(f"Error cleaning up orphan sessions: {e}")
            return 0
    
    def complete_scraping_session(self, scraping_id: int, total_scraped: int, 
                                   csv_path: Optional[str] = None,
                                   error_message: Optional[str] = None) -> bool:
        """Mark a scraping session as completed."""
        from datetime import datetime
        
        # Get session to calculate duration
        session = self.get_scraping_session(scraping_id)
        if not session:
            return False
        
        start_time = datetime.fromisoformat(session['start_time'].replace('Z', '+00:00')) if session.get('start_time') else datetime.now()
        end_time = datetime.now()
        duration = int((end_time - start_time).total_seconds())
        
        status = 'COMPLETED' if not error_message else 'ERROR'
        
        return self.update_scraping_session(
            scraping_id,
            total_scraped=total_scraped,
            csv_path=csv_path,
            end_time=end_time.isoformat(),
            duration_seconds=duration,
            status=status,
            error_message=error_message
        )
    
    def get_scraping_session(self, scraping_id: int) -> Optional[Dict[str, Any]]:
        """Get a scraping session by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM scraping_sessions WHERE scraping_id = ?", (scraping_id,))
        row = cursor.fetchone()
        
        if row:
            result = dict(row)
            result['export_csv'] = bool(result.get('export_csv'))
            result['save_to_db'] = bool(result.get('save_to_db'))
            return result
        return None
    
    def get_scraping_sessions(self, limit: int = 50, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent scraping sessions."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if status:
            cursor.execute("""
                SELECT * FROM scraping_sessions 
                WHERE status = ?
                ORDER BY created_at DESC LIMIT ?
            """, (status, limit))
        else:
            cursor.execute("""
                SELECT * FROM scraping_sessions 
                ORDER BY created_at DESC LIMIT ?
            """, (limit,))
        
        results = []
        for row in cursor.fetchall():
            r = dict(row)
            r['export_csv'] = bool(r.get('export_csv'))
            r['save_to_db'] = bool(r.get('save_to_db'))
            results.append(r)
        
        return results
    
    def get_scraping_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get aggregated scraping statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_sessions,
                COALESCE(SUM(total_scraped), 0) as total_profiles_scraped,
                COALESCE(SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END), 0) as completed_sessions,
                COALESCE(SUM(CASE WHEN status = 'ERROR' THEN 1 ELSE 0 END), 0) as failed_sessions,
                COALESCE(SUM(duration_seconds), 0) as total_duration_seconds,
                COALESCE(AVG(total_scraped), 0) as avg_profiles_per_session
            FROM scraping_sessions
            WHERE created_at >= datetime('now', '-' || ? || ' days')
        """, (days,))
        
        row = cursor.fetchone()
        return dict(row) if row else {}
    
    # ============================================
    # SCRAPED COMMENTS
    # ============================================
    
    def save_scraped_comment(
        self,
        username: str,
        content: str,
        target_username: str,
        post_url: Optional[str] = None,
        scraping_session_id: Optional[int] = None,
        likes_count: int = 0,
        is_reply: bool = False,
        parent_comment_id: Optional[int] = None
    ) -> Optional[int]:
        """
        Save a scraped comment to the database.
        
        Args:
            username: Username of the commenter
            content: Comment text content
            target_username: Username of the target account (whose post was commented)
            post_url: URL of the post
            scraping_session_id: ID of the scraping session
            likes_count: Number of likes on the comment
            is_reply: Whether this is a reply to another comment
            parent_comment_id: ID of parent comment if this is a reply
            
        Returns:
            comment_id if successful, None otherwise
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Get or create profile for the commenter
            profile_id = None
            try:
                profile_id, _ = self.get_or_create_profile({'username': username})
            except:
                pass
            
            cursor.execute("""
                INSERT INTO scraped_comments 
                (scraping_session_id, profile_id, target_username, post_url, username, content, likes_count, is_reply, parent_comment_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                scraping_session_id,
                profile_id,
                target_username,
                post_url,
                username,
                content,
                likes_count,
                1 if is_reply else 0,
                parent_comment_id
            ))
            conn.commit()
            
            comment_id = cursor.lastrowid
            logger.debug(f"Saved comment from @{username} on @{target_username}'s post: {content[:50]}...")
            return comment_id
            
        except Exception as e:
            logger.error(f"Error saving scraped comment: {e}")
            return None
    
    def get_comments_by_username(self, username: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all comments made by a specific user."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM scraped_comments 
            WHERE username = ?
            ORDER BY scraped_at DESC LIMIT ?
        """, (username, limit))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_comments_on_target(self, target_username: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all comments on a target's posts."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM scraped_comments 
            WHERE target_username = ?
            ORDER BY scraped_at DESC LIMIT ?
        """, (target_username, limit))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_comments_by_session(self, scraping_session_id: int) -> List[Dict[str, Any]]:
        """Get all comments from a specific scraping session."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM scraped_comments 
            WHERE scraping_session_id = ?
            ORDER BY scraped_at ASC
        """, (scraping_session_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    # ============================================
    # PROCESSED HASHTAG POSTS
    # ============================================
    
    def is_hashtag_post_processed(
        self, 
        account_id: int, 
        hashtag: str, 
        post_author: str, 
        post_caption_hash: Optional[str] = None,
        hours_limit: int = 168  # 7 days default
    ) -> bool:
        """
        Check if a hashtag post has already been processed.
        
        Args:
            account_id: Bot account ID
            hashtag: Hashtag name (without #)
            post_author: Username of the post author
            post_caption_hash: Hash of the caption (first 100 chars)
            hours_limit: Only consider posts processed within this time window
            
        Returns:
            True if post was already processed
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Build query based on available data
            if post_caption_hash:
                cursor.execute("""
                    SELECT id FROM processed_hashtag_posts
                    WHERE account_id = ? 
                    AND hashtag = ? 
                    AND post_author = ?
                    AND post_caption_hash = ?
                    AND processed_at >= datetime('now', '-' || ? || ' hours')
                """, (account_id, hashtag.lower().strip('#'), post_author, post_caption_hash, hours_limit))
            else:
                # Without caption hash, just check author + hashtag
                cursor.execute("""
                    SELECT id FROM processed_hashtag_posts
                    WHERE account_id = ? 
                    AND hashtag = ? 
                    AND post_author = ?
                    AND processed_at >= datetime('now', '-' || ? || ' hours')
                """, (account_id, hashtag.lower().strip('#'), post_author, hours_limit))
            
            return cursor.fetchone() is not None
            
        except Exception as e:
            logger.error(f"Error checking processed hashtag post: {e}")
            return False
    
    def record_processed_hashtag_post(
        self,
        account_id: int,
        hashtag: str,
        post_author: str,
        post_caption_hash: Optional[str] = None,
        post_caption_preview: Optional[str] = None,
        likes_count: Optional[int] = None,
        comments_count: Optional[int] = None,
        likers_processed: int = 0,
        interactions_made: int = 0
    ) -> bool:
        """
        Record a hashtag post as processed.
        
        Args:
            account_id: Bot account ID
            hashtag: Hashtag name (without #)
            post_author: Username of the post author
            post_caption_hash: Hash of the caption for uniqueness
            post_caption_preview: First ~100 chars of caption for display
            likes_count: Number of likes on the post
            comments_count: Number of comments on the post
            likers_processed: Number of likers we processed
            interactions_made: Number of successful interactions
            
        Returns:
            True if recorded successfully
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO processed_hashtag_posts 
                (account_id, hashtag, post_author, post_caption_hash, post_caption_preview,
                 likes_count, comments_count, likers_processed, interactions_made, processed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                account_id,
                hashtag.lower().strip('#'),
                post_author,
                post_caption_hash,
                post_caption_preview[:100] if post_caption_preview else None,
                likes_count,
                comments_count,
                likers_processed,
                interactions_made
            ))
            conn.commit()
            
            logger.debug(f"Recorded processed hashtag post: #{hashtag} by @{post_author}")
            return True
            
        except Exception as e:
            logger.error(f"Error recording processed hashtag post: {e}")
            return False
    
    def get_processed_hashtag_posts(
        self,
        account_id: int,
        hashtag: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get list of processed hashtag posts for an account."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if hashtag:
                cursor.execute("""
                    SELECT * FROM processed_hashtag_posts
                    WHERE account_id = ? AND hashtag = ?
                    ORDER BY processed_at DESC LIMIT ?
                """, (account_id, hashtag.lower().strip('#'), limit))
            else:
                cursor.execute("""
                    SELECT * FROM processed_hashtag_posts
                    WHERE account_id = ?
                    ORDER BY processed_at DESC LIMIT ?
                """, (account_id, limit))
            
            return [dict(row) for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Error getting processed hashtag posts: {e}")
            return []
    
    # ============================================
    # TIKTOK ACCOUNTS
    # ============================================
    
    def get_or_create_tiktok_account(self, username: str, display_name: str = None,
                                      is_bot: bool = True, user_id: Optional[int] = None,
                                      license_id: Optional[int] = None) -> Tuple[int, bool]:
        """Get existing TikTok account or create a new one."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT account_id FROM tiktok_accounts WHERE username = ?", (username,))
        row = cursor.fetchone()
        
        if row:
            return row['account_id'], False
        
        cursor.execute("""
            INSERT INTO tiktok_accounts (username, display_name, is_bot, user_id, license_id)
            VALUES (?, ?, ?, ?, ?)
        """, (username, display_name, 1 if is_bot else 0, user_id, license_id))
        conn.commit()
        
        logger.debug(f"Created TikTok account: {username} (ID: {cursor.lastrowid})")
        return cursor.lastrowid, True
    
    def get_tiktok_account_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get TikTok account by username."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM tiktok_accounts WHERE username = ?", (username,))
        row = cursor.fetchone()
        
        return dict(row) if row else None
    
    # ============================================
    # TIKTOK PROFILES
    # ============================================
    
    def get_or_create_tiktok_profile(self, profile_data: Dict[str, Any]) -> Tuple[int, bool]:
        """Get existing TikTok profile or create/update one.
        
        If profile exists, updates it with any non-null values from profile_data.
        This allows enriching profiles with data extracted from the UI.
        """
        username = profile_data.get('username')
        if not username:
            raise ValueError("Username is required")
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT profile_id FROM tiktok_profiles WHERE username = ?", (username,))
        row = cursor.fetchone()
        
        if row:
            profile_id = row['profile_id']
            # Update existing profile with non-null values
            updates = []
            values = []
            
            for field in ('display_name', 'biography'):
                if profile_data.get(field):
                    updates.append(f"{field} = COALESCE(?, {field})")
                    values.append(profile_data[field])
            
            for field in ('followers_count', 'following_count', 'likes_count', 'videos_count'):
                if profile_data.get(field) and profile_data[field] > 0:
                    updates.append(f"{field} = ?")
                    values.append(profile_data[field])
            
            for field in ('is_private', 'is_verified'):
                if field in profile_data and profile_data[field] is not None:
                    updates.append(f"{field} = ?")
                    values.append(1 if profile_data[field] else 0)
            
            if updates:
                updates.append("updated_at = datetime('now')")
                values.append(profile_id)
                cursor.execute(
                    f"UPDATE tiktok_profiles SET {', '.join(updates)} WHERE profile_id = ?",
                    tuple(values)
                )
                conn.commit()
                logger.debug(f"Updated TikTok profile: {username}")
            
            return profile_id, False
        
        cursor.execute("""
            INSERT INTO tiktok_profiles (username, display_name, followers_count, following_count,
                                         likes_count, videos_count, is_private, is_verified, biography)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            username,
            profile_data.get('display_name', ''),
            profile_data.get('followers_count', 0),
            profile_data.get('following_count', 0),
            profile_data.get('likes_count', 0),
            profile_data.get('videos_count', 0),
            1 if profile_data.get('is_private') else 0,
            1 if profile_data.get('is_verified') else 0,
            profile_data.get('biography', '')
        ))
        conn.commit()
        
        logger.debug(f"Created TikTok profile: {username}")
        return cursor.lastrowid, True
    
    def get_tiktok_profile_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get TikTok profile by username."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM tiktok_profiles WHERE username = ?", (username,))
        row = cursor.fetchone()
        
        return dict(row) if row else None
    
    # ============================================
    # TIKTOK SESSIONS
    # ============================================
    
    def create_tiktok_session(self, account_id: int, session_name: str, workflow_type: str,
                               target: str = None, config_used: Optional[Dict] = None) -> Optional[int]:
        """Create a new TikTok automation session."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO tiktok_sessions (account_id, session_name, workflow_type, target, config_used)
                VALUES (?, ?, ?, ?, ?)
            """, (
                account_id,
                session_name[:100],
                workflow_type,
                target[:50] if target else None,
                json.dumps(config_used) if config_used else None
            ))
            conn.commit()
            
            session_id = cursor.lastrowid
            logger.info(f"Created TikTok session {session_id}: {session_name} ({workflow_type})")
            return session_id
            
        except Exception as e:
            logger.error(f"Error creating TikTok session: {e}")
            return None
    
    def update_tiktok_session(self, session_id: int, **kwargs) -> bool:
        """Update TikTok session with new values."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Build dynamic update query
            updates = []
            values = []
            for key, value in kwargs.items():
                if key in ['status', 'end_time', 'duration_seconds', 'profiles_visited',
                           'posts_watched', 'likes', 'follows', 'favorites', 'comments',
                           'shares', 'errors', 'error_message']:
                    updates.append(f"{key} = ?")
                    values.append(value)
            
            if not updates:
                return True
            
            updates.append("updated_at = datetime('now')")
            values.append(session_id)
            
            cursor.execute(f"""
                UPDATE tiktok_sessions SET {', '.join(updates)}
                WHERE session_id = ?
            """, values)
            conn.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating TikTok session: {e}")
            return False
    
    def end_tiktok_session(self, session_id: int, status: str = 'COMPLETED',
                           error_message: str = None, stats: Dict = None) -> bool:
        """End a TikTok session with final stats."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Get session start time to calculate duration
            cursor.execute("SELECT start_time FROM tiktok_sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            
            duration = 0
            if row and row['start_time']:
                from datetime import datetime
                start = datetime.fromisoformat(row['start_time'].replace('Z', '+00:00'))
                duration = int((datetime.now() - start.replace(tzinfo=None)).total_seconds())
            
            update_data = {
                'status': status,
                'end_time': datetime.now().isoformat(),
                'duration_seconds': duration,
                'error_message': error_message
            }
            
            if stats:
                update_data.update({
                    'profiles_visited': stats.get('profiles_visited', 0),
                    'posts_watched': stats.get('posts_watched', 0),
                    'likes': stats.get('likes', 0),
                    'follows': stats.get('follows', 0),
                    'favorites': stats.get('favorites', 0),
                    'comments': stats.get('comments', 0),
                    'shares': stats.get('shares', 0),
                    'errors': stats.get('errors', 0)
                })
            
            return self.update_tiktok_session(session_id, **update_data)
            
        except Exception as e:
            logger.error(f"Error ending TikTok session: {e}")
            return False
    
    def get_tiktok_sessions(self, account_id: int = None, limit: int = 50,
                            workflow_type: str = None) -> List[Dict[str, Any]]:
        """Get TikTok sessions with optional filters."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM tiktok_sessions WHERE 1=1"
        params = []
        
        if account_id:
            query += " AND account_id = ?"
            params.append(account_id)
        
        if workflow_type:
            query += " AND workflow_type = ?"
            params.append(workflow_type)
        
        query += " ORDER BY start_time DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    # ============================================
    # TIKTOK INTERACTIONS
    # ============================================
    
    def record_tiktok_interaction(self, account_id: int, target_username: str,
                                   interaction_type: str, success: bool = True,
                                   content: str = None, video_id: str = None,
                                   session_id: int = None) -> bool:
        """Record a TikTok interaction (like, follow, favorite, comment, etc.)."""
        try:
            profile_id, _ = self.get_or_create_tiktok_profile({'username': target_username})
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO tiktok_interaction_history 
                (session_id, account_id, profile_id, interaction_type, success, content, video_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                account_id,
                profile_id,
                interaction_type.upper(),
                1 if success else 0,
                content,
                video_id
            ))
            conn.commit()
            
            # Update daily stats
            self._update_tiktok_daily_stats(account_id, interaction_type)
            
            logger.debug(f"Recorded TikTok {interaction_type} on @{target_username}")
            return True
            
        except Exception as e:
            logger.error(f"Error recording TikTok interaction: {e}")
            return False
    
    def check_tiktok_recent_interaction(self, target_username: str, account_id: int,
                                         hours: int = 168) -> bool:
        """Check if there was a recent TikTok interaction with a profile."""
        profile = self.get_tiktok_profile_by_username(target_username)
        if not profile:
            return False
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) as count FROM tiktok_interaction_history
            WHERE account_id = ? AND profile_id = ?
            AND interaction_time >= datetime('now', '-' || ? || ' hours')
        """, (account_id, profile['profile_id'], hours))
        
        row = cursor.fetchone()
        return row['count'] > 0
    
    def get_tiktok_interactions(self, account_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent TikTok interactions for an account."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT ih.*, tp.username as target_username
            FROM tiktok_interaction_history ih
            JOIN tiktok_profiles tp ON ih.profile_id = tp.profile_id
            WHERE ih.account_id = ?
            ORDER BY ih.interaction_time DESC
            LIMIT ?
        """, (account_id, limit))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def has_tiktok_interaction(self, account_id: int, target_username: str, hours: int = 168) -> bool:
        """Check if we have already interacted with a TikTok profile.
        
        Args:
            account_id: The bot account ID
            target_username: Username to check
            hours: Time window in hours (default 7 days)
            
        Returns:
            True if interaction exists within the time window
        """
        return self.check_tiktok_recent_interaction(target_username, account_id, hours)
    
    # ============================================
    # TIKTOK FILTERED PROFILES
    # ============================================
    
    def record_tiktok_filtered_profile(self, account_id: int, username: str, reason: str,
                                        source_type: str, source_name: str,
                                        session_id: Optional[int] = None) -> bool:
        """Record a filtered (skipped) TikTok profile."""
        try:
            profile_id, _ = self.get_or_create_tiktok_profile({'username': username})
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO tiktok_filtered_profiles 
                (profile_id, account_id, username, reason, source_type, source_name, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (profile_id, account_id, username, reason, source_type, source_name, session_id))
            conn.commit()
            
            logger.debug(f"Recorded TikTok filtered profile: {username} ({reason})")
            return True
            
        except Exception as e:
            logger.error(f"Error recording TikTok filtered profile: {e}")
            return False
    
    def is_tiktok_profile_filtered(self, username: str, account_id: int) -> bool:
        """Check if a TikTok profile is filtered for an account."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) as count FROM tiktok_filtered_profiles
            WHERE username = ? AND account_id = ?
        """, (username, account_id))
        
        row = cursor.fetchone()
        return row['count'] > 0
    
    def count_tiktok_interactions_for_target(self, account_id: int, target_username: str, hours: int = 168) -> int:
        """Count how many unique profiles we've interacted with from a target's followers.
        
        This is used to determine if we should continue scrolling through a target's followers list.
        
        Args:
            account_id: The bot account ID
            target_username: The target account whose followers we're processing
            hours: Time window in hours (default 7 days = 168 hours)
            
        Returns:
            Number of unique profiles interacted with
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Count unique profiles we've interacted with in the time window
        # We use the session's target field to identify interactions from this target's followers
        cursor.execute("""
            SELECT COUNT(DISTINCT ih.profile_id) as count
            FROM tiktok_interaction_history ih
            JOIN tiktok_sessions ts ON ih.session_id = ts.session_id
            WHERE ih.account_id = ?
            AND ts.target = ?
            AND ih.interaction_time >= datetime('now', '-' || ? || ' hours')
        """, (account_id, target_username, hours))
        
        row = cursor.fetchone()
        return row['count'] if row else 0
    
    # ============================================
    # TIKTOK DAILY STATS
    # ============================================
    
    def _update_tiktok_daily_stats(self, account_id: int, interaction_type: str) -> None:
        """Update TikTok daily stats for an interaction."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Map interaction type to column
            column_map = {
                'LIKE': 'total_likes',
                'FOLLOW': 'total_follows',
                'FAVORITE': 'total_favorites',
                'COMMENT': 'total_comments',
                'SHARE': 'total_shares',
                'PROFILE_VISIT': 'total_profile_visits',
                'POST_WATCH': 'total_posts_watched'
            }
            
            column = column_map.get(interaction_type.upper())
            if not column:
                return
            
            # Upsert daily stats
            cursor.execute(f"""
                INSERT INTO tiktok_daily_stats (account_id, date, {column})
                VALUES (?, ?, 1)
                ON CONFLICT(account_id, date) DO UPDATE SET
                    {column} = {column} + 1,
                    updated_at = datetime('now')
            """, (account_id, today))
            conn.commit()
            
        except Exception as e:
            logger.error(f"Error updating TikTok daily stats: {e}")
    
    def get_tiktok_daily_stats(self, account_id: int, days: int = 7) -> List[Dict[str, Any]]:
        """Get TikTok daily stats for an account."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM tiktok_daily_stats
            WHERE account_id = ? AND date >= date('now', '-' || ? || ' days')
            ORDER BY date DESC
        """, (account_id, days))
        
        return [dict(row) for row in cursor.fetchall()]


# Singleton instance
_local_db_instance: Optional[LocalDatabaseService] = None


def get_local_database() -> LocalDatabaseService:
    """Get the singleton local database instance."""
    global _local_db_instance
    if _local_db_instance is None:
        _local_db_instance = LocalDatabaseService()
    return _local_db_instance
