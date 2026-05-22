"""
Schema definitions for the TAKTIK local SQLite database.

Contains a single public function ``create_schema`` that issues all
``CREATE TABLE IF NOT EXISTS`` and ``CREATE INDEX IF NOT EXISTS``
statements.  Imported and called by ``LocalDatabaseService._create_tables``.
"""
import sqlite3

from loguru import logger  # noqa: F401  (used inside the body below)


def create_schema(conn: sqlite3.Connection) -> None:
    """Create all required tables if they don't exist."""
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
            location_city TEXT,
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
            platform TEXT DEFAULT 'instagram',
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

    # Following Sync — incremental cache of the account's following list
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS following_sync (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            first_seen_at TEXT DEFAULT (datetime('now')),
            last_seen_at TEXT DEFAULT (datetime('now')),
            is_follower_back INTEGER DEFAULT NULL,
            followed_by_bot INTEGER DEFAULT 0,
            unfollowed_at TEXT DEFAULT NULL,
            source TEXT DEFAULT 'sync',
            FOREIGN KEY (account_id) REFERENCES instagram_accounts(account_id) ON DELETE CASCADE,
            UNIQUE(account_id, username)
        )
    """)

    # Followers Sync — incremental cache of who follows this account
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS followers_sync (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            first_seen_at TEXT DEFAULT (datetime('now')),
            last_seen_at TEXT DEFAULT (datetime('now')),
            is_following_back INTEGER DEFAULT NULL,
            source TEXT DEFAULT 'sync',
            FOREIGN KEY (account_id) REFERENCES instagram_accounts(account_id) ON DELETE CASCADE,
            UNIQUE(account_id, username)
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
            source_post_url TEXT,
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

    # ============================================
    # SOCIAL GRAPH — Profile Following
    # ============================================

    # Social graph: following relationships discovered during deep qualify.
    # Each row = "profile_username follows following_username".
    # JOIN with instagram_profiles (nullable) to enrich with known niche/city.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profile_following (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_username   TEXT NOT NULL,
            profile_id         INTEGER REFERENCES instagram_profiles(profile_id) ON DELETE SET NULL,
            following_username TEXT NOT NULL,
            following_id       INTEGER REFERENCES instagram_profiles(profile_id) ON DELETE SET NULL,
            session_id         TEXT,
            discovered_at      TEXT DEFAULT (datetime('now')),
            UNIQUE(profile_username, following_username)
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_profile_following_profile "
        "ON profile_following(profile_username)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_profile_following_following "
        "ON profile_following(following_username)"
    )

    # ============================================
    # GMAIL ACCOUNTS (admin tool — OTP retrieval)
    # ============================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gmail_accounts (
            account_id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            device_id TEXT,
            last_used_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gmail_accounts_email ON gmail_accounts(email)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gmail_accounts_device ON gmail_accounts(device_id)")

    conn.commit()
