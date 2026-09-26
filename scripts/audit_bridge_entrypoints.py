"""Every bridge starts the same way, and every bridge list is the manifest.

A bridge of `bridges/bridges.manifest.json` is started by `bridges/launcher.py`, which calls the
module's `main()`. That `main()` hands its bridge to `run_bridge_main`
(`bridges/common/runtime/entrypoint.py`), the one reader of the run's config: a JSON file named by
the first argument. Nothing else under `bridges/` reads `sys.argv` or parses flags.

Refused:

- a manifest module without `main()`, or whose `main()` does not call `run_bridge_main`;
- `sys.argv` read anywhere under `bridges/` except the launcher and the entrypoint;
- `argparse` imported under `bridges/`;
- a second way to hand over the config (a `config_source` parameter or argument);
- a build file (`scripts/build_exe.py`, `taktik_launcher.spec`, the app's `build-all.ps1`) that
  does not read the manifest, or that names a bridge of it by hand;
- the app's `PLATFORM_BRIDGES` (`electron/utils/paths.ts`) differing from the manifest, platform
  by platform.

    python scripts/audit_bridge_entrypoints.py
"""

from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

CORE = Path(__file__).resolve().parents[1]
APP = CORE.parent / "app"

MANIFEST_NAME = "bridges.manifest.json"
MANIFEST_PATH = CORE / "bridges" / MANIFEST_NAME
BRIDGES_DIR = CORE / "bridges"
ENTRY_HELPER = "run_bridge_main"

# The only two readers of the command line under bridges/.
ARGV_READERS = {"bridges/launcher.py", "bridges/common/runtime/entrypoint.py"}

BUILD_FILES = (
    CORE / "scripts" / "build_exe.py",
    CORE / "taktik_launcher.spec",
    APP / "scripts" / "build" / "build-all.ps1",
)
APP_PATHS = APP / "electron" / "utils" / "paths.ts"


@dataclass
class Sources:
    """What the audit reads, so a test can hand it other files."""

    manifest: dict[str, dict[str, str]]
    bridge_files: dict[str, str]  # relative path -> source, every .py under bridges/
    build_files: dict[str, str] = field(default_factory=dict)  # label -> text
    app_paths: str | None = None


def load_sources() -> Sources:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))
    bridge_files = {
        path.relative_to(CORE).as_posix(): path.read_text(encoding="utf-8-sig")
        for path in sorted(BRIDGES_DIR.rglob("*.py"))
        if "__pycache__" not in path.parts
    }
    build_files = {
        (path.relative_to(CORE.parent).as_posix()): path.read_text(encoding="utf-8-sig")
        for path in BUILD_FILES
        if path.is_file()
    }
    app_paths = APP_PATHS.read_text(encoding="utf-8-sig") if APP_PATHS.is_file() else None
    return Sources(manifest, bridge_files, build_files, app_paths)


def module_file(module: str) -> str:
    return module.replace(".", "/") + ".py"


def _called_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _main_of(tree: ast.Module) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node
    return None


def check_entrypoints(sources: Sources) -> list[str]:
    findings: list[str] = []
    for platform, bridges in sources.manifest.items():
        for name, module in bridges.items():
            rel = module_file(module)
            text = sources.bridge_files.get(rel)
            if text is None:
                findings.append(f"{name}: {rel} not found")
                continue
            main = _main_of(ast.parse(text))
            if main is None:
                findings.append(f"{name}: {rel} has no main()")
                continue
            calls = {_called_name(node) for node in ast.walk(main) if isinstance(node, ast.Call)}
            if ENTRY_HELPER not in calls:
                findings.append(f"{name}: main() of {rel} does not call {ENTRY_HELPER}")
    return findings


def _reads_argv(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "argv"
        and isinstance(node.value, ast.Name)
        and node.value.id == "sys"
    )


def check_config_readers(sources: Sources) -> list[str]:
    findings: list[str] = []
    for rel, text in sources.bridge_files.items():
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if rel not in ARGV_READERS and _reads_argv(node):
                findings.append(f"{rel}:{node.lineno} reads sys.argv (only run_bridge_main reads the config)")
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                if any(name == "argparse" or name.startswith("argparse.") for name in names):
                    findings.append(f"{rel}:{node.lineno} imports argparse (a bridge reads a config file)")
            elif isinstance(node, ast.Call):
                if any(keyword.arg == "config_source" for keyword in node.keywords):
                    findings.append(f"{rel}:{node.lineno} picks another config source (config_source)")
            elif isinstance(node, ast.FunctionDef) and node.name == ENTRY_HELPER:
                params = [arg.arg for arg in (*node.args.args, *node.args.kwonlyargs)]
                if "config_source" in params:
                    findings.append(f"{rel}:{node.lineno} {ENTRY_HELPER} accepts another config source")
    return findings


def check_build_lists(sources: Sources) -> list[str]:
    findings: list[str] = []
    names = {name for bridges in sources.manifest.values() for name in bridges}
    modules = {module for bridges in sources.manifest.values() for module in bridges.values()}
    for label, text in sources.build_files.items():
        if MANIFEST_NAME not in text:
            findings.append(f"{label} does not read {MANIFEST_NAME}")
        written = sorted(
            item for item in names | modules
            if re.search(rf"(?<![\w.]){re.escape(item)}(?![\w])", text)
        )
        if written:
            findings.append(f"{label} names bridges by hand: {written}")
    return findings


def app_platform_bridges(text: str) -> dict[str, list[str]] | None:
    match = re.search(r"export const PLATFORM_BRIDGES = \{(?P<body>.*?)\n\} as const", text, re.S)
    if not match:
        return None
    groups: dict[str, list[str]] = {}
    for group in re.finditer(r"(?P<platform>\w+):\s*\[(?P<names>[^\]]*)\]", match.group("body")):
        groups[group.group("platform")] = re.findall(r"'([a-z0-9_]+)'", group.group("names"))
    return groups


def check_app_list(sources: Sources) -> list[str]:
    if sources.app_paths is None:
        return [f"{APP_PATHS} not found: the app list is not checked"]
    groups = app_platform_bridges(sources.app_paths)
    if groups is None:
        return ["PLATFORM_BRIDGES not found in electron/utils/paths.ts"]
    expected = {platform: sorted(bridges) for platform, bridges in sources.manifest.items()}
    actual = {platform: sorted(names) for platform, names in groups.items()}
    if expected == actual:
        return []
    findings = []
    for platform in sorted(set(expected) | set(actual)):
        want, have = set(expected.get(platform, [])), set(actual.get(platform, []))
        if want - have:
            findings.append(f"paths.ts, {platform}: missing {sorted(want - have)}")
        if have - want:
            findings.append(f"paths.ts, {platform}: extra {sorted(have - want)}")
    return findings or ["paths.ts: PLATFORM_BRIDGES differs from the manifest"]


def audit(sources: Sources) -> list[str]:
    return (
        check_entrypoints(sources)
        + check_config_readers(sources)
        + check_build_lists(sources)
        + check_app_list(sources)
    )


def main() -> int:
    sources = load_sources()
    findings = audit(sources)
    count = sum(len(bridges) for bridges in sources.manifest.values())
    if findings:
        print(f"Bridge entrypoints: {len(findings)} finding(s)")
        for finding in findings:
            print(f" - {finding}")
        return 1
    print(f"Bridge entrypoints OK ({count} bridges on {ENTRY_HELPER}, lists = manifest)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
