"""Legacy Instagram database helper shim.

This module remains in the platform package for backward compatibility, but new
database-backed workflow bookkeeping must be owned by `taktik.core.database`.
"""

from typing import Optional

from taktik.core.database.instagram_follow_graph import InstagramFollowGraphService
from taktik.core.database.instagram_hashtag_posts import InstagramHashtagPostService
from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService


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
        return InstagramFollowGraphService.has_bot_follow_record(
            username=username,
            account_id=account_id,
        )
    
    @staticmethod
    def get_days_since_follow(username: str, account_id: int) -> Optional[int]:
        return InstagramFollowGraphService.get_days_since_follow(
            username=username,
            account_id=account_id,
        )
    
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
        return InstagramFollowGraphService.sync_following_upsert(
            username=username,
            display_name=display_name,
            account_id=account_id,
            followed_by_bot=followed_by_bot,
            source=source,
        )

    @staticmethod
    def get_following_sync_usernames(account_id: int) -> set:
        return InstagramFollowGraphService.get_following_sync_usernames(account_id=account_id)

    @staticmethod
    def mark_not_follower_back(username: str, account_id: int) -> None:
        InstagramFollowGraphService.mark_not_follower_back(
            username=username,
            account_id=account_id,
        )

    @staticmethod
    def mark_follower_back(username: str, account_id: int) -> None:
        InstagramFollowGraphService.mark_follower_back(
            username=username,
            account_id=account_id,
        )

    @staticmethod
    def mark_unfollowed(username: str, account_id: int) -> None:
        InstagramFollowGraphService.mark_unfollowed(
            username=username,
            account_id=account_id,
        )


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
        return InstagramFollowGraphService.sync_follower_upsert(
            username=username,
            account_id=account_id,
            display_name=display_name,
            is_following_back=is_following_back,
            source=source,
        )

    @staticmethod
    def get_followers_sync_usernames(account_id: int) -> set:
        return InstagramFollowGraphService.get_followers_sync_usernames(account_id=account_id)


__all__ = ['DatabaseHelpers']
