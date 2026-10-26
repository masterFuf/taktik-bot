"""What the CLI injects into the Instagram automation handlers, so a terminal run starts like a
desktop run.

Same clean restart as the desktop bridge (`start_instagram_session` on the core's `AppService`,
the one app lifecycle of the bot), same selector version overrides, same AI hooks; the events go to
the log instead of stdout. When the payload brings no AI key, the CLI's own (`ai_key.py`: the
environment, the key typed at launch, the saved one), which the launch already made sure of.
What stays with the desktop process: the uiautomator2 repair, the IP rotation, the media capture,
the per-profile decision round trip. A scraping run is restarted the same way: the desktop restarts
Instagram before it launches its scraping bridge.

The host holds the run's phone (`CliPhone`) without connecting it: each method below is a
`connect` a launcher calls once it has read and validated its payload, and the phone connects
there, on the first call. A refused payload never connects.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

from loguru import logger

from taktik.cli.hosts.ai_key import ai_block_with_key
from taktik.core.ai.openrouter_policy import PROVIDER_OPENROUTER
from taktik.cli.hosts.phone import CliPhone
from taktik.core.social_media.instagram.workflows.common.startup import InstagramStartError


def _log(level: str, message: str) -> None:
    getattr(logger, level if level in ("info", "warning", "error", "debug", "success") else "info")(message)


def _log_dm_event(payload: Mapping[str, Any]) -> None:
    # Never the content of a message: the type, the username and the progress only.
    conversation = payload.get("conversation") or {}
    username = payload.get("username") or conversation.get("username") or payload.get("account_username") or ""
    progress = f" {payload.get('current')}/{payload.get('total')}" if payload.get("current") is not None else ""
    logger.info(f"[DM] {payload.get('type', 'event')} {username}{progress}".rstrip())


class CliInstagramHost:
    """The CLI's phone, as the Instagram launchers' host: it connects when a launcher asks."""

    def __init__(self, phone: CliPhone):
        self.phone = phone
        self.device_id = phone.device_id
        self.app = None

    def _app_for(self, package_name: Optional[str]):
        from taktik.core.shared.device.app_manager import AppService
        from taktik.core.shared.device.connected_device import ConnectedDevice

        # The CLI's manager, connected: the app service takes it as the connection it holds.
        connection = ConnectedDevice(self.phone.connect(), self.device_id)
        return AppService(connection, platform="instagram", package_override=package_name)

    def start(self, package_name: Optional[str]) -> bool:
        """The clean restart before the run, on the run's package (a clone when it names one)."""
        from taktik.core.social_media.instagram.workflows.common.startup import start_instagram_session

        self.app = self._app_for(package_name)
        return start_instagram_session(self.app)

    def run_phone(self, package_name: Optional[str]):
        """The phone an automation or a scraping run drives (`InstagramRunPhone`), connected now, with
        the clean restart on the run's package and the installed version for the selector overrides."""
        from taktik.core.social_media.instagram.workflows.common.startup import InstagramRunPhone

        return InstagramRunPhone(
            device_manager=self.phone.connect(),
            start=lambda: self.start(package_name),
            installed_version=self.installed_version,
        )

    def account_app(self, package_name: Optional[str]):
        """The app lifecycle an account flow restarts, or keeps on its current screen."""
        return self._app_for(package_name)

    def task_device(self, package_name: Optional[str]):
        """The phone after the clean restart of the task's Instagram (a clone when it names one), as
        the task bridge restarts it: a one-shot starts from the feed."""
        if not self.start(package_name):
            raise InstagramStartError("Instagram did not start cleanly; the task was not started")
        return getattr(self.phone.connect(), "device", None)

    def installed_version(self) -> Optional[str]:
        """The installed Instagram version, for the selector overrides."""
        app = self.app or self._app_for(None)
        return app.get_installed_version()

    def cold_dm_runtime(self, package_name: Optional[str]):
        """The device a cold DM run drives, prepared by the Instagram device base the cold DM bridge
        uses too: the clone-aware proxy, the device facade, the selector overrides of the installed
        version and the clean restart through `AppService`, on the device the CLI already connected."""
        from taktik.core.shared.device.connected_device import on_connected_device
        from taktik.core.social_media.instagram.workflows.common.device import InstagramDeviceBase
        from taktik.core.social_media.instagram.workflows.cold_dm.agent_handler import ColdDmRuntime

        base = on_connected_device(InstagramDeviceBase(self.device_id, package_name=package_name),
                                   self.phone.connect(), self.device_id)
        return ColdDmRuntime(
            device=base.device,
            device_manager=base.device_manager,
            restart=base.restart,
        )

    def agent_runtime(self, package_name: Optional[str]):
        """The device a Taktik Agent session drives, prepared by the Instagram device base its bridge
        uses too, and its clean restart, on the device the CLI already connected."""
        from taktik.core.shared.device.connected_device import on_connected_device
        from taktik.core.social_media.instagram.workflows.common.device import InstagramDeviceBase
        from taktik.core.social_media.instagram.workflows.agent.agent_handler import AgentRuntime

        base = on_connected_device(InstagramDeviceBase(self.device_id, package_name=package_name),
                                   self.phone.connect(), self.device_id)
        # The app service's restart, which says whether Instagram came back, as the bridge uses it.
        return AgentRuntime(device_manager=base.device_manager, restart=base._app.restart)

    def dm_runtime(self, package_name: Optional[str]):
        """The DM inbox runtime the desktop's DM bridge connects too (`InstagramDMRuntime`: the core
        runtime on the Instagram device, with the Taktik Keyboard and the clean restart), on the
        device the CLI already connected. A read's events go to the log."""
        from taktik.core.shared.device.connected_device import on_connected_device
        from taktik.core.social_media.instagram.workflows.dm.runtime import InstagramDMRuntime

        runtime = on_connected_device(InstagramDMRuntime(self.device_id, package_name=package_name),
                                      self.phone.connect(), self.device_id)
        runtime.dm_events = _log_dm_event
        return runtime

    def notifications_runtime(self, package_name: Optional[str]):
        """The device the notifications bridge connects too (`InstagramDeviceBase`: clone-aware,
        and its clean restart), on the device the CLI already connected; the launcher restarts
        Instagram when the command asks for it (a scan)."""
        from taktik.core.shared.device.connected_device import on_connected_device
        from taktik.core.social_media.instagram.workflows.common.device import InstagramDeviceBase

        return on_connected_device(InstagramDeviceBase(self.device_id, package_name=package_name),
                                   self.phone.connect(), self.device_id)


def cli_instagram_scraping_ai_service(*, api_key: str, provider: str = PROVIDER_OPENROUTER, ipc=None,
                                      vision_model: str = None, text_model: str = None,
                                      niche_taxonomy: dict = None):
    """The AI service a scraping run builds: the core's, as the bridge's factory builds it
    (no `ai_spend`: nothing reads it for this run)."""
    from taktik.core.ai.factory import build_ai_service

    return build_ai_service(api_key=api_key, provider=provider, ipc=ipc, vision_model=vision_model,
                            text_model=text_model, niche_taxonomy=niche_taxonomy,
                            report_spend=False)


def cli_instagram_agent_ai_service_factory(*, api_key: str, provider: str = PROVIDER_OPENROUTER, ipc=None,
                                            vision_model: str = None, text_model: str = None):
    """The AI service a Taktik Agent session builds (its key: the config's or the environment's):
    the core's, as the bridge's factory builds it; no premium taxonomy in standalone, no `ai_spend`."""
    from taktik.core.ai.factory import build_ai_service

    return build_ai_service(api_key=api_key, provider=provider, ipc=ipc, vision_model=vision_model,
                            text_model=text_model, report_spend=False)


def cli_instagram_ai_service(ai_config: Mapping[str, Any]):
    """The AI service a run asks for, with the CLI's key if the run brings none. None when the run does not
    ask for the AI; a run that asks and has no key is refused (`missing_ai_key`)."""
    ai_config = ai_block_with_key(ai_config)
    if ai_config is None:
        return None

    from taktik.core.ai.factory import create_ai_service

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
    gets its key first (asked for at a terminal, `MissingAIKeyError` otherwise).

    `device_manager` is the phone of the command, connected (a menu) or not (`_choose_phone`): the
    launcher connects it once it has read its payload (`handler_on_phone`)."""
    from taktik.cli.hosts.ai_key import ensure_ai_key, is_interactive
    from taktik.cli.hosts.registry import build_registry, handler_on_phone
    from taktik.core.kernel.contracts import WorkflowInvocation
    from taktik.core.shared.diagnostics.run_start import begin_run

    ensure_ai_key(workflow_id, payload, interactive=is_interactive())

    build = build_registry(device_manager=device_manager, device_id=device_id)
    handler = handler_on_phone(build, workflow_id, CliPhone(device_manager, device_id))
    invocation = WorkflowInvocation(platform="instagram", workflow_id=workflow_id, params={})
    # The main menu serves one run after another: this one starts without the latch of the one before.
    begin_run()
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


def run_instagram_account_payload(device_manager: Any, device_id: str, workflow_id: str,
                                  payload: Mapping[str, Any]) -> dict:
    """Run an account flow (`instagram.account.login`, `logout`, `change_language`...)."""
    return _run_through_handler(device_manager, device_id, workflow_id, payload)


def run_instagram_cold_dm_payload(device_manager: Any, device_id: str, payload: Mapping[str, Any]) -> dict:
    """Run a Cold DM page payload (`instagram.engagement.coldDm`)."""
    return _run_through_handler(device_manager, device_id, "instagram.engagement.coldDm", payload)


__all__ = [
    "CliInstagramHost",
    "cli_instagram_agent_ai_service_factory",
    "cli_instagram_ai_service",
    "cli_instagram_scraping_ai_service",
    "is_internal_workflow_format",
    "run_instagram_account_payload",
    "run_instagram_cold_dm_payload",
    "run_instagram_dm_payload",
    "run_instagram_payload",
    "run_instagram_scraping_payload",
]
