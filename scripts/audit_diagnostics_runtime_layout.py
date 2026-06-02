"""Audit compat diagnostics runtime layout.

The diagnostics runtime used by Action Tester/Cartography, selector tests and
workflow tests must stay split by subdomain. This catches regressions where new
support modules are dropped flat into ``bridges/compat/diagnostics/runtime``.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / "bridges" / "compat" / "diagnostics" / "runtime"

ALLOWED_ROOT_FILES = {"__init__.py", "events.py"}
ALLOWED_ROOT_DIRS = {"action_test", "selector_test", "workflow_test", "registry"}
IGNORED_ROOT_DIRS = {"__pycache__"}

EXPECTED_FILES = (
    "action_test/action_bundle.py",
    "action_test/runner.py",
    "action_test/tracing.py",
    "action_test/bundles/__init__.py",
    "action_test/bundles/instagram.py",
    "action_test/bundles/tiktok.py",
    "registry/actions.py",
    "registry/commands.py",
    "selector_test/request.py",
    "selector_test/runner.py",
    "workflow_test/catalog.py",
    "workflow_test/dispatch_result.py",
    "workflow_test/dispatcher.py",
    "workflow_test/lifecycle.py",
    "workflow_test/observability.py",
    "workflow_test/report.py",
    "workflow_test/request.py",
    "workflow_test/runners.py",
    "workflow_test/session.py",
    "workflow_test/platforms/instagram/dispatcher.py",
    "workflow_test/platforms/instagram/runners.py",
    "workflow_test/platforms/instagram/workflows/dm.py",
    "workflow_test/platforms/instagram/workflows/publish.py",
    "workflow_test/platforms/instagram/workflows/scraping.py",
    "workflow_test/platforms/instagram/workflows/smart_comment.py",
    "workflow_test/platforms/tiktok/dispatcher.py",
    "workflow_test/platforms/tiktok/runners.py",
    "workflow_test/platforms/tiktok/workflows/automation.py",
    "workflow_test/platforms/tiktok/workflows/dm.py",
    "workflow_test/platforms/tiktok/workflows/publish.py",
    "workflow_test/platforms/tiktok/workflows/scraping.py",
    "workflow_test/platforms/tiktok/workflows/unfollow.py",
)

LEGACY_RUNTIME_MODULES = (
    "action_bundle",
    "action_runner",
    "bundles",
    "bundles_instagram",
    "bundles_tiktok",
    "instagram_automation",
    "instagram_automation_config",
    "instagram_automation_instrumentation",
    "registry_commands",
    "selector_request",
    "selector_runner",
    "tracing",
    "workflow_catalog",
    "workflow_dispatch_result",
    "workflow_dispatcher",
    "workflow_dispatcher_instagram",
    "workflow_dispatcher_tiktok",
    "workflow_lifecycle",
    "workflow_observability",
    "workflow_observability_instagram",
    "workflow_observability_instagram_hooks",
    "workflow_observability_instagram_screens",
    "workflow_report",
    "workflow_request",
    "workflow_runners",
    "workflow_runners_instagram",
    "workflow_runners_tiktok",
    "workflow_session",
)

LEGACY_IMPORT_RE = re.compile(
    r"bridges\.compat\.diagnostics\.runtime\.(?P<module>"
    + "|".join(re.escape(module) for module in LEGACY_RUNTIME_MODULES)
    + r")\b"
)


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def collect_layout_errors() -> list[str]:
    errors: list[str] = []

    if not RUNTIME_ROOT.exists():
        return [f"{relative(RUNTIME_ROOT)} does not exist"]

    for expected_dir in sorted(ALLOWED_ROOT_DIRS):
        if not (RUNTIME_ROOT / expected_dir).is_dir():
            errors.append(f"missing runtime subdomain directory: {relative(RUNTIME_ROOT / expected_dir)}")

    for entry in sorted(RUNTIME_ROOT.iterdir(), key=lambda item: item.name):
        if entry.is_file() and entry.name not in ALLOWED_ROOT_FILES:
            errors.append(
                f"unexpected flat runtime file: {relative(entry)} "
                "(move it under action_test, selector_test, workflow_test or registry)"
            )
        if entry.is_dir() and entry.name not in ALLOWED_ROOT_DIRS and entry.name not in IGNORED_ROOT_DIRS:
            errors.append(f"unexpected runtime root directory: {relative(entry)}")

    for expected_file in EXPECTED_FILES:
        path = RUNTIME_ROOT / expected_file
        if not path.is_file():
            errors.append(f"missing expected runtime module: {relative(path)}")

    return errors


def collect_legacy_import_errors() -> list[str]:
    errors: list[str] = []
    scan_roots = (ROOT / "bridges", ROOT / "tests")

    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        for path in sorted(scan_root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            source = path.read_text(encoding="utf-8-sig")
            for line_number, line in enumerate(source.splitlines(), start=1):
                if LEGACY_IMPORT_RE.search(line):
                    errors.append(f"{relative(path)}:{line_number}: legacy runtime import: {line.strip()}")

    return errors


def main() -> int:
    errors = collect_layout_errors() + collect_legacy_import_errors()

    if errors:
        print("Diagnostics runtime layout audit failed:")
        for error in errors:
            print(f" - {error}")
        return 1

    print("Diagnostics runtime layout OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
