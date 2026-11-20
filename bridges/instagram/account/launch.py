"""The account bridge's path to its launcher, `run_instagram_account`.

The payload is read the launcher's way (`instagram_account_params`), and the run gets the
bridge's device, its app lifecycle and stdout for the start status.
"""

from __future__ import annotations

import sys
from typing import Any, Optional

from bridges.common.network import send_run_refusal
from bridges.instagram.common.ipc import send_error, send_status
from taktik.core.shared.diagnostics.run_halt import RunRefused
from taktik.core.social_media.instagram.workflows.account.agent_handler import (
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
        """The flow through the launcher. A phone its door refuses ends the bridge here, exit 1, on its
        coded `error` line: each flow reports any other failure as an uncoded error, which would hide
        the motive from the desktop (the TikTok session start does the same)."""
        try:
            return run_instagram_account(
                workflow_id,
                params,
                device=device,
                device_id=self.device_id,
                app=self._app,
                on_status=send_status,
                **narration,
            )
        except RunRefused as refused:
            send_run_refusal(refused, "Account")
            sys.exit(1)


__all__ = ["AccountLaunchMixin"]
