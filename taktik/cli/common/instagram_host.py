"""What the CLI injects into the Instagram automation handlers, so a terminal run starts like a
desktop run.

Same clean restart as the desktop bridge (`start_instagram_session` on the bridges' `AppService`,
the one app lifecycle of the bot), same selector version overrides, same AI hooks; the events go to
the log instead of stdout. The AI key comes from `OPENROUTER_API_KEY` when the payload brings none.
What stays with the desktop process: the uiautomator2 repair, the IP rotation, the media capture,
the per-profile decision round trip.
"""
from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any, Mapping, Optional

from loguru import logger

OPENROUTER_KEY_ENV = "OPENROUTER_API_KEY"


def _log(level: str, message: str) -> None:
    getattr(logger, level if level in ("info", "warning", "error", "debug", "success") else "info")(message)


class CliInstagramHost:
    """The CLI's connected device, as the Instagram launcher's host."""

    def __init__(self, device_manager: Any, device_id: str):
        self.device_manager = device_manager
        self.device_id = device_id
        self.app = None

    def _app_for(self, package_name: Optional[str]):
        from bridges.common.device.app_manager import AppService

        # The app service only reads these three from a connection; the CLI's manager is connected.
        connection = SimpleNamespace(
            device_manager=self.device_manager,
            device=getattr(self.device_manager, "device", None),
            device_id=self.device_id,
        )
        return AppService(connection, platform="instagram", package_override=package_name)

    def start(self, package_name: Optional[str]) -> bool:
        """The clean restart before the run, on the run's package (a clone when it names one)."""
        from taktik.core.social_media.instagram.workflows.core.startup import start_instagram_session

        self.app = self._app_for(package_name)
        return start_instagram_session(self.app)

    def installed_version(self) -> Optional[str]:
        """The installed Instagram version, for the selector overrides."""
        app = self.app or self._app_for(None)
        return app.get_installed_version()


def _with_key(ai_config: Mapping[str, Any]) -> Optional[dict]:
    """The run's `ai` block with a key, from the environment if the run brings none; None when AI
    is off or no key is available."""
    ai_config = dict(ai_config or {})
    if not ai_config.get("enabled"):
        return None

    if not ai_config.get("openrouterApiKey"):
        key = os.environ.get(OPENROUTER_KEY_ENV, "").strip()
        if not key:
            logger.warning(f"AI requested but {OPENROUTER_KEY_ENV} is not set: this run goes on without AI")
            return None
        ai_config["openrouterApiKey"] = key
    return ai_config


def cli_instagram_ai_service(ai_config: Mapping[str, Any]):
    """The AI service a run asks for, with the key from the environment if the run brings none.
    None when no service can be built: the run goes on without AI."""
    ai_config = _with_key(ai_config)
    if ai_config is None:
        return None

    from taktik.core.app.ai.factory import create_ai_service

    enabled, service = create_ai_service(
        ai_config=ai_config,
        log=_log,
        ready_message="AI mode enabled - Smart Comments / Profile Analysis / Post Analysis",
    )
    return service if enabled else None


#: Keys of the workflow's internal format, which the menus and `--config` files used to write.
_INTERNAL_FORMAT_KEYS = ("actions", "steps", "session_settings")


def is_internal_workflow_format(config: Mapping[str, Any]) -> bool:
    """True for a config written in the workflow's internal format rather than a page's."""
    return any(key in config for key in _INTERNAL_FORMAT_KEYS)


def run_instagram_payload(device_manager: Any, device_id: str, payload: Mapping[str, Any]) -> dict:
    """Run a page payload through the automation handler: the same path as
    `taktik workflows run instagram.automation.<type>` and as the desktop bridge's launcher."""
    from taktik.cli.common.registry_builder import build_registry
    from taktik.core.agent.kernel.contracts import WorkflowInvocation

    workflow_id = f"instagram.automation.{payload.get('workflowType')}"
    build = build_registry(device=getattr(device_manager, "device", None), device_id=device_id,
                           device_manager=device_manager)
    handler = build.registry.resolve(workflow_id)
    invocation = WorkflowInvocation(platform="instagram", workflow_id=workflow_id, params={})
    return handler(invocation, {"deviceId": device_id, **dict(payload)})


__all__ = [
    "CliInstagramHost",
    "OPENROUTER_KEY_ENV",
    "cli_instagram_ai_service",
    "is_internal_workflow_format",
    "run_instagram_payload",
]
