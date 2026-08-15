"""Audit Electron handlers for direct bridge spawn helpers.

Handlers should not call ``getSpawnArgs()`` or ``getBridgeCommand()`` directly.
Bridge process creation belongs in ``taktik-bot/app/electron/services/bridge`` so that
dev/prod spawn logic, path checks, env handling and future lifecycle behaviour
stay centralised.
"""

from __future__ import annotations

import re
from pathlib import Path


# ROOT is the folder holding the three sibling repositories (core, app, docs).
ROOT = Path(__file__).resolve().parents[2]
HANDLERS_DIR = ROOT / "app" / "electron" / "handlers"

FORBIDDEN_PATTERNS = [
    re.compile(r"\bgetSpawnArgs\s*\("),
    re.compile(r"\bgetBridgeCommand\s*\("),
]


def main() -> int:
    errors: list[str] = []

    # rglob on a missing directory yields nothing and raises nothing, so a wrong
    # path used to make this audit report OK without reading a single file. Scanning
    # zero handlers is never a pass — it means the layout moved under the audit.
    handlers = sorted(HANDLERS_DIR.rglob("*.ts"))
    if not handlers:
        print(f"Bridge handler usage audit failed: no handler found under {HANDLERS_DIR}")
        print("Check the path above — the audit cannot vouch for files it never read.")
        return 1

    for path in handlers:
        rel = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8-sig")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern in FORBIDDEN_PATTERNS:
                if pattern.search(line):
                    errors.append(f"{rel}:{lineno}: {line.strip()}")

    if errors:
        print("Bridge handler usage audit failed:")
        for error in errors:
            print(f" - {error}")
        print("\nUse runBridge(), startBridge() or spawnBridgeProcess() from BridgeProcessRunner.ts.")
        return 1

    print("Bridge handler usage OK (no direct getSpawnArgs/getBridgeCommand in handlers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
