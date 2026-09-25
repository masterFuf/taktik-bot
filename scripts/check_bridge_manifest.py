"""Check bridge registry consistency between Bot and Front.

This is intentionally read-only. The launcher and the build scripts read
`bridges.manifest.json`; this check refuses a hand-written list coming back
in launcher.py and compares the manifest with the Front's `PLATFORM_BRIDGES`.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import re
import sys
from pathlib import Path


# ROOT is the folder holding the three sibling repositories (core, app, docs).
ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "core" / "bridges" / "bridges.manifest.json"
LAUNCHER_PATH = ROOT / "core" / "bridges" / "launcher.py"
FRONT_PATHS_PATH = ROOT / "app" / "electron" / "utils" / "paths.ts"
BOT_PATH = ROOT / "core"

if str(BOT_PATH) not in sys.path:
    sys.path.insert(0, str(BOT_PATH))


def load_manifest() -> dict[str, str]:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))
    flattened: dict[str, str] = {}
    for bridges in data.values():
        flattened.update(bridges)
    return flattened


def launcher_hardcodes_its_list() -> bool:
    """True if launcher.py writes the bridge table by hand instead of reading the manifest."""
    tree = ast.parse(LAUNCHER_PATH.read_text(encoding="utf-8-sig"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, ast.Dict):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id == "BRIDGE_MODULES" for t in targets):
                return bool(node.value.keys)
    return False


def load_launcher_modules() -> dict[str, str]:
    """The table the launcher actually routes with, as it loads it at start."""
    from bridges import launcher

    return dict(launcher.load_bridge_modules())


def load_front_bridges() -> set[str]:
    text = FRONT_PATHS_PATH.read_text(encoding="utf-8-sig")
    match = re.search(r"export const PLATFORM_BRIDGES = \{(?P<body>.*?)\} as const", text, re.S)
    if not match:
        raise RuntimeError("PLATFORM_BRIDGES not found in paths.ts")
    return set(re.findall(r"'([^']+_bridge|selector_test_bridge|workflow_test_bridge|action_test_bridge|tiktok_action_test_bridge)'", match.group("body")))


def main() -> int:
    manifest = load_manifest()
    launcher = load_launcher_modules()
    front = load_front_bridges()

    errors: list[str] = []

    if launcher_hardcodes_its_list():
        errors.append("launcher.py hardcodes BRIDGE_MODULES: it must read bridges.manifest.json")

    if manifest != launcher:
        missing_in_launcher = sorted(set(manifest) - set(launcher))
        extra_in_launcher = sorted(set(launcher) - set(manifest))
        mismatched_modules = sorted(
            name for name in set(manifest) & set(launcher)
            if manifest[name] != launcher[name]
        )
        if missing_in_launcher:
            errors.append(f"Missing in launcher.py: {missing_in_launcher}")
        if extra_in_launcher:
            errors.append(f"Extra in launcher.py: {extra_in_launcher}")
        if mismatched_modules:
            errors.append(f"Module mismatch in launcher.py: {mismatched_modules}")

    manifest_names = set(manifest)
    if manifest_names != front:
        missing_in_front = sorted(manifest_names - front)
        extra_in_front = sorted(front - manifest_names)
        if missing_in_front:
            errors.append(f"Missing in front paths.ts: {missing_in_front}")
        if extra_in_front:
            errors.append(f"Extra in front paths.ts: {extra_in_front}")

    missing_modules = sorted(
        module_path
        for module_path in set(manifest.values())
        if importlib.util.find_spec(module_path) is None
    )
    if missing_modules:
        errors.append(f"Bridge modules not importable: {missing_modules}")

    if errors:
        print("Bridge manifest check failed:")
        for error in errors:
            print(f" - {error}")
        return 1

    print(f"Bridge manifest OK ({len(manifest)} bridges)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
