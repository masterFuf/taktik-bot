"""Assemble the full Agent workflow registry for standalone CLI use.

The bot must stay usable without the desktop app. In practice every capability added over the last
months landed as a bridge plus an Agent handler, and the CLI menus were never extended — so 40
workflows had a runnable handler and none could be reached by its canonical id from the terminal.

The handlers are the right entry point: AGENTS.md makes them the branchable unit, and they take
their device by injection instead of opening a connection. This module is the missing piece — it
hands each registrar what it asks for and returns one registry the CLI can list and resolve.

Registrars do not share a signature: some want `device_manager`, some `device`, some both `device`
and `device_id`, Threads wants a `startup_provider`. Their needs are read from the signature rather
than hardcoded, so adding a platform does not mean editing a mapping here.

A registrar that fails is reported, never silent: a platform missing from the menu because its
import broke is exactly the kind of gap this module exists to end.
"""
from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass
from typing import Any, Callable

from taktik.core.agent.kernel.registry import WorkflowRegistry


#: (label, module path, registrar name). Label is what the operator sees when one fails.
REGISTRARS: tuple[tuple[str, str, str], ...] = (
    ("Instagram automation", "taktik.core.social_media.instagram.workflows.core.agent_handler",
     "register_instagram_automation_handlers"),
    ("Instagram account", "taktik.core.social_media.instagram.workflows.management.agent_handler",
     "register_instagram_account_handlers"),
    ("Instagram scraping", "taktik.core.social_media.instagram.workflows.scraping.agent_handler",
     "register_instagram_scraping_handlers"),
    ("TikTok For You", "taktik.core.social_media.tiktok.actions.business.workflows.for_you.agent_handler",
     "register_tiktok_for_you_handlers"),
    ("TikTok search/hashtag/target", "taktik.core.social_media.tiktok.actions.business.workflows.search.agent_handler",
     "register_tiktok_search_handlers"),
    ("TikTok followers", "taktik.core.social_media.tiktok.actions.business.workflows.followers.agent_handler",
     "register_tiktok_followers_handlers"),
    ("TikTok DM", "taktik.core.social_media.tiktok.actions.business.workflows.dm.agent_handler",
     "register_tiktok_dm_handlers"),
    ("TikTok DM outreach", "taktik.core.social_media.tiktok.actions.business.workflows.dm.agent_handler",
     "register_tiktok_dm_outreach_handlers"),
    ("TikTok unfollow", "taktik.core.social_media.tiktok.actions.business.workflows.unfollow.agent_handler",
     "register_tiktok_unfollow_handlers"),
    ("TikTok scraping", "taktik.core.social_media.tiktok.actions.business.workflows.scraping.agent_handler",
     "register_tiktok_scraping_handlers"),
    ("TikTok account", "taktik.core.social_media.tiktok.workflows.management.agent_handler",
     "register_tiktok_account_handlers"),
    ("TikTok publish", "taktik.core.social_media.tiktok.workflows.publish.agent_handler",
     "register_tiktok_publish_handlers"),
    ("Threads automation", "taktik.core.social_media.threads.workflows.agent_handler",
     "register_threads_automation_handlers"),
    ("Gmail account", "taktik.core.app.email.gmail.workflows.agent_handler",
     "register_gmail_account_handlers"),
    ("YouTube account", "taktik.core.social_media.youtube.workflows.account.agent_handler",
     "register_youtube_account_handlers"),
    ("YouTube publish", "taktik.core.social_media.youtube.workflows.publish.agent_handler",
     "register_youtube_publish_handlers"),
)


@dataclass
class RegistryBuild:
    """A registry plus what could not be registered, so the CLI can be honest about gaps."""

    registry: WorkflowRegistry
    failures: list[tuple[str, str]]

    @property
    def workflow_ids(self) -> list[str]:
        return sorted(getattr(self.registry, "_handlers", {}))

    def ids_for(self, platform: str) -> list[str]:
        prefix = f"{platform}."
        return [i for i in self.workflow_ids if i.startswith(prefix)]

    @property
    def platforms(self) -> list[str]:
        return sorted({i.split(".", 1)[0] for i in self.workflow_ids})


def build_registry(
    *,
    device: Any = None,
    device_id: str = "",
    device_manager: Any = None,
    notifier: Any = None,
    startup_provider: Callable[..., Any] | None = None,
) -> RegistryBuild:
    """Register every available handler, returning the registry and any registrar failures."""
    registry = WorkflowRegistry()
    failures: list[tuple[str, str]] = []

    supplied: dict[str, Any] = {
        "device": device,
        "device_id": device_id,
        "device_manager": device_manager if device_manager is not None else device,
        "notifier": notifier,
        "ai_notifier": notifier,
        "startup_provider": startup_provider,
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
            register(registry, **kwargs)
        except Exception as exc:  # noqa: BLE001 - one broken platform must not hide the others
            failures.append((label, f"{type(exc).__name__}: {exc}"))

    return RegistryBuild(registry=registry, failures=failures)


__all__ = ["REGISTRARS", "RegistryBuild", "build_registry"]
