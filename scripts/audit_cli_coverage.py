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
    """Register every handler the bot exposes, and return (registry, failures).

    Delegates to the CLI's own `build_registry`: the registrar list belongs to the module
    that assembles the registry for real, and this audit keeping a second copy meant the
    coverage report would silently stop seeing a platform the day one list was extended
    alone. Reading the production list is also the only way the report can be trusted to
    describe production.
    """
    from taktik.cli.common.registry_builder import build_registry

    build = build_registry(device=_NullDeviceManager(), device_id="audit-device",
                           startup_provider=lambda *a, **k: None)
    return build.registry, build.failures

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
