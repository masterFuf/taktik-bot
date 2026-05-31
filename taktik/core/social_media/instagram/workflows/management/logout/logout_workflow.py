"""
Workflow de déconnexion Instagram.

Orchestration simple : un seul appel à `InstagramLogout.logout()`,
sans retries (la déconnexion est idempotente).
"""

from typing import Dict, Any
from loguru import logger

from ....auth.logout import InstagramLogout
from ...support.workflow_helpers import WorkflowHelpers


class LogoutWorkflow:
    """Workflow complet de déconnexion Instagram."""

    def __init__(self, device, device_id: str):
        self.device = device
        self.device_id = device_id
        self.logger = logger.bind(module="instagram-logout-workflow")

        self.logout_manager = InstagramLogout(device, device_id)
        self.helpers = WorkflowHelpers(device)

    def execute(self) -> Dict[str, Any]:
        """
        Exécute le workflow de déconnexion.

        Returns:
            {
                'success': bool,
                'message': str,
                'error_type': Optional[str]
            }
        """
        self.logger.info("🚀 Starting logout workflow")

        result: Dict[str, Any] = {
            'success': False,
            'message': '',
            'error_type': None,
        }

        logout_result = self.logout_manager.logout()

        result['success'] = logout_result.success
        result['message'] = logout_result.message
        result['error_type'] = logout_result.error_type

        if result['success']:
            self.logger.success(f"✅ Logout workflow completed: {result['message']}")
        else:
            self.logger.error(f"❌ Logout workflow failed: {result['message']}")

        return result
