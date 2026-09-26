"""The account bridge's path to its launcher, `run_instagram_account`.

The payload is read the launcher's way (`instagram_account_params`), and the run gets the
bridge's device, its app lifecycle and stdout for the start status.
"""

from __future__ import annotations

from typing import Any, Optional

from bridges.instagram.runtime.ipc import send_error, send_status
from taktik.core.social_media.instagram.workflows.management.agent_handler import (
    instagram_account_params,
    run_instagram_account,
)


class AccountLaunchMixin:
    """Read an account payload and run it through the launcher."""

    def _account_params(self, workflow_id: str) -> Optional[dict[str, Any]]:
        try:
            return instagram_account_params(workflow_id, self.config)
        except ValueError as exc:
            send_error(str(exc))
            return None

    def _launch_account(self, device, workflow_id: str, params: dict[str, Any], **narration) -> dict[str, Any]:
        return run_instagram_account(
            workflow_id,
            params,
            device=device,
            device_id=self.device_id,
            app=self._app,
            on_status=send_status,
            **narration,
        )


__all__ = ["AccountLaunchMixin"]
