"""
Workflow de login Instagram.

Ce module orchestre le processus complet de connexion à Instagram,
incluant la gestion des erreurs, des popups et de la persistance de session.
"""

from typing import Optional, Dict, Any
from loguru import logger

from ....auth.login import InstagramLogin, LoginResult
from ....auth.session import SessionManager
from ...support.workflow_helpers import WorkflowHelpers


class LoginWorkflow:
    """Workflow complet de connexion Instagram."""
    
    def __init__(self, device, device_id: str):
        """
        Initialise le workflow de login.
        
        Args:
            device: Instance du device (uiautomator2)
            device_id: ID du device (ADB ID)
        """
        self.device = device
        self.device_id = device_id
        self.logger = logger.bind(module="instagram-login-workflow")
        
        # Composants
        self.login_manager = InstagramLogin(device, device_id)
        self.session_manager = SessionManager()
        self.helpers = WorkflowHelpers(device)
    
    def execute(
        self,
        username: str,
        password: str,
        max_retries: int = 3,
        save_session: bool = True,
        use_saved_session: bool = True,
        save_login_info_instagram: bool = False
    ) -> Dict[str, Any]:
        """
        Exécute le workflow de login complet.
        
        Args:
            username: Nom d'utilisateur, email ou numéro de téléphone
            password: Mot de passe
            max_retries: Nombre maximum de tentatives en cas d'échec
            save_session: Sauvegarder la session après connexion réussie (notre système)
            use_saved_session: Tenter d'utiliser une session sauvegardée (notre système)
            save_login_info_instagram: Sauvegarder les infos dans Instagram (popup Instagram)
            
        Returns:
            Dictionnaire avec le résultat du workflow:
            {
                'success': bool,
                'message': str,
                'username': str,
                'attempts': int,
                'session_saved': bool,
                'error_type': Optional[str]
            }
        """
        self.logger.info(f"🚀 Starting login workflow for {username}")
        
        result = {
            'success': False,
            'message': '',
            'username': username,
            'attempts': 0,
            'session_saved': False,
            'error_type': None
        }
        
        # Tentatives de connexion
        for attempt in range(1, max_retries + 1):
            result['attempts'] = attempt
            
            self.logger.info(f"🔄 Login attempt {attempt}/{max_retries}")
            
            # Tenter la connexion
            login_result = self.login_manager.login(
                username=username,
                password=password,
                save_session=save_session,
                use_saved_session=(use_saved_session and attempt == 1),
                save_login_info_instagram=save_login_info_instagram
            )
            
            # Analyser le résultat
            if login_result.success:
                result['success'] = True
                result['message'] = login_result.message
                result['session_saved'] = save_session
                
                self.logger.success(f"✅ Login successful for {username}")
                break
            
            # Gérer les erreurs spécifiques
            result['error_type'] = login_result.error_type
            result['message'] = login_result.message
            
            if login_result.requires_2fa:
                self.logger.warning("🔐 2FA required - stopping attempts")
                result['message'] = "2FA required (not yet implemented)"
                break
            
            if login_result.error_type == "credentials_error":
                self.logger.error("❌ Invalid credentials - stopping attempts")
                break
            
            if login_result.error_type == "suspicious_login":
                self.logger.warning("⚠️ Suspicious login - stopping attempts")
                break
            
            # Attendre avant la prochaine tentative
            if attempt < max_retries:
                self.logger.info(f"⏳ Waiting before retry...")
                import time
                time.sleep(3)
        
        # Log final
        if result['success']:
            self.logger.success(f"✅ Login workflow completed successfully for {username}")
        else:
            self.logger.error(
                f"❌ Login workflow failed for {username} after {result['attempts']} attempt(s): "
                f"{result['message']}"
            )
        
        return result
    
