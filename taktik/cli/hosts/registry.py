"""Assemble the full Agent workflow registry for standalone CLI use.

The bot must stay usable without the desktop app. In practice every capability added over the last
months landed as a bridge plus an Agent handler, and the CLI menus were never extended — so 40
workflows had a runnable handler and none could be reached by its canonical id from the terminal.

The handlers are the right entry point: AGENTS.md makes them the branchable unit, and they take
their device by injection instead of opening a connection. This module is the missing piece — it
hands each registrar what it asks for and returns one registry the CLI can list and resolve.

Registrars do not share a signature: some want a `connect` (the Instagram runs), some `device`, some
both `device` and `device_id`, Threads wants a `startup_provider`. Their needs are read from the
signature rather than hardcoded, so adding a platform does not mean editing a mapping here.

Building the registry never connects the phone. A launcher that takes a `connect` reads and
validates its payload, then calls it, and the phone connects there. A registrar that requires the
connected device itself, built on a phone not connected yet, is named in `built_without_device`:
`handler_on_phone` connects the phone before it hands over one of its handlers, whose launcher then
reads once the phone is connected. Every CLI door runs its workflow through `handler_on_phone`.

A registrar that fails is reported, never silent: a platform missing from the menu because its
import broke is exactly the kind of gap this module exists to end.
"""
from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from taktik.core.kernel.registry import WorkflowHandler, WorkflowRegistry


#: (label, module path, registrar name). Label is what the operator sees when one fails.
REGISTRARS: tuple[tuple[str, str, str], ...] = (
    ("Instagram automation", "taktik.core.social_media.instagram.workflows.automation.agent_handler",
     "register_instagram_automation_handlers"),
    ("Instagram account", "taktik.core.social_media.instagram.workflows.account.agent_handler",
     "register_instagram_account_handlers"),
    ("Instagram scraping", "taktik.core.social_media.instagram.workflows.scraping.agent_handler",
     "register_instagram_scraping_handlers"),
    ("Instagram cold DM", "taktik.core.social_media.instagram.workflows.cold_dm.agent_handler",
     "register_instagram_cold_dm_handlers"),
    ("Instagram DM", "taktik.core.social_media.instagram.workflows.dm.agent_handler",
     "register_instagram_dm_handlers"),
    ("Instagram notifications",
     "taktik.core.social_media.instagram.workflows.notifications.agent_handler",
     "register_instagram_notifications_handlers"),
    ("Taktik Agent (Instagram)", "taktik.core.social_media.instagram.workflows.agent.agent_handler",
     "register_instagram_agent_handlers"),
    ("Instagram tasks", "taktik.core.social_media.instagram.workflows.tasks.agent_handler",
     "register_instagram_task_handlers"),
    ("Instagram publish", "taktik.core.social_media.instagram.workflows.publish.agent_handler",
     "register_instagram_publish_handlers"),
    ("TikTok For You", "taktik.core.social_media.tiktok.workflows.automation.for_you.agent_handler",
     "register_tiktok_for_you_handlers"),
    ("TikTok hashtag", "taktik.core.social_media.tiktok.workflows.automation.search.agent_handler",
     "register_tiktok_search_handlers"),
    ("TikTok followers", "taktik.core.social_media.tiktok.workflows.automation.followers.agent_handler",
     "register_tiktok_followers_handlers"),
    ("TikTok target profiles",
     "taktik.core.social_media.tiktok.workflows.automation.target_profiles.agent_handler",
     "register_tiktok_target_profiles_handlers"),
    ("TikTok post URL", "taktik.core.social_media.tiktok.workflows.automation.post_url.agent_handler",
     "register_tiktok_post_url_handlers"),
    ("TikTok follow-graph sync",
     "taktik.core.social_media.tiktok.workflows.automation.sync_lists.agent_handler",
     "register_tiktok_sync_lists_handlers"),
    ("TikTok notifications",
     "taktik.core.social_media.tiktok.workflows.notifications.agent_handler",
     "register_tiktok_notifications_handlers"),
    ("TikTok DM", "taktik.core.social_media.tiktok.workflows.dm.agent_handler",
     "register_tiktok_dm_handlers"),
    ("TikTok DM outreach", "taktik.core.social_media.tiktok.workflows.dm.agent_handler",
     "register_tiktok_dm_outreach_handlers"),
    ("TikTok inbox", "taktik.core.social_media.tiktok.workflows.dm.inbox_agent_handler",
     "register_tiktok_inbox_handlers"),
    ("TikTok unfollow", "taktik.core.social_media.tiktok.workflows.automation.unfollow.agent_handler",
     "register_tiktok_unfollow_handlers"),
    ("TikTok scraping", "taktik.core.social_media.tiktok.workflows.scraping.agent_handler",
     "register_tiktok_scraping_handlers"),
    ("TikTok account", "taktik.core.social_media.tiktok.workflows.account.agent_handler",
     "register_tiktok_account_handlers"),
    ("TikTok publish", "taktik.core.social_media.tiktok.workflows.publish.agent_handler",
     "register_tiktok_publish_handlers"),
    ("Threads automation", "taktik.core.social_media.threads.workflows.agent_handler",
     "register_threads_automation_handlers"),
    ("Gmail account", "taktik.core.social_media.gmail.workflows.agent_handler",
     "register_gmail_account_handlers"),
    ("YouTube account", "taktik.core.social_media.youtube.workflows.account.agent_handler",
     "register_youtube_account_handlers"),
    ("YouTube publish", "taktik.core.social_media.youtube.workflows.publish.agent_handler",
     "register_youtube_publish_handlers"),
)


@dataclass
class RegistryBuild:
    """A registry plus what could not be registered, so the CLI can be honest about gaps.

    `built_without_device`: the workflows whose registrar takes the connected device itself (`device`,
    `device_manager`) rather than a callable that connects it, built here on a phone not connected yet:
    their handlers hold no device (`handler_on_phone` connects the phone and builds them again).
    """

    registry: WorkflowRegistry
    failures: list[tuple[str, str]]
    built_without_device: frozenset[str] = frozenset()

    @property
    def workflow_ids(self) -> list[str]:
        return sorted(getattr(self.registry, "_handlers", {}))

    def ids_for(self, platform: str) -> list[str]:
        prefix = f"{platform}."
        return [i for i in self.workflow_ids if i.startswith(prefix)]

    @property
    def platforms(self) -> list[str]:
        return sorted({i.split(".", 1)[0] for i in self.workflow_ids})


#: What a registrar takes that only a connected phone gives: the handlers it builds drive that device.
_CONNECTED_DEVICE_PARAMS = ("device", "device_manager")


def _takes_a_connected_device(params: Mapping[str, inspect.Parameter]) -> bool:
    """The registrar requires the connected device itself, not a callable that connects it."""
    return any(
        name in params and params[name].default is inspect.Parameter.empty
        for name in _CONNECTED_DEVICE_PARAMS
    )


def build_registry(
    *,
    device: Any = None,
    device_id: str = "",
    device_manager: Any = None,
    notifier: Any = None,
    startup_provider: Callable[..., Any] | None = None,
) -> RegistryBuild:
    """Register every available handler, returning the registry and any registrar failures.

    `device_manager` is the CLI's phone (a `DeviceManager`), connected or not: building the registry
    never connects it. Each host callable below connects it when a launcher calls it, once the
    launcher has read and validated its payload (`hosts/phone.py`). `device` is the connected device,
    the manager's own when it holds one; without a manager, `device` stands for both.
    """
    from taktik.cli.hosts.instagram import (
        CliInstagramHost,
        cli_instagram_agent_ai_service_factory,
        cli_instagram_ai_service,
        cli_instagram_scraping_ai_service,
        cli_openrouter_key,
    )
    from taktik.cli.hosts.phone import CliPhone
    from taktik.cli.hosts.tiktok import (
        cli_tiktok_account_app,
        cli_tiktok_ai_hooks,
        cli_tiktok_outreach_message_generator,
        cli_tiktok_startup,
        cli_tiktok_welcome_qualifier,
    )

    registry = WorkflowRegistry()
    failures: list[tuple[str, str]] = []
    built_without_device: set[str] = set()
    manager = device_manager if device_manager is not None else device
    phone = CliPhone(manager, device_id) if manager is not None else None
    if device is None and phone is not None and phone.connected:
        device = phone.device_manager.device
    instagram_host = CliInstagramHost(phone) if phone is not None else None

    supplied: dict[str, Any] = {
        "device": device,
        "device_id": device_id,
        "device_manager": manager,
        "notifier": notifier,
        "ai_notifier": notifier,
        "startup_provider": startup_provider,
        # TikTok handlers that take these start and hook a run the way the bridges do.
        "tiktok_startup": cli_tiktok_startup(phone) if phone is not None else None,
        "tiktok_ai_hooks": cli_tiktok_ai_hooks,
        # The account flows restart TikTok the way the account bridge does.
        "tiktok_account_app": cli_tiktok_account_app(phone) if phone is not None else None,
        "tiktok_welcome_qualifier": cli_tiktok_welcome_qualifier,
        "tiktok_outreach_message_generator": cli_tiktok_outreach_message_generator,
        # The Instagram automation and scraping runs start on the phone the way their bridges do.
        "instagram_connect": instagram_host.run_phone if instagram_host else None,
        # The account flows restart Instagram (or keep its screen) the way the account bridge does.
        "instagram_account_app": instagram_host.account_app if instagram_host else None,
        "instagram_ai_service": cli_instagram_ai_service,
        # The scraping handlers build their AI service from a key, the payload's or the environment's.
        "instagram_scraping_ai_service": cli_instagram_scraping_ai_service,
        "instagram_ai_key": cli_openrouter_key,
        # The cold DM run drives the device the way the cold DM bridge prepares it.
        "instagram_cold_dm_runtime": instagram_host.cold_dm_runtime if instagram_host else None,
        # The DM inbox runs on the DM bridge's own runtime.
        "instagram_dm_runtime": instagram_host.dm_runtime if instagram_host else None,
        # The notifications run connects the way its bridge connects.
        "instagram_notifications_runtime": instagram_host.notifications_runtime if instagram_host else None,
        # The Taktik Agent session starts the way its bridge starts it.
        "instagram_agent_runtime": instagram_host.agent_runtime if instagram_host else None,
        # A task (the story relay) starts from a clean restart of its Instagram, as its bridge does.
        "instagram_task_connect": instagram_host.task_device if instagram_host else None,
        "instagram_agent_ai_service_factory": cli_instagram_agent_ai_service_factory,
    }

    for label, module_path, func_name in REGISTRARS:
        try:
            module = importlib.import_module(module_path)
            register = getattr(module, func_name)
            params = inspect.signature(register).parameters
            kwargs = {
                name: supplied[name]
                for name, param in params.items()
                if param.kind is inspect.Parameter.KEYWORD_ONLY and name in supplied
                # Only fill what the registrar actually requires, or what we can meaningfully
                # provide; defaults it declares itself must stay in force.
                and (param.default is inspect.Parameter.empty or supplied[name] is not None)
            }
            before = set(registry.workflow_ids())
            register(registry, **kwargs)
            if device is None and _takes_a_connected_device(params):
                built_without_device |= set(registry.workflow_ids()) - before
        except Exception as exc:  # noqa: BLE001 - one broken platform must not hide the others
            failures.append((label, f"{type(exc).__name__}: {exc}"))

    return RegistryBuild(registry=registry, failures=failures,
                         built_without_device=frozenset(built_without_device))


def handler_on_phone(build: RegistryBuild, workflow_id: str, phone: Any) -> WorkflowHandler:
    """The handler that runs `workflow_id` on the CLI's `phone` (`CliPhone`), from `build`.

    A launcher that takes a `connect` connects the phone itself, after it has read and validated its
    payload: its handler is the one `build` holds. A workflow of `build.built_without_device` takes the
    connected device itself: the phone is connected now, and the registry built again on it. Raises
    `KeyError` for an id nobody registered, `PhoneNotConnectedError` when the phone does not connect.
    """
    if workflow_id not in build.built_without_device:
        return build.registry.resolve(workflow_id)
    manager = phone.connect()
    return build_registry(device_manager=manager, device_id=phone.device_id).registry.resolve(workflow_id)


__all__ = ["REGISTRARS", "RegistryBuild", "build_registry", "handler_on_phone"]
