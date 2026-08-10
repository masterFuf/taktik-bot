"""
Workflow de login Instagram.

Orchestrates the full login process, including error handling, popups and
session persistence.
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
        Initialise the login workflow.
        
        Args:
            device: the device instance
            device_id: the device identifier
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
        Run the full login workflow.
        
        Args:
            username: Nom d'utilisateur, email ou numéro de téléphone
            password: the password
            max_retries: Nombre maximum de tentatives en cas d'échec
            save_session: save our own session record after a successful login
            use_saved_session: try to reuse one of our saved session records
            save_login_info_instagram: answer the app's own save-credentials popup
            
        Returns:
            Dict carrying the workflow result:
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
            
            # Attempt the login
            login_result = self.login_manager.login(
                username=username,
                password=password,
                save_session=save_session,
                use_saved_session=(use_saved_session and attempt == 1),
                save_login_info_instagram=save_login_info_instagram
            )
            
            # Analyse the result
            if login_result.success:
                result['success'] = True
                result['message'] = login_result.message
                result['session_saved'] = save_session
                
                self.logger.success(f"✅ Login successful for {username}")
                break
            
            # Handle the specific errors
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
            
            # Wait before the next attempt
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
    
