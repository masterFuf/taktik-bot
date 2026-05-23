"""Audit Electron handlers for direct bridge spawn helpers.

Handlers should not call ``getSpawnArgs()`` or ``getBridgeCommand()`` directly.
Bridge process creation belongs in ``front/electron/services/bridge`` so that
dev/prod spawn logic, path checks, env handling and future lifecycle behaviour
stay centralised.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HANDLERS_DIR = ROOT / "front" / "electron" / "handlers"

FORBIDDEN_PATTERNS = [
    re.compile(r"\bgetSpawnArgs\s*\("),
    re.compile(r"\bgetBridgeCommand\s*\("),
]


def main() -> int:
    errors: list[str] = []

    for path in sorted(HANDLERS_DIR.rglob("*.ts")):
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
