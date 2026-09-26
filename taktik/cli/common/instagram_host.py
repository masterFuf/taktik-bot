"""What the CLI injects into the Instagram automation handlers, so a terminal run starts like a
desktop run.

Same clean restart as the desktop bridge (`start_instagram_session` on the bridges' `AppService`,
the one app lifecycle of the bot), same selector version overrides, same AI hooks; the events go to
the log instead of stdout. When the payload brings no AI key, the CLI's own (`ai_key.py`: the
environment, the key typed at launch, the saved one), which the launch already made sure of.
What stays with the desktop process: the uiautomator2 repair, the IP rotation, the media capture,
the per-profile decision round trip. A scraping run is restarted the same way: the desktop restarts
Instagram before it launches its scraping bridge.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Mapping, Optional

from loguru import logger

from taktik.cli.common.ai_key import OPENROUTER_KEY_ENV, resolve_openrouter_key


def _log(level: str, message: str) -> None:
    getattr(logger, level if level in ("info", "warning", "error", "debug", "success") else "info")(message)


class _ConnectedDevice:
    """The CLI's connected manager, as the connection the bridges' Instagram base expects."""

    def __init__(self, device_manager, device_id):
        self.device_manager = device_manager
        self.device_id = device_id
        self._device = getattr(device_manager, "device", None)

    @property
    def device(self):
        return self._device

    @property
    def screen_size(self):
        from bridges.common.device.screen import read_screen_size

        return read_screen_size(self._device)

    def connect(self) -> bool:
        return self._device is not None


def _on_connected_device(base, device_manager, device_id: str):
    """Connect a bridges' Instagram base on the device the CLI already connected: the clone-aware
    proxy, the device facade and the selector overrides of the installed version, as a bridge."""
    base._connection = _ConnectedDevice(device_manager, device_id)
    if not base.connect():
        raise RuntimeError(f"No connected device for {device_id}")
    return base


def _log_dm_event(payload: Mapping[str, Any]) -> None:
    # Never the content of a message: the type, the username and the progress only.
    conversation = payload.get("conversation") or {}
    username = payload.get("username") or conversation.get("username") or payload.get("account_username") or ""
    progress = f" {payload.get('current')}/{payload.get('total')}" if payload.get("current") is not None else ""
    logger.info(f"[DM] {payload.get('type', 'event')} {username}{progress}".rstrip())


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

    def cold_dm_runtime(self, package_name: Optional[str]):
        """The device a cold DM run drives, prepared by the bridges' own Instagram base: the
        clone-aware proxy, the device facade, the selector overrides of the installed version and
        the clean restart through `AppService`, on the device the CLI already connected."""
        from bridges.common.input.keyboard import KeyboardService
        from bridges.instagram.runtime.bridge import InstagramBridgeBase
        from taktik.core.social_media.instagram.workflows.cold_dm.agent_handler import ColdDmRuntime

        base = _on_connected_device(InstagramBridgeBase(self.device_id, package_name=package_name),
                                    self.device_manager, self.device_id)
        return ColdDmRuntime(
            device=base.device,
            device_manager=base.device_manager,
            keyboard=KeyboardService(self.device_id),
            restart=base.restart,
        )

    def agent_runtime(self, package_name: Optional[str]):
        """The device a Taktik Agent session drives, prepared by the bridges' own Instagram base,
        and its clean restart, on the device the CLI already connected."""
        from bridges.instagram.runtime.bridge import InstagramBridgeBase
        from taktik.core.social_media.instagram.workflows.agent.agent_handler import AgentRuntime

        base = _on_connected_device(InstagramBridgeBase(self.device_id, package_name=package_name),
                                    self.device_manager, self.device_id)
        # The app service's restart, which says whether Instagram came back, as the bridge uses it.
        return AgentRuntime(device_manager=base.device_manager, restart=base._app.restart)

    def dm_runtime(self, package_name: Optional[str]):
        """The DM inbox runtime of the desktop's DM bridge (`DMBridge`: the core runtime on the
        bridges' Instagram device, with the Taktik Keyboard and the clean restart), on the device
        the CLI already connected. A read's events go to the log."""
        from bridges.instagram.engagement.runtime.dm.bridge import DMBridge

        runtime = _on_connected_device(DMBridge(self.device_id, package_name=package_name),
                                       self.device_manager, self.device_id)
        runtime.dm_events = _log_dm_event
        return runtime


def _with_key(ai_config: Mapping[str, Any]) -> Optional[dict]:
    """The run's `ai` block with a key, the CLI's if the run brings none; None when AI is off or no
    key is available."""
    ai_config = dict(ai_config or {})
    if not ai_config.get("enabled"):
        return None

    if not ai_config.get("openrouterApiKey"):
        key = cli_openrouter_key()
        if not key:
            return None
        ai_config["openrouterApiKey"] = key
    return ai_config


def cli_openrouter_key() -> Optional[str]:
    """The CLI's OpenRouter key, for a run that asks for AI without bringing one."""
    key = resolve_openrouter_key()
    if not key:
        logger.warning(f"AI requested but no OpenRouter key ({OPENROUTER_KEY_ENV}): this run goes on without AI")
        return None
    return key


def cli_instagram_scraping_ai_service(*, api_key: str, ipc=None, vision_model: str = None,
                                      text_model: str = None, niche_taxonomy: dict = None):
    """The AI service a scraping run builds: the core's, as the bridge's factory builds it."""
    from taktik.core.app.ai.factory import build_ai_service

    return build_ai_service(api_key=api_key, ipc=ipc, vision_model=vision_model,
                            text_model=text_model, niche_taxonomy=niche_taxonomy)


def cli_instagram_agent_ai_service_factory(*, api_key: str, ipc=None, vision_model: str = None,
                                            text_model: str = None):
    """The AI service a Taktik Agent session builds (its key: the config's or the environment's):
    the core's, as the bridge's factory builds it; no premium taxonomy in standalone."""
    from taktik.core.app.ai.factory import build_ai_service

    return build_ai_service(api_key=api_key, ipc=ipc, vision_model=vision_model, text_model=text_model)


def cli_instagram_ai_service(ai_config: Mapping[str, Any]):
    """The AI service a run asks for, with the CLI's key if the run brings none. None when no
    service can be built: the run goes on without AI."""
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


def _run_through_handler(device_manager: Any, device_id: str, workflow_id: str,
                         payload: Mapping[str, Any]) -> dict:
    """Run a page payload through the handler registered as `workflow_id`: the same path as
    `taktik workflows run <workflow_id>` and as the desktop bridge's launcher. A run that uses AI
    gets its key first (asked for at a terminal, `MissingAIKeyError` otherwise)."""
    from taktik.cli.common.ai_key import ensure_ai_key, is_interactive
    from taktik.cli.common.registry_builder import build_registry
    from taktik.core.agent.kernel.contracts import WorkflowInvocation

    ensure_ai_key(workflow_id, payload, interactive=is_interactive())

    build = build_registry(device=getattr(device_manager, "device", None), device_id=device_id,
                           device_manager=device_manager)
    handler = build.registry.resolve(workflow_id)
    invocation = WorkflowInvocation(platform="instagram", workflow_id=workflow_id, params={})
    return handler(invocation, {"deviceId": device_id, **dict(payload)})


def run_instagram_payload(device_manager: Any, device_id: str, payload: Mapping[str, Any]) -> dict:
    """Run an automation page payload (`instagram.automation.<workflowType>`)."""
    return _run_through_handler(device_manager, device_id,
                                f"instagram.automation.{payload.get('workflowType')}", payload)


def run_instagram_scraping_payload(device_manager: Any, device_id: str, payload: Mapping[str, Any]) -> dict:
    """Run a Scraping page payload (`instagram.scraping.<type>`)."""
    return _run_through_handler(device_manager, device_id, f"instagram.scraping.{payload.get('type')}", payload)


def run_instagram_dm_payload(device_manager: Any, device_id: str, workflow_id: str,
                             payload: Mapping[str, Any]) -> dict:
    """Run a DM command (`instagram.engagement.dm_read` or `dm_send`)."""
    return _run_through_handler(device_manager, device_id, workflow_id, payload)


def run_instagram_cold_dm_payload(device_manager: Any, device_id: str, payload: Mapping[str, Any]) -> dict:
    """Run a Cold DM page payload (`instagram.engagement.coldDm`)."""
    return _run_through_handler(device_manager, device_id, "instagram.engagement.coldDm", payload)


__all__ = [
    "CliInstagramHost",
    "OPENROUTER_KEY_ENV",
    "cli_instagram_agent_ai_service_factory",
    "cli_instagram_ai_service",
    "cli_instagram_scraping_ai_service",
    "cli_openrouter_key",
    "is_internal_workflow_format",
    "run_instagram_cold_dm_payload",
    "run_instagram_dm_payload",
    "run_instagram_payload",
    "run_instagram_scraping_payload",
]
