"""Legacy Instagram database helper shim.

This module remains in the platform package for backward compatibility, but new
database-backed workflow bookkeeping must be owned by `taktik.core.database`.
"""

from typing import Optional

from loguru import logger

from taktik.core.database.instagram_hashtag_posts import InstagramHashtagPostService
from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService

log = logger.bind(module="instagram-database-helpers")


class DatabaseHelpers:

    @staticmethod
    def record_individual_actions(
        username: str,
        action_type: str,
        count: int,
        account_id: Optional[int] = None,
        session_id: Optional[int] = None
    ) -> bool:
        return InstagramWorkflowStateService.record_individual_actions(
            username=username,
            action_type=action_type,
            count=count,
            account_id=account_id,
            session_id=session_id,
        )
    
    @staticmethod
    def is_profile_already_processed(
        username: str,
        account_id: Optional[int] = None,
        hours_limit: int = 1440  # 24h par défaut
    ) -> bool:
        return InstagramWorkflowStateService.is_profile_already_processed(
            username=username,
            account_id=account_id,
            hours_limit=hours_limit,
        )
    
    @staticmethod
    def mark_profile_as_processed(
        username: str,
        source: str,
        account_id: Optional[int] = None,
        session_id: Optional[int] = None
    ) -> bool:
        return InstagramWorkflowStateService.mark_profile_as_processed(
            username=username,
            source=source,
            account_id=account_id,
            session_id=session_id,
        )
    
    @staticmethod
    def record_filtered_profile(
        username: str,
        reason: str,
        source_type: str,
        source_name: str,
        account_id: Optional[int] = None,
        session_id: Optional[int] = None
    ) -> bool:
        return InstagramWorkflowStateService.record_filtered_profile(
            username=username,
            reason=reason,
            source_type=source_type,
            source_name=source_name,
            account_id=account_id,
            session_id=session_id,
        )
    
    @staticmethod
    def is_profile_filtered(
        username: str,
        account_id: Optional[int] = None
    ) -> bool:
        return InstagramWorkflowStateService.is_profile_filtered(
            username=username,
            account_id=account_id,
        )
    
    @staticmethod
    def is_profile_skippable(
        username: str,
        account_id: Optional[int] = None,
        hours_limit: int = 1440
    ) -> tuple[bool, str]:
        """
        Vérifie si un profil doit être skippé (déjà traité OU déjà filtré).
        
        Returns:
            tuple[bool, str]: (should_skip, reason)
        """
        return InstagramWorkflowStateService.is_profile_skippable(
            username=username,
            account_id=account_id,
            hours_limit=hours_limit,
        )
    
    # ============================================
    # HASHTAG POST TRACKING
    # ============================================
    
    @staticmethod
    def is_hashtag_post_processed(
        hashtag: str,
        post_author: str,
        post_caption_hash: str = None,
        account_id: Optional[int] = None,
        hours_limit: int = 168  # 7 days
    ) -> bool:
        """
        Vérifie si un post hashtag a déjà été traité.
        
        Args:
            hashtag: Le hashtag (avec ou sans #)
            post_author: Username de l'auteur du post
            post_caption_hash: Hash de la caption pour unicité
            account_id: ID du compte bot
            hours_limit: Fenêtre de temps en heures
            
        Returns:
            True si le post a déjà été traité
        """
        return InstagramHashtagPostService.is_processed(
            hashtag=hashtag,
            post_author=post_author,
            post_caption_hash=post_caption_hash,
            account_id=account_id,
            hours_limit=hours_limit,
        )
    
    @staticmethod
    def record_hashtag_post_processed(
        hashtag: str,
        post_author: str,
        post_caption_hash: str = None,
        post_caption_preview: str = None,
        likes_count: int = None,
        comments_count: int = None,
        likers_processed: int = 0,
        interactions_made: int = 0,
        account_id: Optional[int] = None
    ) -> bool:
        """
        Enregistre un post hashtag comme traité.
        
        Args:
            hashtag: Le hashtag (avec ou sans #)
            post_author: Username de l'auteur du post
            post_caption_hash: Hash de la caption
            post_caption_preview: Aperçu de la caption (100 premiers chars)
            likes_count: Nombre de likes
            comments_count: Nombre de commentaires
            likers_processed: Nombre de likers traités
            interactions_made: Nombre d'interactions réussies
            account_id: ID du compte bot
            
        Returns:
            True si enregistré avec succès
        """
        return InstagramHashtagPostService.record_processed(
            hashtag=hashtag,
            post_author=post_author,
            post_caption_hash=post_caption_hash,
            post_caption_preview=post_caption_preview,
            likes_count=likes_count,
            comments_count=comments_count,
            likers_processed=likers_processed,
            interactions_made=interactions_made,
            account_id=account_id,
        )
    
    # ============================================
    # UNFOLLOW DECISION HELPERS
    # ============================================
    
    @staticmethod
    def has_bot_follow_record(username: str, account_id: int) -> bool:
        """
        Check if this username was originally followed by the bot.
        Queries interaction_history for a FOLLOW action by this account targeting this username.
        
        Args:
            username: Target username to check
            account_id: The bot account ID
            
        Returns:
            True if a FOLLOW record exists for this user by this account
        """
        try:
            from taktik.core.database.local.service import get_local_database
            local_db = get_local_database()
            conn = local_db._get_connection()
            
            # Look up the profile_id for this username
            cursor = conn.execute(
                "SELECT profile_id FROM instagram_profiles WHERE username = ? COLLATE NOCASE",
                (username,)
            )
            row = cursor.fetchone()
            if not row:
                return False
            
            profile_id = row['profile_id'] if isinstance(row, dict) else row[0]
            
            # Check if a FOLLOW interaction exists
            cursor = conn.execute(
                """SELECT 1 FROM interaction_history 
                   WHERE account_id = ? AND profile_id = ? AND interaction_type = 'FOLLOW' AND success = 1
                   LIMIT 1""",
                (account_id, profile_id)
            )
            return cursor.fetchone() is not None
            
        except Exception as e:
            log.debug(f"Error checking bot follow record for @{username}: {e}")
            return False
    
    @staticmethod
    def get_days_since_follow(username: str, account_id: int) -> Optional[int]:
        """
        Get the number of days since the bot followed this username.
        
        Args:
            username: Target username
            account_id: The bot account ID
            
        Returns:
            Number of days since follow, or None if no record found
        """
        try:
            from datetime import datetime
            from taktik.core.database.local.service import get_local_database
            local_db = get_local_database()
            conn = local_db._get_connection()
            
            # Look up the profile_id
            cursor = conn.execute(
                "SELECT profile_id FROM instagram_profiles WHERE username = ? COLLATE NOCASE",
                (username,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            profile_id = row['profile_id'] if isinstance(row, dict) else row[0]
            
            # Get the most recent FOLLOW interaction time
            cursor = conn.execute(
                """SELECT interaction_time FROM interaction_history 
                   WHERE account_id = ? AND profile_id = ? AND interaction_type = 'FOLLOW' AND success = 1
                   ORDER BY interaction_time DESC LIMIT 1""",
                (account_id, profile_id)
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            follow_time_str = row['interaction_time'] if isinstance(row, dict) else row[0]
            if not follow_time_str:
                return None
            
            follow_time = datetime.fromisoformat(follow_time_str)
            delta = datetime.now() - follow_time
            return delta.days
            
        except Exception as e:
            log.debug(f"Error getting days since follow for @{username}: {e}")
            return None
    
    @staticmethod
    def generate_caption_hash(caption: str) -> str:
        """
        Génère un hash court de la caption pour identification.
        Utilise les 100 premiers caractères normalisés.
        """
        return InstagramHashtagPostService.generate_caption_hash(caption)

    # ============================================
    # FOLLOWING SYNC HELPERS
    # ============================================

    @staticmethod
    def sync_following_upsert(
        username: str,
        display_name: str,
        account_id: int,
        followed_by_bot: bool = False,
        source: str = 'sync',
    ) -> str:
        """
        Insert or update a following entry in following_sync.

        Returns:
            'new' if inserted, 'updated' if already existed
        """
        try:
            from taktik.core.database.local.service import get_local_database
            local_db = get_local_database()
            conn = local_db._get_connection()

            cursor = conn.execute(
                "SELECT id FROM following_sync WHERE account_id = ? AND username = ? COLLATE NOCASE",
                (account_id, username)
            )
            existing = cursor.fetchone()

            if existing:
                conn.execute(
                    """UPDATE following_sync
                       SET display_name = ?, last_seen_at = datetime('now'),
                           followed_by_bot = ?, source = ?
                       WHERE account_id = ? AND username = ? COLLATE NOCASE""",
                    (display_name, int(followed_by_bot), source, account_id, username)
                )
                conn.commit()
                return 'updated'
            else:
                conn.execute(
                    """INSERT INTO following_sync
                       (account_id, username, display_name, followed_by_bot, source)
                       VALUES (?, ?, ?, ?, ?)""",
                    (account_id, username, display_name, int(followed_by_bot), source)
                )
                conn.commit()
                return 'new'

        except Exception as e:
            log.debug(f"Error in sync_following_upsert for @{username}: {e}")
            return 'error'

    @staticmethod
    def get_following_sync_usernames(account_id: int) -> set:
        """
        Get the set of all known following usernames for an account.

        Returns:
            Set of lowercase usernames
        """
        try:
            from taktik.core.database.local.service import get_local_database
            local_db = get_local_database()
            conn = local_db._get_connection()

            cursor = conn.execute(
                "SELECT username FROM following_sync WHERE account_id = ? AND unfollowed_at IS NULL",
                (account_id,)
            )
            return {row[0].lower() for row in cursor.fetchall()}

        except Exception as e:
            log.debug(f"Error in get_following_sync_usernames: {e}")
            return set()

    @staticmethod
    def mark_not_follower_back(username: str, account_id: int) -> None:
        """Mark a following as NOT following back (is_follower_back = 0)."""
        try:
            from taktik.core.database.local.service import get_local_database
            local_db = get_local_database()
            conn = local_db._get_connection()
            conn.execute(
                """UPDATE following_sync SET is_follower_back = 0, last_seen_at = datetime('now')
                   WHERE account_id = ? AND username = ? COLLATE NOCASE""",
                (account_id, username)
            )
            conn.commit()
        except Exception as e:
            log.debug(f"Error in mark_not_follower_back for @{username}: {e}")

    @staticmethod
    def mark_follower_back(username: str, account_id: int) -> None:
        """Mark a following as following back (is_follower_back = 1)."""
        try:
            from taktik.core.database.local.service import get_local_database
            local_db = get_local_database()
            conn = local_db._get_connection()
            conn.execute(
                """UPDATE following_sync SET is_follower_back = 1, last_seen_at = datetime('now')
                   WHERE account_id = ? AND username = ? COLLATE NOCASE""",
                (account_id, username)
            )
            conn.commit()
        except Exception as e:
            log.debug(f"Error in mark_follower_back for @{username}: {e}")

    @staticmethod
    def mark_unfollowed(username: str, account_id: int) -> None:
        """Mark a following as unfollowed (sets unfollowed_at timestamp)."""
        try:
            from taktik.core.database.local.service import get_local_database
            local_db = get_local_database()
            conn = local_db._get_connection()
            conn.execute(
                """UPDATE following_sync SET unfollowed_at = datetime('now')
                   WHERE account_id = ? AND username = ? COLLATE NOCASE""",
                (account_id, username)
            )
            conn.commit()
        except Exception as e:
            log.debug(f"Error in mark_unfollowed for @{username}: {e}")


    # ============================================
    # FOLLOWERS SYNC HELPERS
    # ============================================

    @staticmethod
    def sync_follower_upsert(
        username: str,
        account_id: int,
        display_name: str = '',
        is_following_back: bool = None,
        source: str = 'sync',
    ) -> str:
        """
        Insert or update a follower entry in followers_sync.

        Returns:
            'new' if inserted, 'updated' if already existed
        """
        try:
            from taktik.core.database.local.service import get_local_database
            local_db = get_local_database()
            conn = local_db._get_connection()

            cursor = conn.execute(
                "SELECT id FROM followers_sync WHERE account_id = ? AND username = ? COLLATE NOCASE",
                (account_id, username)
            )
            existing = cursor.fetchone()

            following_back_val = None if is_following_back is None else int(is_following_back)

            if existing:
                conn.execute(
                    """UPDATE followers_sync
                       SET display_name = COALESCE(NULLIF(?, ''), display_name),
                           last_seen_at = datetime('now'),
                           is_following_back = COALESCE(?, is_following_back),
                           source = ?
                       WHERE account_id = ? AND username = ? COLLATE NOCASE""",
                    (display_name, following_back_val, source, account_id, username)
                )
                conn.commit()
                return 'updated'
            else:
                conn.execute(
                    """INSERT INTO followers_sync
                       (account_id, username, display_name, is_following_back, source)
                       VALUES (?, ?, ?, ?, ?)""",
                    (account_id, username, display_name, following_back_val, source)
                )
                conn.commit()
                return 'new'

        except Exception as e:
            log.debug(f"Error in sync_follower_upsert for @{username}: {e}")
            return 'error'

    @staticmethod
    def get_followers_sync_usernames(account_id: int) -> set:
        """
        Get the set of all known follower usernames for an account.

        Returns:
            Set of lowercase usernames
        """
        try:
            from taktik.core.database.local.service import get_local_database
            local_db = get_local_database()
            conn = local_db._get_connection()

            cursor = conn.execute(
                "SELECT username FROM followers_sync WHERE account_id = ?",
                (account_id,)
            )
            return {row[0].lower() for row in cursor.fetchall()}

        except Exception as e:
            log.debug(f"Error in get_followers_sync_usernames: {e}")
            return set()


__all__ = ['DatabaseHelpers']
