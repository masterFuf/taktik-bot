"""The one launcher of a TikTok notifications pass, and its Agent handler.

`run_tiktok_notifications` is what the desktop bridge calls and what the handler registered as
`tiktok.automation.notifications` (the CLI) calls. What differs between hosts is injected:
- `tiktok_startup() -> TikTokStartup`: clean restart, language, account; supplies the device and
  the account the notifications are recorded under.
- `notifier`: where the pass reports (the bridge's stdout IPC; the log otherwise).
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.tiktok.actions.business.workflows._internal.agent_runtime import (
    merge_invocation_payload,
)
from taktik.core.social_media.tiktok.actions.business.workflows.notifications.payload import (
    notifications_settings_from_payload,
)


TIKTOK_NOTIFICATIONS_WORKFLOW_ID = "tiktok.automation.notifications"
StartupProvider = Callable[[], Any]


def run_tiktok_notifications(
    payload: Any,
    *,
    device=None,
    notifier=None,
    tiktok_startup: Optional[StartupProvider] = None,
) -> dict[str, Any]:
    """Start, then run one notifications pass from a payload."""
    from taktik.core.social_media.tiktok.actions.business.workflows.notifications.workflow import (
        run_notifications_pass,
    )
    from taktik.core.social_media.tiktok.workflows.runtime.notifier import LoggingWorkflowNotifier

    settings = notifications_settings_from_payload(payload)
    run_device = device
    # The phone's own profile only: the pass has never taken the account from the app.
    bot_username = None
    if tiktok_startup is not None:
        started = tiktok_startup()
        run_device = started.device
        bot_username = started.bot_username

    return run_notifications_pass(
        run_device,
        settings,
        bot_username=bot_username,
        notifier=notifier if notifier is not None else LoggingWorkflowNotifier(),
    )


def build_tiktok_notifications_handler(
    *,
    device=None,
    notifier=None,
    tiktok_startup: Optional[StartupProvider] = None,
) -> WorkflowHandler:
    """Build the notifications handler for the Agent runtime."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        return run_tiktok_notifications(
            merge_invocation_payload(invocation, payload),
            device=device,
            notifier=notifier,
            tiktok_startup=tiktok_startup,
        )

    return handler


def register_tiktok_notifications_handlers(
    registry: WorkflowRegistry,
    *,
    device=None,
    notifier=None,
    tiktok_startup: Optional[StartupProvider] = None,
) -> WorkflowRegistry:
    """Register the TikTok notifications handler into an injected Agent registry."""
    registry.register(
        TIKTOK_NOTIFICATIONS_WORKFLOW_ID,
        build_tiktok_notifications_handler(device=device, notifier=notifier, tiktok_startup=tiktok_startup),
    )
    return registry


__all__ = [
    "TIKTOK_NOTIFICATIONS_WORKFLOW_ID",
    "build_tiktok_notifications_handler",
    "register_tiktok_notifications_handlers",
    "run_tiktok_notifications",
]
