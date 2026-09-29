"""The one launcher of a Taktik Agent session on Instagram, and its Agent handler.

`run_instagram_agent` is what the desktop bridge (`taktik_agent_bridge`) calls, what `taktik agent
run` calls and what the handler registered as `instagram.engagement.taktik_agent` calls: read the
payload (`payload.py`), refuse a session the Agent cannot decide in before the phone is touched,
restart Instagram cleanly, then run `TaktikAgentWorkflow` with the warmup budget of the account's
day (`WarmupBudget`, the automation's counter, on the caps of the file). What differs between the
hosts is injected:
- `connect(package_name) -> AgentRuntime`: the device ready for the flow, on the Instagram the payload
  names (`packageName`, a clone; None: the installed one): the bridges' clone-aware, facade-wrapped
  device, with the selector overrides of the installed version, and its clean restart through
  `AppService`.
- `ipc`: where the status lines and the Agent's events go (the bridge's stdout, the CLI's console).
- `ai_service_factory(*, api_key, ipc, vision_model, text_model)`: how the AI service is built.
- `on_workflow(workflow)`: told the workflow once built (the bridge registers it for its stop
  signal).
- `instagram_ai_key() -> str | None` (handler only): the OpenRouter key when the payload brings
  none (the CLI's; the desktop puts it in the payload).
The CLI used to launch Instagram hot on the raw device: no restart, no clone package, the baseline
selectors whatever the installed version.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

from taktik.core.kernel.contracts import WorkflowInvocation
from taktik.core.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.instagram.workflows.agent.payload import taktik_agent_request_from_payload
from taktik.core.social_media.instagram.workflows.core.startup import package_name_from_payload
from taktik.core.social_media.instagram.workflows.management.session.warmup_budget import WarmupBudget


INSTAGRAM_AGENT_WORKFLOW_ID = "instagram.engagement.taktik_agent"

#: The Agent decides with the model: a session without an OpenRouter key cannot run.
NO_AI_KEY = "Could not initialize AI service — check API key"


@dataclass
class AgentRuntime:
    """What the host prepared for one Agent session."""

    device_manager: Any
    restart: Callable[[], Any]


RuntimeProvider = Callable[[Optional[str]], AgentRuntime]
AIServiceFactory = Callable[..., Any]
AIKeyProvider = Callable[[], Optional[str]]


def run_instagram_agent(
    config: Mapping[str, Any],
    *,
    connect: RuntimeProvider,
    ipc=None,
    ai_service_factory: Optional[AIServiceFactory] = None,
    on_workflow: Optional[Callable[[Any], None]] = None,
) -> dict:
    """Refuse a session without an OpenRouter key, restart Instagram, then run a Taktik Agent session."""
    request = taktik_agent_request_from_payload(config)
    if not request.openrouter_api_key:
        # The status line the workflow printed once Instagram was open, now before it is touched.
        announce = getattr(ipc, "agent_status", None)
        if callable(announce):
            announce("error", NO_AI_KEY, message_key="agentStatusErrNoAi")
        raise ValueError(NO_AI_KEY)
    runtime = connect(package_name_from_payload(config))
    if ipc is not None:
        ipc.status("launching", "Restarting Instagram…")
    # Clean restart (force-stop + launch) for a consistent initial state, like every other bridge.
    if not runtime.restart():
        if ipc is not None:
            ipc.error("Failed to launch Instagram", error_code="INSTAGRAM_LAUNCH_FAILED")
        return {"success": False, "error": "Failed to launch Instagram"}
    if ipc is not None:
        ipc.status("instagram_ready", "Instagram launched successfully")

    # Imported here, by name: the app's config contract test follows the config into the class.
    from taktik.core.social_media.instagram.workflows.agent.autopilot import TaktikAgentWorkflow

    workflow = TaktikAgentWorkflow(
        device_manager=runtime.device_manager,
        config=config,
        ipc=ipc,
        ai_service_factory=ai_service_factory,
        # Handed in, not built by the session: the Agent kernel does not import a platform.
        warmup=WarmupBudget(request.warmup_policy),
    )
    if on_workflow is not None:
        on_workflow(workflow)
    return workflow.run()


def build_instagram_agent_handler(
    *,
    instagram_agent_runtime: Optional[RuntimeProvider] = None,
    instagram_agent_ai_service_factory: Optional[AIServiceFactory] = None,
    instagram_ai_key: Optional[AIKeyProvider] = None,
    notifier=None,
) -> WorkflowHandler:
    """Build an injectable Taktik Agent handler: the launcher, on the runtime the host prepares."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        if instagram_agent_runtime is None:
            raise RuntimeError("Taktik Agent needs a connected device")
        config = dict(payload)
        config.update(invocation.params)
        if not config.get("openrouter_api_key") and instagram_ai_key is not None:
            key = instagram_ai_key()
            if key:
                config["openrouter_api_key"] = key
        return run_instagram_agent(
            config,
            connect=instagram_agent_runtime,
            ipc=notifier,
            ai_service_factory=instagram_agent_ai_service_factory,
        )

    return handler


def register_instagram_agent_handlers(
    registry: WorkflowRegistry,
    *,
    instagram_agent_runtime: Optional[RuntimeProvider] = None,
    instagram_agent_ai_service_factory: Optional[AIServiceFactory] = None,
    instagram_ai_key: Optional[AIKeyProvider] = None,
    notifier=None,
) -> WorkflowRegistry:
    """Register the Taktik Agent handler into an injected Agent registry."""
    registry.register(
        INSTAGRAM_AGENT_WORKFLOW_ID,
        build_instagram_agent_handler(
            instagram_agent_runtime=instagram_agent_runtime,
            instagram_agent_ai_service_factory=instagram_agent_ai_service_factory,
            instagram_ai_key=instagram_ai_key,
            notifier=notifier,
        ),
    )
    return registry


__all__ = [
    "AgentRuntime",
    "INSTAGRAM_AGENT_WORKFLOW_ID",
    "NO_AI_KEY",
    "build_instagram_agent_handler",
    "register_instagram_agent_handlers",
    "run_instagram_agent",
]
