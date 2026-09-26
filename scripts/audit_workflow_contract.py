#!/usr/bin/env python3
"""The declared bot/app contract (`taktik/core/app/contract/`) still names real things.

Rule 3 of the anti-drift doctrine: the contract is declared once and the app's types are generated
from it. The readers are held to the declaration by `tests/unit/app/contract`; this audit holds the
declaration to the rest of the bot, and the app's generated file to the declaration:

- each workflow id is a runnable workflow of `workflows.manifest.json`;
- each bridge is in `bridges/bridges.manifest.json`;
- each launcher and reader resolves to a function;
- each declared line `type` is one the bot emits (`audit_bridge_events.py`, the census the app's
  `npm run bridge:events` reads);
- the app's generated file, when the app sits next to the bot (`../app`, or `TAKTIK_APP_PATH`),
  is what `scripts/workflow_contract.py` renders today.

    python scripts/audit_workflow_contract.py
"""

from __future__ import annotations

import functools
import importlib
import json
import os
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

#: Where the app keeps the generated file, relative to the app's root.
APP_FILE = Path("src/app/types/contract/workflow-contract.generated.ts")


def _runnable(root: Path) -> set:
    from inventory_capabilities import kind_of, platform_families

    manifest = json.loads((root / "workflows.manifest.json").read_text(encoding="utf-8-sig"))
    return {
        f"{platform}.{family}.{workflow}"
        for platform, family, workflows in platform_families(manifest)
        for workflow in workflows
        if kind_of(manifest, platform, family, workflow) not in ("ui", "planned")
    }


def _bridges(root: Path) -> set:
    manifest = json.loads((root / "bridges" / "bridges.manifest.json").read_text(encoding="utf-8-sig"))
    return {name for platform in manifest.values() for name in platform}


@functools.lru_cache(maxsize=None)
def _emitted(root: Path) -> frozenset:
    import audit_bridge_events

    emitted, _ = audit_bridge_events.scan(root)
    return frozenset(emitted)


def _resolves(dotted: str) -> bool:
    module, _, name = dotted.partition(":")
    try:
        return callable(getattr(importlib.import_module(module), name, None))
    except Exception:
        return False


def app_root(root: Path = ROOT) -> Path:
    return Path(os.environ["TAKTIK_APP_PATH"]) if os.environ.get("TAKTIK_APP_PATH") else root.parent / "app"


def problems(root: Path = ROOT, app: Path | None = None) -> List[str]:
    import workflow_contract
    from taktik.core.app.contract import WORKFLOW_CONTRACTS

    found: List[str] = []
    runnable, bridges = _runnable(root), _bridges(root)
    emitted = _emitted(root)
    seen = set()
    for contract in WORKFLOW_CONTRACTS:
        where = contract.workflow_id
        if where in seen:
            found.append(f"{where}: declared twice")
        seen.add(where)
        if where not in runnable:
            found.append(f"{where}: not a runnable workflow of workflows.manifest.json")
        if contract.bridge not in bridges:
            found.append(f"{where}: bridge {contract.bridge} is not in bridges/bridges.manifest.json")
        for label, dotted in (("launcher", contract.launcher), ("reader", contract.reader),
                              *(("reader", item.reader) for item in contract.settings if item.reader)):
            if not _resolves(dotted):
                found.append(f"{where}: {label} {dotted} does not resolve")
        for event in contract.events:
            if event.type not in emitted:
                found.append(f"{where}: line `{event.type}` is emitted nowhere in the bot")
        keys = [item.key for item in (*contract.settings, *contract.bridge_fields)]
        for key in {k for k in keys if keys.count(k) > 1}:
            found.append(f"{where}: key {key} declared twice")

    app = app if app is not None else app_root(root)
    target = app / APP_FILE
    if app.is_dir():
        text, _ = workflow_contract.render()
        current = target.read_text(encoding="utf-8").replace("\r\n", "\n") if target.exists() else ""
        if current != text:
            found.append(f"{target} is not what the bot declares: npm run workflow:contract -- --write (app)")
    return found


def main() -> int:
    found = problems()
    if found:
        print("[workflow-contract] FAILED")
        for line in found:
            print(f"  - {line}")
        return 1
    from taktik.core.app.contract import WORKFLOW_CONTRACTS

    app = app_root()
    checked = "generated file up to date" if app.is_dir() else "app not found, generated file not checked"
    print(f"[workflow-contract] OK: {len(WORKFLOW_CONTRACTS)} workflows declared; {checked}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
