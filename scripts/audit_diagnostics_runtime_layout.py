"""Audit compat diagnostics layout.

The diagnostics runtime used by Action Tester/Cartography, selector tests and
workflow tests must stay split by subdomain. This catches regressions where new
support modules are dropped flat into ``bridges/compat/diagnostics`` or
``bridges/compat/diagnostics/runtime``.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS_ROOT = ROOT / "bridges" / "compat" / "diagnostics"
RUNTIME_ROOT = DIAGNOSTICS_ROOT / "runtime"
WORKFLOW_TEST_ROOT = RUNTIME_ROOT / "workflow_test"

ALLOWED_ROOT_FILES = {"__init__.py", "events.py"}
ALLOWED_ROOT_DIRS = {"action_test", "selector_test", "workflow_test", "registry"}
ALLOWED_DIAGNOSTICS_FILES = {"__init__.py"}
ALLOWED_DIAGNOSTICS_DIRS = {"actions", "entrypoints", "runtime"}
ALLOWED_WORKFLOW_ROOT_FILES = {"__init__.py"}
ALLOWED_WORKFLOW_ROOT_DIRS = {
    "config",
    "contracts",
    "execution",
    "observability",
    "platforms",
    "reporting",
}
IGNORED_ROOT_DIRS = {"__pycache__"}

EXPECTED_FILES = (
    "../entrypoints/action_test.py",
    "../entrypoints/compat.py",
    "../entrypoints/selector_test.py",
    "../entrypoints/tiktok_action_test.py",
    "../entrypoints/workflow_test.py",
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
    "workflow_test/config/catalog.py",
    "workflow_test/config/request.py",
    "workflow_test/contracts/dispatch.py",
    "workflow_test/execution/dispatcher.py",
    "workflow_test/execution/lifecycle.py",
    "workflow_test/execution/runners.py",
    "workflow_test/execution/session.py",
    "workflow_test/observability/__init__.py",
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
    "workflow_test/reporting/report.py",
)

LEGACY_ENTRYPOINT_MODULES = (
    "action_test",
    "compat",
    "selector_test",
    "tiktok_action_test",
    "workflow_test",
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
    r"(?:bridges\.compat\.diagnostics\.(?P<entrypoint>"
    + "|".join(re.escape(module) for module in LEGACY_ENTRYPOINT_MODULES)
    + r")\b|bridges\.compat\.diagnostics\.runtime\.(?P<module>"
    + "|".join(re.escape(module) for module in LEGACY_RUNTIME_MODULES)
    + r")\b)"
)


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def collect_layout_errors() -> list[str]:
    errors: list[str] = []

    if not DIAGNOSTICS_ROOT.exists():
        return [f"{relative(DIAGNOSTICS_ROOT)} does not exist"]

    for expected_dir in sorted(ALLOWED_DIAGNOSTICS_DIRS):
        if not (DIAGNOSTICS_ROOT / expected_dir).is_dir():
            errors.append(f"missing diagnostics subdomain directory: {relative(DIAGNOSTICS_ROOT / expected_dir)}")

    for entry in sorted(DIAGNOSTICS_ROOT.iterdir(), key=lambda item: item.name):
        if entry.is_file() and entry.name not in ALLOWED_DIAGNOSTICS_FILES:
            errors.append(
                f"unexpected flat diagnostics file: {relative(entry)} "
                "(move bridge entrypoints under diagnostics/entrypoints)"
            )
        if entry.is_dir() and entry.name not in ALLOWED_DIAGNOSTICS_DIRS and entry.name not in IGNORED_ROOT_DIRS:
            errors.append(f"unexpected diagnostics root directory: {relative(entry)}")

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

    for expected_dir in sorted(ALLOWED_WORKFLOW_ROOT_DIRS):
        if not (WORKFLOW_TEST_ROOT / expected_dir).is_dir():
            errors.append(f"missing workflow-test subdomain directory: {relative(WORKFLOW_TEST_ROOT / expected_dir)}")

    for entry in sorted(WORKFLOW_TEST_ROOT.iterdir(), key=lambda item: item.name):
        if entry.is_file() and entry.name not in ALLOWED_WORKFLOW_ROOT_FILES:
            errors.append(
                f"unexpected flat workflow-test file: {relative(entry)} "
                "(move it under config, contracts, execution, observability, platforms or reporting)"
            )
        if entry.is_dir() and entry.name not in ALLOWED_WORKFLOW_ROOT_DIRS and entry.name not in IGNORED_ROOT_DIRS:
            errors.append(f"unexpected workflow-test root directory: {relative(entry)}")

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
                    errors.append(f"{relative(path)}:{line_number}: legacy diagnostics import: {line.strip()}")

    return errors


def main() -> int:
    errors = collect_layout_errors() + collect_legacy_import_errors()

    if errors:
        print("Diagnostics layout audit failed:")
        for error in errors:
            print(f" - {error}")
        return 1

    print("Diagnostics layout OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
