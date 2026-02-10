from typing import Optional
from loguru import logger
from taktik.core.database import get_db_service

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
        log.debug(f"🔍 [DEBUG] record_individual_actions - username: {username}, type: {action_type}, count: {count}")
        
        if not account_id:
            log.warning(f"⚠️ account_id manquant - impossible d'enregistrer {action_type} pour @{username}")
            return False
        
        success_count = 0
        
        try:
            for i in range(count):
                content = f"Action {action_type} sur profil @{username}"
                success = get_db_service().record_interaction(
                    account_id=account_id,
                    username=username,
                    interaction_type=action_type,
                    success=True,
                    content=content,
                    session_id=session_id
                )
                
                if success:
                    success_count += 1
                    log.debug(f"✅ Action {action_type} #{i+1}/{count} enregistrée pour @{username}")
                else:
                    log.warning(f"⚠️ Échec enregistrement {action_type} #{i+1}/{count} pour @{username}")
            
            log.debug(f"📊 {success_count}/{count} actions {action_type} enregistrées pour @{username}")
            return success_count > 0
            
        except Exception as e:
            log.error(f"❌ Erreur enregistrement actions {action_type} pour @{username}: {e}")
            return False
    
    @staticmethod
    def is_profile_already_processed(
        username: str,
        account_id: Optional[int] = None,
        hours_limit: int = 1440  # 24h par défaut
    ) -> bool:
        if not account_id:
            return False
        
        try:
            is_processed = get_db_service().is_profile_processed(
                account_id=account_id,
                username=username,
                hours_limit=hours_limit
            )
            
            if is_processed:
                log.debug(f"🔄 Profil @{username} déjà traité (dernières {hours_limit}h)")
            
            return is_processed
            
        except Exception as e:
            log.error(f"❌ Erreur vérification profil @{username}: {e}")
            return False
    
    @staticmethod
    def mark_profile_as_processed(
        username: str,
        source: str,
        account_id: Optional[int] = None,
        session_id: Optional[int] = None
    ) -> bool:
        if not account_id:
            log.warning(f"⚠️ account_id manquant - impossible de marquer @{username}")
            return False
        
        try:
            visit_notes = source
            get_db_service().mark_profile_as_processed(
                account_id=account_id,
                username=username,
                notes=visit_notes,
                session_id=session_id
            )
            log.debug(f"✅ @{username} marqué comme traité (source: {source})")
            return True
            
        except Exception as e:
            log.error(f"❌ Erreur marquage @{username}: {e}")
            return False
    
    @staticmethod
    def record_filtered_profile(
        username: str,
        reason: str,
        source_type: str,
        source_name: str,
        account_id: Optional[int] = None,
        session_id: Optional[int] = None
    ) -> bool:
        if not account_id:
            log.warning(f"⚠️ account_id manquant - impossible d'enregistrer filtrage de @{username}")
            return False
        
        try:
            success = get_db_service().record_filtered_profile(
                account_id=account_id,
                username=username,
                reason=reason,
                source_type=source_type,
                source_name=source_name,
                session_id=session_id
            )
            
            if success:
                log.debug(f"✅ Profil filtré @{username} enregistré: {reason}")
            else:
                log.warning(f"⚠️ Échec enregistrement filtrage @{username}")
            
            return success
            
        except Exception as e:
            log.error(f"❌ Erreur enregistrement filtrage @{username}: {e}")
            return False
    
    @staticmethod
    def is_profile_filtered(
        username: str,
        account_id: Optional[int] = None
    ) -> bool:
        """Vérifie si un profil a déjà été filtré pour ce compte."""
        if not account_id:
            return False
        
        try:
            is_filtered = get_db_service().is_profile_filtered(username, account_id)
            if is_filtered:
                log.debug(f"🚫 Profil @{username} déjà filtré")
            return is_filtered
            
        except Exception as e:
            log.debug(f"Erreur vérification filtrage @{username}: {e}")
            return False
    
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
        if not account_id:
            return False, ""
        
        # Vérifier si déjà traité (interagi)
        if DatabaseHelpers.is_profile_already_processed(username, account_id, hours_limit):
            return True, "already_processed"
        
        # Vérifier si déjà filtré
        if DatabaseHelpers.is_profile_filtered(username, account_id):
            return True, "already_filtered"
        
        return False, ""
    
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
        if not account_id:
            return False
        
        try:
            from taktik.core.database.local.service import get_local_database
            local_db = get_local_database()
            
            is_processed = local_db.is_hashtag_post_processed(
                account_id=account_id,
                hashtag=hashtag,
                post_author=post_author,
                post_caption_hash=post_caption_hash,
                hours_limit=hours_limit
            )
            
            if is_processed:
                log.debug(f"📋 Post #{hashtag} by @{post_author} already processed")
            
            return is_processed
            
        except Exception as e:
            log.error(f"❌ Error checking hashtag post: {e}")
            return False
    
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
        if not account_id:
            log.warning("⚠️ account_id manquant - impossible d'enregistrer le post hashtag")
            return False
        
        try:
            from taktik.core.database.local.service import get_local_database
            local_db = get_local_database()
            
            success = local_db.record_processed_hashtag_post(
                account_id=account_id,
                hashtag=hashtag,
                post_author=post_author,
                post_caption_hash=post_caption_hash,
                post_caption_preview=post_caption_preview,
                likes_count=likes_count,
                comments_count=comments_count,
                likers_processed=likers_processed,
                interactions_made=interactions_made
            )
            
            if success:
                log.debug(f"✅ Post #{hashtag} by @{post_author} recorded as processed")
            
            return success
            
        except Exception as e:
            log.error(f"❌ Error recording hashtag post: {e}")
            return False
    
    @staticmethod
    def generate_caption_hash(caption: str) -> str:
        """
        Génère un hash court de la caption pour identification.
        Utilise les 100 premiers caractères normalisés.
        """
        import hashlib
        if not caption:
            return "empty"
        
        # Normaliser: lowercase, strip, premiers 100 chars
        normalized = caption.lower().strip()[:100]
        # Hash MD5 tronqué à 16 chars
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()[:16]


__all__ = ['DatabaseHelpers']
