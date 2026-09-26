"""The one launcher of a Taktik Agent session on Instagram, and its Agent handler.

`run_instagram_agent` is what the desktop bridge (`taktik_agent_bridge`) calls, what `taktik agent
run` calls and what the handler registered as `instagram.engagement.taktik_agent` calls: restart
Instagram cleanly, then run `TaktikAgentWorkflow` (which reads its own config). What differs
between the hosts is injected:
- `device_manager` and `restart`: the device ready for the flow (the bridges' clone-aware,
  facade-wrapped device, with the selector overrides of the installed version) and its clean
  restart through `AppService`.
- `ipc`: where the status lines and the Agent's events go (the bridge's stdout, the CLI's console).
- `ai_service_factory(*, api_key, ipc, vision_model, text_model)`: how the AI service is built.
- `on_workflow(workflow)`: told the workflow once built (the bridge registers it for its stop
  signal).
The CLI used to launch Instagram hot on the raw device: no restart, no clone package, the baseline
selectors whatever the installed version.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry


INSTAGRAM_AGENT_WORKFLOW_ID = "instagram.engagement.taktik_agent"


@dataclass
class AgentRuntime:
    """What the host prepared for one Agent session."""

    device_manager: Any
    restart: Callable[[], Any]


RuntimeProvider = Callable[[Optional[str]], AgentRuntime]
AIServiceFactory = Callable[..., Any]


def run_instagram_agent(
    config: Mapping[str, Any],
    *,
    device_manager,
    restart: Callable[[], Any],
    ipc=None,
    ai_service_factory: Optional[AIServiceFactory] = None,
    on_workflow: Optional[Callable[[Any], None]] = None,
) -> dict:
    """Restart Instagram, then run a Taktik Agent session with `config`."""
    if ipc is not None:
        ipc.status("launching", "Restarting Instagram…")
    # Clean restart (force-stop + launch) for a consistent initial state, like every other bridge.
    if not restart():
        if ipc is not None:
            ipc.error("Failed to launch Instagram", error_code="INSTAGRAM_LAUNCH_FAILED")
        return {"success": False, "error": "Failed to launch Instagram"}
    if ipc is not None:
        ipc.status("instagram_ready", "Instagram launched successfully")

    # Imported here, by name: the app's config contract test follows the config into the class.
    from taktik.core.agent.scenarios.instagram_feed_autopilot import TaktikAgentWorkflow

    workflow = TaktikAgentWorkflow(
        device_manager=device_manager,
        config=config,
        ipc=ipc,
        ai_service_factory=ai_service_factory,
    )
    if on_workflow is not None:
        on_workflow(workflow)
    return workflow.run()


def build_instagram_agent_handler(
    *,
    instagram_agent_runtime: Optional[RuntimeProvider] = None,
    instagram_agent_ai_service_factory: Optional[AIServiceFactory] = None,
    notifier=None,
) -> WorkflowHandler:
    """Build an injectable Taktik Agent handler: the launcher, on the runtime the host prepares."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        if instagram_agent_runtime is None:
            raise RuntimeError("Taktik Agent needs a connected device")
        config = dict(payload)
        config.update(invocation.params)
        runtime = instagram_agent_runtime(config.get("packageName"))
        return run_instagram_agent(
            config,
            device_manager=runtime.device_manager,
            restart=runtime.restart,
            ipc=notifier,
            ai_service_factory=instagram_agent_ai_service_factory,
        )

    return handler


def register_instagram_agent_handlers(
    registry: WorkflowRegistry,
    *,
    instagram_agent_runtime: Optional[RuntimeProvider] = None,
    instagram_agent_ai_service_factory: Optional[AIServiceFactory] = None,
    notifier=None,
) -> WorkflowRegistry:
    """Register the Taktik Agent handler into an injected Agent registry."""
    registry.register(
        INSTAGRAM_AGENT_WORKFLOW_ID,
        build_instagram_agent_handler(
            instagram_agent_runtime=instagram_agent_runtime,
            instagram_agent_ai_service_factory=instagram_agent_ai_service_factory,
            notifier=notifier,
        ),
    )
    return registry


__all__ = [
    "AgentRuntime",
    "INSTAGRAM_AGENT_WORKFLOW_ID",
    "build_instagram_agent_handler",
    "register_instagram_agent_handlers",
    "run_instagram_agent",
]
