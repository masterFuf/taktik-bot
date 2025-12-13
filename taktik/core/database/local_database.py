"""
TAKTIK Local SQLite Database Service
Replaces API calls with local database operations for privacy
"""

import sqlite3
import os
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from loguru import logger


class LocalDatabaseService:
    """
    Local SQLite database service for storing Instagram automation data.
    Uses the same database as Electron app for shared access.
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
        self._ensure_database()
    
    def _ensure_database(self) -> None:
        """Ensure database directory exists and create tables if needed."""
        db_dir = os.path.dirname(self.db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Created database directory: {db_dir}")
        
        # Initialize tables
        self._create_tables()
        logger.info(f"✅ Local database initialized at: {self.db_path}")
    
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
        
        conn.commit()
    
    def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("Database connection closed")
    
    # ============================================
    # ACCOUNTS
    # ============================================
    
    def get_or_create_account(self, username: str, is_bot: bool = True, 
                               user_id: Optional[int] = None, 
                               license_id: Optional[int] = None) -> Tuple[int, bool]:
        """
        Get existing account or create a new one.
        
        Returns:
            Tuple of (account_id, created)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Check if exists
        cursor.execute("SELECT account_id FROM instagram_accounts WHERE username = ?", (username,))
        row = cursor.fetchone()
        
        if row:
            return row['account_id'], False
        
        # Create new
        cursor.execute("""
            INSERT INTO instagram_accounts (username, is_bot, user_id, license_id)
            VALUES (?, ?, ?, ?)
        """, (username, 1 if is_bot else 0, user_id, license_id))
        conn.commit()
        
        logger.debug(f"Created account: {username} (ID: {cursor.lastrowid})")
        return cursor.lastrowid, True
    
    def get_account_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get account by username."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM instagram_accounts WHERE username = ?", (username,))
        row = cursor.fetchone()
        
        if row:
            return dict(row)
        return None
    
    # ============================================
    # PROFILES
    # ============================================
    
    def get_or_create_profile(self, profile_data: Dict[str, Any]) -> Tuple[int, bool]:
        """
        Get existing profile or create/update one.
        
        Returns:
            Tuple of (profile_id, created)
        """
        username = profile_data.get('username')
        if not username:
            raise ValueError("Username is required")
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Check if exists
        cursor.execute("SELECT profile_id FROM instagram_profiles WHERE username = ?", (username,))
        row = cursor.fetchone()
        
        if row:
            # Update existing
            profile_id = row['profile_id']
            cursor.execute("""
                UPDATE instagram_profiles SET
                    full_name = COALESCE(?, full_name),
                    biography = COALESCE(?, biography),
                    followers_count = COALESCE(?, followers_count),
                    following_count = COALESCE(?, following_count),
                    posts_count = COALESCE(?, posts_count),
                    is_private = COALESCE(?, is_private),
                    profile_pic_path = COALESCE(?, profile_pic_path),
                    notes = COALESCE(?, notes),
                    updated_at = datetime('now')
                WHERE profile_id = ?
            """, (
                profile_data.get('full_name'),
                profile_data.get('biography'),
                profile_data.get('followers_count'),
                profile_data.get('following_count'),
                profile_data.get('posts_count'),
                1 if profile_data.get('is_private') else 0 if profile_data.get('is_private') is not None else None,
                profile_data.get('profile_pic_path'),
                profile_data.get('notes'),
                profile_id
            ))
            conn.commit()
            return profile_id, False
        
        # Create new
        cursor.execute("""
            INSERT INTO instagram_profiles 
            (username, full_name, biography, followers_count, following_count, posts_count, is_private, profile_pic_path, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            username,
            profile_data.get('full_name', ''),
            profile_data.get('biography'),
            profile_data.get('followers_count', 0),
            profile_data.get('following_count', 0),
            profile_data.get('posts_count', 0),
            1 if profile_data.get('is_private') else 0,
            profile_data.get('profile_pic_path'),
            profile_data.get('notes')
        ))
        conn.commit()
        
        logger.debug(f"Created profile: {username} (ID: {cursor.lastrowid})")
        return cursor.lastrowid, True
    
    def get_profile_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get profile by username."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM instagram_profiles WHERE username = ?", (username,))
        row = cursor.fetchone()
        
        if row:
            result = dict(row)
            result['is_private'] = bool(result.get('is_private'))
            return result
        return None
    
    def save_profile(self, profile_data: Dict[str, Any]) -> Optional[int]:
        """Save a profile and return its ID."""
        profile_id, _ = self.get_or_create_profile(profile_data)
        return profile_id
    
    # ============================================
    # INTERACTIONS
    # ============================================
    
    def record_interaction(self, account_id: int, target_username: str, 
                          interaction_type: str, success: bool = True,
                          content: Optional[str] = None, 
                          session_id: Optional[int] = None) -> bool:
        """
        Record an interaction with a profile.
        
        Args:
            account_id: The bot account ID
            target_username: Username of the target profile
            interaction_type: Type of interaction (LIKE, FOLLOW, etc.)
            success: Whether the interaction was successful
            content: Optional content (e.g., comment text)
            session_id: Optional session ID
            
        Returns:
            True if recorded successfully
        """
        try:
            # Get or create the target profile
            profile_id, _ = self.get_or_create_profile({'username': target_username})
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO interaction_history 
                (session_id, account_id, profile_id, interaction_type, success, content)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                account_id,
                profile_id,
                interaction_type.upper(),
                1 if success else 0,
                content
            ))
            conn.commit()
            
            # Update daily stats
            self._update_daily_stats(account_id, interaction_type)
            
            logger.debug(f"Recorded {interaction_type} on {target_username}")
            return True
            
        except Exception as e:
            logger.error(f"Error recording interaction: {e}")
            return False
    
    def check_recent_interaction(self, target_username: str, account_id: int, 
                                  days: int = 7) -> bool:
        """Check if there was a recent interaction with a profile."""
        profile = self.get_profile_by_username(target_username)
        if not profile:
            return False
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) as count FROM interaction_history
            WHERE account_id = ? AND profile_id = ?
            AND interaction_time >= datetime('now', '-' || ? || ' days')
        """, (account_id, profile['profile_id'], days))
        
        row = cursor.fetchone()
        return row['count'] > 0
    
    def get_interactions(self, account_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent interactions for an account."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT ih.*, ip.username as target_username
            FROM interaction_history ih
            JOIN instagram_profiles ip ON ih.profile_id = ip.profile_id
            WHERE ih.account_id = ?
            ORDER BY ih.interaction_time DESC
            LIMIT ?
        """, (account_id, limit))
        
        return [dict(row) for row in cursor.fetchall()]
    
    # ============================================
    # FILTERED PROFILES
    # ============================================
    
    def record_filtered_profile(self, account_id: int, username: str, reason: str,
                                 source_type: str, source_name: str,
                                 session_id: Optional[int] = None) -> bool:
        """Record a filtered (skipped) profile."""
        try:
            profile_id, _ = self.get_or_create_profile({'username': username})
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO filtered_profiles 
                (profile_id, account_id, username, reason, source_type, source_name, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (profile_id, account_id, username, reason, source_type, source_name, session_id))
            conn.commit()
            
            logger.debug(f"Recorded filtered profile: {username} ({reason})")
            return True
            
        except Exception as e:
            logger.error(f"Error recording filtered profile: {e}")
            return False
    
    def is_profile_filtered(self, username: str, account_id: int) -> bool:
        """Check if a profile is filtered for an account."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) as count FROM filtered_profiles
            WHERE username = ? AND account_id = ?
        """, (username, account_id))
        
        row = cursor.fetchone()
        return row['count'] > 0
    
    def check_filtered_profiles_batch(self, usernames: List[str], account_id: int) -> List[str]:
        """Check multiple profiles at once, return list of filtered usernames."""
        if not usernames:
            return []
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        placeholders = ','.join(['?' for _ in usernames])
        cursor.execute(f"""
            SELECT username FROM filtered_profiles
            WHERE account_id = ? AND username IN ({placeholders})
        """, [account_id] + usernames)
        
        return [row['username'] for row in cursor.fetchall()]
    
    # ============================================
    # SESSIONS
    # ============================================
    
    def create_session(self, account_id: int, session_name: str, target_type: str,
                       target: str, config_used: Optional[Dict] = None) -> Optional[int]:
        """Create a new automation session."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO sessions (account_id, session_name, target_type, target, config_used)
                VALUES (?, ?, ?, ?, ?)
            """, (
                account_id,
                session_name[:100],  # Truncate
                target_type,
                target[:50],  # Truncate
                json.dumps(config_used) if config_used else None
            ))
            conn.commit()
            
            session_id = cursor.lastrowid
            
            # Update daily stats
            self._increment_daily_session_count(account_id)
            
            logger.info(f"Created session {session_id}: {session_name}")
            return session_id
            
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return None
    
    def update_session(self, session_id: int, **kwargs) -> bool:
        """
        Update a session.
        
        Supported kwargs: status, end_time, duration_seconds, error_message
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            updates = ["updated_at = datetime('now')"]
            values = []
            
            if 'status' in kwargs:
                updates.append("status = ?")
                values.append(kwargs['status'])
            if 'end_time' in kwargs:
                updates.append("end_time = ?")
                values.append(kwargs['end_time'])
            if 'duration_seconds' in kwargs:
                updates.append("duration_seconds = ?")
                values.append(kwargs['duration_seconds'])
            if 'error_message' in kwargs:
                updates.append("error_message = ?")
                values.append(kwargs['error_message'])
            
            values.append(session_id)
            
            cursor.execute(f"UPDATE sessions SET {', '.join(updates)} WHERE session_id = ?", values)
            conn.commit()
            
            # Update daily stats for completed/failed sessions
            status = kwargs.get('status')
            if status in ('COMPLETED', 'FAILED', 'ERROR'):
                session = self.get_session(session_id)
                if session:
                    self._update_daily_session_status(
                        session['account_id'], 
                        status, 
                        kwargs.get('duration_seconds', 0)
                    )
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating session {session_id}: {e}")
            return False
    
    def get_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Get a session by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        
        if row:
            result = dict(row)
            result['synced_to_api'] = bool(result.get('synced_to_api'))
            return result
        return None
    
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


# Singleton instance
_local_db_instance: Optional[LocalDatabaseService] = None


def get_local_database() -> LocalDatabaseService:
    """Get the singleton local database instance."""
    global _local_db_instance
    if _local_db_instance is None:
        _local_db_instance = LocalDatabaseService()
    return _local_db_instance
