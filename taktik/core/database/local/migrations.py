"""
Database migrations for the TAKTIK local SQLite database.

Contains ``run_migrations`` which applies incremental ALTER TABLE
statements on a database already initialised with ``create_schema``.
Imported and called by ``LocalDatabaseService._run_migrations``.
"""
import re
import sqlite3

from loguru import logger


_IDENTIFIER_RE = re.compile(r'^[a-z][a-z0-9_]*$')


def _validate_sql_identifier(name: str) -> str:
    """Assert that *name* is a safe SQL identifier.

    Returns the name unchanged if valid, raises ``ValueError`` otherwise.
    This prevents SQL injection when column/table names must be interpolated
    (SQLite does not support parameterised identifiers).
    """
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Unsafe SQL identifier rejected: {name!r}")
    return name


def run_migrations(conn: sqlite3.Connection) -> None:
    """Run migrations to add missing columns to existing tables."""
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
        ("account_based_in", "TEXT"),
        ("date_joined", "TEXT"),
        ("location_city", "TEXT"),
    ]:
        try:
            _col = _validate_sql_identifier(col_name)
            cursor.execute(f"SELECT {_col} FROM instagram_profiles LIMIT 1")
        except sqlite3.OperationalError:
            logger.info(f"Migration: Adding {col_name} to instagram_profiles")
            cursor.execute(f"ALTER TABLE instagram_profiles ADD COLUMN {_col} {col_def}")

    # Migration: Add discovery_campaign_id to scraping_sessions
    try:
        cursor.execute("SELECT discovery_campaign_id FROM scraping_sessions LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Migration: Adding discovery_campaign_id to scraping_sessions")
        cursor.execute("ALTER TABLE scraping_sessions ADD COLUMN discovery_campaign_id INTEGER")

    # Migration: Add platform column to scraping_sessions
    try:
        cursor.execute("SELECT platform FROM scraping_sessions LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Migration: Adding platform to scraping_sessions")
        cursor.execute("ALTER TABLE scraping_sessions ADD COLUMN platform TEXT DEFAULT 'instagram'")

    # Migration: Add AI qualification columns to scraped_profiles
    for col_name, col_def in [
        ("ai_score", "INTEGER"),
        ("ai_qualified", "INTEGER DEFAULT 0"),
        ("ai_analysis", "TEXT"),
        ("qualification_criteria", "TEXT"),
        ("scored_at", "TEXT"),
    ]:
        try:
            _col = _validate_sql_identifier(col_name)
            cursor.execute(f"SELECT {_col} FROM scraped_profiles LIMIT 1")
        except sqlite3.OperationalError:
            logger.info(f"Migration: Adding {col_name} to scraped_profiles")
            cursor.execute(f"ALTER TABLE scraped_profiles ADD COLUMN {_col} {col_def}")

    # Migration: Add source_post_url to scraped_profiles
    try:
        cursor.execute("SELECT source_post_url FROM scraped_profiles LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Migration: Adding source_post_url to scraped_profiles")
        cursor.execute("ALTER TABLE scraped_profiles ADD COLUMN source_post_url TEXT")

    # Create indexes for AI qualification and source_post_url
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_profiles_qualified ON scraped_profiles(ai_qualified)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_profiles_score ON scraped_profiles(ai_score)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_profiles_post_url ON scraped_profiles(source_post_url)")
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
