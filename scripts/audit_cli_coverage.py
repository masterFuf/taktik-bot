"""Report which bot workflows the standalone CLI cannot reach.

The bot is meant to stay usable on its own, without the desktop app — that is the first rule of
AGENTS.md. In practice the desktop has been the only consumer for months, so capabilities landed
as bridges and Agent handlers while the CLI menus stayed where they were.

This audit answers one question with evidence rather than memory: for every workflow the bot can
actually execute, can a CLI user reach it?

The source of truth is the Agent registry, not the JSON manifest. The manifest documents intent;
the registry is what has a runnable handler behind it. A workflow present in the manifest with no
registered handler is not a CLI gap, it is an unimplemented workflow — and the two must not be
reported the same way.

Exit code is always 0: this is a coverage report, not a gate. Making it fail the build would
freeze the gap in place rather than describe it.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CLI_DIR = ROOT / "taktik" / "cli"


class _NullDeviceManager:
    """Stand-in so handlers can be built without a phone.

    Handlers receive the device manager and only touch it when the workflow runs, so building the
    registry never dereferences it. If that ever changes, this audit fails loudly instead of
    silently reporting a smaller registry.
    """

    device = None

    def __getattr__(self, name):  # pragma: no cover - defensive
        raise AssertionError(
            f"Building the registry touched device_manager.{name}; handlers must stay lazy."
        )


def build_full_registry():
    """Register every handler the bot exposes, and return (registry, failures)."""
    from taktik.core.agent.kernel.registry import WorkflowRegistry

    registry = WorkflowRegistry()
    device_manager = _NullDeviceManager()
    failures: list[tuple[str, str]] = []

    registrars = [
        ("instagram.automation", "taktik.core.social_media.instagram.workflows.core.agent_handler",
         "register_instagram_automation_handlers"),
        ("instagram.account", "taktik.core.social_media.instagram.workflows.management.agent_handler",
         "register_instagram_account_handlers"),
        ("instagram.scraping", "taktik.core.social_media.instagram.workflows.scraping.agent_handler",
         "register_instagram_scraping_handlers"),
        ("tiktok.for_you", "taktik.core.social_media.tiktok.actions.business.workflows.for_you.agent_handler",
         "register_tiktok_for_you_handlers"),
        ("tiktok.search", "taktik.core.social_media.tiktok.actions.business.workflows.search.agent_handler",
         "register_tiktok_search_handlers"),
        ("tiktok.followers", "taktik.core.social_media.tiktok.actions.business.workflows.followers.agent_handler",
         "register_tiktok_followers_handlers"),
        ("tiktok.dm", "taktik.core.social_media.tiktok.actions.business.workflows.dm.agent_handler",
         "register_tiktok_dm_handlers"),
        ("tiktok.dm_outreach", "taktik.core.social_media.tiktok.actions.business.workflows.dm.agent_handler",
         "register_tiktok_dm_outreach_handlers"),
        ("tiktok.unfollow", "taktik.core.social_media.tiktok.actions.business.workflows.unfollow.agent_handler",
         "register_tiktok_unfollow_handlers"),
        ("tiktok.scraping", "taktik.core.social_media.tiktok.actions.business.workflows.scraping.agent_handler",
         "register_tiktok_scraping_handlers"),
        ("tiktok.account", "taktik.core.social_media.tiktok.workflows.management.agent_handler",
         "register_tiktok_account_handlers"),
        ("tiktok.publish", "taktik.core.social_media.tiktok.workflows.publish.agent_handler",
         "register_tiktok_publish_handlers"),
        ("threads.automation", "taktik.core.social_media.threads.workflows.agent_handler",
         "register_threads_automation_handlers"),
        ("gmail.account", "taktik.core.app.email.gmail.workflows.agent_handler",
         "register_gmail_account_handlers"),
        ("youtube.account", "taktik.core.social_media.youtube.workflows.account.agent_handler",
         "register_youtube_account_handlers"),
        ("youtube.publish", "taktik.core.social_media.youtube.workflows.publish.agent_handler",
         "register_youtube_publish_handlers"),
    ]

    import importlib
    import inspect

    # Registrars do not share one signature: some take `device_manager`, some `device`, some both
    # `device` and `device_id`, and Threads takes a `startup_provider`. Rather than hardcode each
    # case — which would rot the first time a registrar changes — supply whatever its signature
    # asks for.
    def _stub_for(name: str):
        if name in ("device_manager", "device"):
            return device_manager
        if name == "device_id":
            return "audit-device"
        if name == "startup_provider":
            return lambda *a, **k: None
        return None

    for label, module_path, func_name in registrars:
        try:
            module = importlib.import_module(module_path)
            register = getattr(module, func_name)
            params = inspect.signature(register).parameters
            kwargs = {
                name: _stub_for(name)
                for name, p in params.items()
                if p.kind is inspect.Parameter.KEYWORD_ONLY and p.default is inspect.Parameter.empty
            }
            register(registry, **kwargs)
        except Exception as exc:  # noqa: BLE001 - the report must survive a broken registrar
            failures.append((label, f"{type(exc).__name__}: {exc}"))

    return registry, failures


def registered_ids(registry) -> list[str]:
    handlers = getattr(registry, "_handlers", {})
    return sorted(handlers)


def cli_source() -> str:
    parts = []
    for path in sorted(CLI_DIR.rglob("*.py")):
        if "__pycache__" in str(path):
            continue
        parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def cli_reaches(workflow_id: str, source: str) -> bool:
    """Whether the CLI can plausibly reach this workflow.

    Matches the canonical id, or a registry-driven launcher that resolves ids dynamically. Deep
    menu wiring that reimplements a workflow without naming its id is NOT counted: the point of
    the audit is that the CLI should go through the registry.
    """
    if workflow_id in source:
        return True
    return bool(re.search(r"registry\.resolve\(|missing_workflow_ids\(|WORKFLOW_IDS\b", source))


def main() -> int:
    registry, failures = build_full_registry()
    ids = registered_ids(registry)
    source = cli_source()

    reachable = [i for i in ids if cli_reaches(i, source)]
    missing = [i for i in ids if i not in reachable]

    print("=" * 78)
    print("COUVERTURE CLI DES WORKFLOWS BOT")
    print("=" * 78)
    print(f"  workflows avec handler executable : {len(ids)}")
    print(f"  atteignables depuis la CLI        : {len(reachable)}")
    print(f"  NON atteignables                  : {len(missing)}")

    if failures:
        print("\n  registrars en echec (workflow non compte) :")
        for label, err in failures:
            print(f"    {label}: {err}")

    if missing:
        print("\n" + "-" * 78)
        print("NON ATTEIGNABLES DEPUIS LA CLI")
        print("-" * 78)
        current = None
        for workflow_id in missing:
            platform = workflow_id.split(".")[0]
            if platform != current:
                current = platform
                print(f"\n  {platform.upper()}")
            print(f"    {workflow_id}")

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
