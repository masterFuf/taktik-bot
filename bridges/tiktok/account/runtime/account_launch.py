"""The TikTok account bridge's path to its launcher, `run_tiktok_account`.

The payload is read the launcher's way (`tiktok_account_params`), and the run gets the bridge's
device, its app lifecycle and the stdout IPC as notifier.
"""

from __future__ import annotations

from typing import Any, Optional

from bridges.tiktok.runtime.ipc import _ipc, send_error
from taktik.core.social_media.tiktok.workflows.management.agent_handler import (
    run_tiktok_account,
    tiktok_account_params,
)


class TikTokAccountLaunchMixin:
    """Read an account payload and run it through the launcher."""

    def _account_params(self, workflow_id: str) -> Optional[dict[str, Any]]:
        try:
            return tiktok_account_params(workflow_id, self.config)
        except ValueError as exc:
            send_error(str(exc))
            return None

    def _launch_account(self, device, workflow_id: str, params: dict[str, Any]) -> dict[str, Any]:
        return run_tiktok_account(
            workflow_id,
            params,
            device=device,
            device_id=self.device_id,
            app=self._app,
            notifier=_ipc,
        )


__all__ = ["TikTokAccountLaunchMixin"]
