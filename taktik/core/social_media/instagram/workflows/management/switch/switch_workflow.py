"""
Workflow de changement de compte Instagram (switch).

Orchestration simple : un appel à `InstagramSwitchAccount.switch_to(target)`.
Le switch ne concerne que les comptes déjà connectés sur le device ; un compte
absent doit passer par le workflow Login.
"""

from typing import Any, Callable, Dict, Optional

from loguru import logger

from ....auth.switch import InstagramSwitchAccount


class SwitchAccountWorkflow:
    """Workflow complet de changement de compte Instagram."""

    def __init__(self, device, device_id: str, notifier: Optional[Callable[[str], None]] = None):
        self.device = device
        self.device_id = device_id
        self.logger = logger.bind(module="instagram-switch-workflow")
        self.switch_manager = InstagramSwitchAccount(device, device_id, notifier=notifier)

    def execute(self, target_username: str) -> Dict[str, Any]:
        """
        Exécute le switch vers ``target_username``.

        Returns:
            {
                'success': bool,
                'message': str,
                'error_type': Optional[str],
                'switched_to': Optional[str],
                'relogin_required': bool,
                'detected_accounts': list[str],
            }
        """
        self.logger.info(f"🚀 Starting switch-account workflow → @{target_username}")

        switch_result = self.switch_manager.switch_to(target_username)

        result: Dict[str, Any] = {
            'success': switch_result.success,
            'message': switch_result.message,
            'error_type': switch_result.error_type,
            'switched_to': switch_result.switched_to,
            'relogin_required': switch_result.relogin_required,
            'detected_accounts': switch_result.detected_accounts,
        }

        if result['success']:
            self.logger.success(f"✅ Switch workflow completed: {result['message']}")
        else:
            self.logger.error(f"❌ Switch workflow failed: {result['message']}")

        return result

    def list_accounts(self) -> Dict[str, Any]:
        """List the accounts logged in on the device (no logout). See InstagramSwitchAccount."""
        self.logger.info("📋 Listing connected accounts")
        accounts = self.switch_manager.list_accounts()
        return {
            'success': True,
            'accounts': accounts,
            'message': f"{len(accounts)} connected account(s)",
        }
