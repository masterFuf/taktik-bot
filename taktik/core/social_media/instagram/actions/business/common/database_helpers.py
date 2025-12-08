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
            # Accéder directement à l'API client
            db_service = get_db_service()
            if hasattr(db_service, 'api_client'):
                is_filtered = db_service.api_client.is_profile_filtered(username, account_id)
                if is_filtered:
                    log.debug(f"🚫 Profil @{username} déjà filtré")
                return is_filtered
            return False
            
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


__all__ = ['DatabaseHelpers']
