"""The one launcher of an Instagram cold DM run, and its Agent handler.

`run_instagram_cold_dm` is what the desktop bridge (`cold_dm_bridge`) calls and what the handler
registered as `instagram.engagement.coldDm` (the CLI) calls: read the Cold DM page's payload, then
run `ColdDMWorkflow`, the only cold DM engine. What differs between the hosts is injected:
- `runtime`: the device ready for the flow (the bridges' clone-aware, facade-wrapped device), its
  manager, the Taktik Keyboard service and the clean restart of Instagram.
- `progress(current, total, username)`: where the per-recipient progress goes (the bridge's stdout).
- `ai_ipc`: where the AI spend is reported (the bridge's stdout IPC).
- `instagram_ai_key() -> str | None`: the OpenRouter key when the payload brings none (the CLI's
  environment).
- `on_session_start(session_id)`: where the id of the run's session goes (the bridge's
  `session_start`, which the desktop needs to write the run's AI spend into the session).
No injected callable receives the whole payload, so the app's config contract test can still see
every key the bot reads.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

from loguru import logger

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.instagram.workflows.cold_dm.recipient_policy import ColdDmRecipientPolicy
from taktik.core.social_media.instagram.workflows.cold_dm.session import (
    close_cold_dm_session,
    open_cold_dm_session,
    session_account_id,
)


INSTAGRAM_COLD_DM_WORKFLOW_ID = "instagram.engagement.coldDm"


@dataclass
class ColdDmRuntime:
    """What the host prepared for one cold DM run."""

    device: Any
    device_manager: Any
    keyboard: Any
    restart: Optional[Callable[[], Any]] = None


RuntimeProvider = Callable[[Optional[str]], ColdDmRuntime]
ProgressCallback = Callable[..., None]
AIKeyProvider = Callable[[], Optional[str]]
WorkflowFactory = Callable[..., Any]
SessionStartCallback = Callable[[int], None]


def _default_workflow_factory() -> WorkflowFactory:
    # Resolved at call time, so the module's class is the one a run gets.
    from taktik.core.social_media.instagram.workflows.cold_dm import workflow

    return workflow.ColdDMWorkflow


def run_instagram_cold_dm(
    config: Mapping[str, Any],
    *,
    runtime: ColdDmRuntime,
    progress: Optional[ProgressCallback] = None,
    ai_ipc=None,
    instagram_ai_key: Optional[AIKeyProvider] = None,
    workflow_factory: Optional[WorkflowFactory] = None,
    on_session_start: Optional[SessionStartCallback] = None,
) -> dict[str, Any]:
    """Send the cold DMs a Cold DM page payload describes, as one session."""
    device_id = config.get("deviceId")
    recipients = config.get("recipients", [])
    messages = config.get("messages", [])
    delay_min = config.get("delayMin", 30)
    delay_max = config.get("delayMax", 60)
    max_dms = config.get("maxDmsPerSession", 50)
    account_id = config.get("accountId", 1)
    session_id = config.get("sessionId", device_id)
    ai_prompt = config.get("aiPrompt", "")
    openrouter_api_key = config.get("openrouterApiKey", "")

    # The page's and the scheduler node's « Ignorer les comptes privés / certifiés ». Absent
    # -> the behaviour the engine always had: private profiles skipped, certified ones not.
    recipient_policy = ColdDmRecipientPolicy(
        skip_private=config.get("skipPrivateAccounts", True) is not False,
        skip_verified=bool(config.get("skipVerifiedAccounts", False)),
    )

    message_mode = config.get("messageMode", "manual")
    if message_mode == "ai" and not openrouter_api_key and instagram_ai_key is not None:
        openrouter_api_key = instagram_ai_key() or ""
    if message_mode == "ai" and not openrouter_api_key:
        logger.warning("AI mode requested but no OpenRouter API key provided, falling back to manual messages")

    logger.info(f"Cold DM config: {len(recipients)} recipients, {len(messages)} messages, mode: {message_mode}")

    workflow = (workflow_factory or _default_workflow_factory())(
        runtime.device,
        runtime.device_manager,
        keyboard=runtime.keyboard,
        restart=runtime.restart,
        progress=progress,
        ai_ipc=ai_ipc,
    )

    run_session_id = open_cold_dm_session(session_account_id(config), recipients=recipients, config=config)
    if run_session_id is not None and on_session_start is not None:
        on_session_start(run_session_id)
    started = time.monotonic()
    try:
        result = workflow.run(
            recipients,
            messages,
            delay_min,
            delay_max,
            max_dms,
            account_id,
            session_id,
            ai_prompt,
            openrouter_api_key,
            recipient_policy=recipient_policy,
        )
    except BaseException as exc:
        close_cold_dm_session(run_session_id, duration_seconds=int(time.monotonic() - started), error=exc)
        raise
    close_cold_dm_session(run_session_id, duration_seconds=int(time.monotonic() - started), result=result)
    return result


def build_instagram_cold_dm_handler(
    *,
    instagram_cold_dm_runtime: Optional[RuntimeProvider] = None,
    instagram_ai_key: Optional[AIKeyProvider] = None,
    workflow_factory: Optional[WorkflowFactory] = None,
) -> WorkflowHandler:
    """Build an injectable cold DM handler: the launcher, on the runtime the host prepares."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        if instagram_cold_dm_runtime is None:
            raise RuntimeError("Instagram cold DM needs a connected device")
        config = dict(payload)
        config.update(invocation.params)
        if not config.get("recipients"):
            raise ValueError("Instagram cold DM requires recipients")
        return run_instagram_cold_dm(
            config,
            runtime=instagram_cold_dm_runtime(config.get("packageName")),
            instagram_ai_key=instagram_ai_key,
            workflow_factory=workflow_factory,
        )

    return handler


def register_instagram_cold_dm_handlers(
    registry: WorkflowRegistry,
    *,
    instagram_cold_dm_runtime: Optional[RuntimeProvider] = None,
    instagram_ai_key: Optional[AIKeyProvider] = None,
    workflow_factory: Optional[WorkflowFactory] = None,
) -> WorkflowRegistry:
    """Register the Instagram cold DM handler into an injected Agent registry."""
    registry.register(
        INSTAGRAM_COLD_DM_WORKFLOW_ID,
        build_instagram_cold_dm_handler(
            instagram_cold_dm_runtime=instagram_cold_dm_runtime,
            instagram_ai_key=instagram_ai_key,
            workflow_factory=workflow_factory,
        ),
    )
    return registry


__all__ = [
    "ColdDmRuntime",
    "INSTAGRAM_COLD_DM_WORKFLOW_ID",
    "build_instagram_cold_dm_handler",
    "register_instagram_cold_dm_handlers",
    "run_instagram_cold_dm",
]
