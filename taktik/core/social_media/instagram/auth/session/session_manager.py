"""
Gestionnaire de sessions Instagram.

Ce module gère la persistance des sessions de connexion pour éviter
de devoir se reconnecter à chaque fois.
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timedelta
from loguru import logger


class SessionManager:
    """Gestionnaire de sessions Instagram pour persistance des connexions."""
    
    def __init__(self, session_dir: Optional[str] = None):
        """
        Initialise le gestionnaire de sessions.
        
        Args:
            session_dir: Répertoire où stocker les sessions. 
                        Par défaut: ~/.taktik/sessions/
        """
        if session_dir is None:
            home = Path.home()
            session_dir = home / ".taktik" / "sessions"
        
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"📁 Session directory: {self.session_dir}")
    
    def save_session(
        self, 
        username: str, 
        device_id: str,
        session_data: Dict
    ) -> bool:
        """
        Sauvegarde une session de connexion.
        
        Args:
            username: Nom d'utilisateur Instagram
            device_id: ID du device (ADB ID)
            session_data: Données de session (cookies, tokens, etc.)
            
        Returns:
            True si sauvegarde réussie, False sinon
        """
        try:
            session_file = self._get_session_file(username, device_id)
            
            # Ajouter metadata
            session_data['metadata'] = {
                'username': username,
                'device_id': device_id,
                'created_at': datetime.now().isoformat(),
                'last_used': datetime.now().isoformat()
            }
            
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2)
            
            logger.success(f"✅ Session saved for {username} on device {device_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to save session: {e}")
            return False
    
    def load_session(
        self, 
        username: str, 
        device_id: str
    ) -> Optional[Dict]:
        """
        Charge une session de connexion existante.
        
        Args:
            username: Nom d'utilisateur Instagram
            device_id: ID du device (ADB ID)
            
        Returns:
            Données de session si trouvées et valides, None sinon
        """
        try:
            session_file = self._get_session_file(username, device_id)
            
            if not session_file.exists():
                logger.info(f"ℹ️ No session found for {username} on device {device_id}")
                return None
            
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            # Vérifier si la session est encore valide (< 30 jours)
            if self._is_session_expired(session_data):
                logger.warning(f"⚠️ Session expired for {username}")
                self.delete_session(username, device_id)
                return None
            
            # Mettre à jour last_used
            session_data['metadata']['last_used'] = datetime.now().isoformat()
            self.save_session(username, device_id, session_data)
            
            logger.success(f"✅ Session loaded for {username} on device {device_id}")
            return session_data
            
        except Exception as e:
            logger.error(f"❌ Failed to load session: {e}")
            return None
    
    def delete_session(self, username: str, device_id: str) -> bool:
        """
        Supprime une session de connexion.
        
        Args:
            username: Nom d'utilisateur Instagram
            device_id: ID du device (ADB ID)
            
        Returns:
            True si suppression réussie, False sinon
        """
        try:
            session_file = self._get_session_file(username, device_id)
            
            if session_file.exists():
                session_file.unlink()
                logger.success(f"✅ Session deleted for {username} on device {device_id}")
                return True
            else:
                logger.info(f"ℹ️ No session to delete for {username}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to delete session: {e}")
            return False
    
    def list_sessions(self) -> list:
        """
        Liste toutes les sessions sauvegardées.
        
        Returns:
            Liste de dictionnaires contenant les métadonnées des sessions
        """
        sessions = []
        
        try:
            for session_file in self.session_dir.glob("*.json"):
                with open(session_file, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                    if 'metadata' in session_data:
                        sessions.append(session_data['metadata'])
            
            return sessions
            
        except Exception as e:
            logger.error(f"❌ Failed to list sessions: {e}")
            return []
    
    def _get_session_file(self, username: str, device_id: str) -> Path:
        """
        Génère le chemin du fichier de session.
        
        Args:
            username: Nom d'utilisateur Instagram
            device_id: ID du device (ADB ID)
            
        Returns:
            Chemin du fichier de session
        """
        # Nettoyer les caractères spéciaux
        safe_username = "".join(c for c in username if c.isalnum() or c in "._-")
        safe_device = "".join(c for c in device_id if c.isalnum() or c in "._-")
        
        filename = f"{safe_username}_{safe_device}.json"
        return self.session_dir / filename
    
    def _is_session_expired(self, session_data: Dict) -> bool:
        """
        Vérifie si une session est expirée.
        
        Args:
            session_data: Données de session
            
        Returns:
            True si expirée, False sinon
        """
        try:
            if 'metadata' not in session_data:
                return True
            
            created_at = datetime.fromisoformat(session_data['metadata']['created_at'])
            expiration_date = created_at + timedelta(days=30)
            
            return datetime.now() > expiration_date
            
        except Exception as e:
            logger.error(f"❌ Failed to check session expiration: {e}")
            return True
    
    def cleanup_expired_sessions(self) -> int:
        """
        Nettoie toutes les sessions expirées.
        
        Returns:
            Nombre de sessions supprimées
        """
        deleted_count = 0
        
        try:
            for session_file in self.session_dir.glob("*.json"):
                with open(session_file, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                
                if self._is_session_expired(session_data):
                    session_file.unlink()
                    deleted_count += 1
                    logger.info(f"🗑️ Deleted expired session: {session_file.name}")
            
            if deleted_count > 0:
                logger.success(f"✅ Cleaned up {deleted_count} expired session(s)")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"❌ Failed to cleanup sessions: {e}")
            return deleted_count
