"""Audit the Cartography Lab layout, ``bridges/tools/lab``.

The Lab and its benches must stay split by subdomain. This catches a support module dropped flat
at the root of the Lab, a folder there that no subdomain owns, and a module dropped flat at the
root of the workflow bench (``workflow_test``).

At the root of the Lab live its package, the stdout helper of the benches (``events.py``) and one
entry per Lab bridge, named as its key of ``bridges/bridges.manifest.json``
(``action_test_bridge.py``...). The entries are read from the manifest, not listed here again.

Until the tree lot of 2026-09-29 the Lab lived under ``bridges/compat/diagnostics`` (entries under
``entrypoints/``, support under ``runtime/``) and this audit also refused the imports of the flat
modules of an older layout. An import of a module that does not exist is refused for every package
by ``audit_import_layers.py`` (``import-resolves``), and a flat module coming back is refused by the
layout check below.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LAB_ROOT = ROOT / "bridges" / "tools" / "lab"
WORKFLOW_TEST_ROOT = LAB_ROOT / "workflow_test"
MANIFEST_PATH = ROOT / "bridges" / "bridges.manifest.json"
LAB_PACKAGE = "bridges.tools.lab"

ALLOWED_ROOT_FILES = {"__init__.py", "events.py"}
ALLOWED_ROOT_DIRS = {"actions", "action_test", "registry", "selector_test", "workflow_test", "youtube_action_test"}
ALLOWED_WORKFLOW_ROOT_FILES = {"__init__.py"}
ALLOWED_WORKFLOW_ROOT_DIRS = {
    "config",
    "contracts",
    "execution",
    "observability",
    "platforms",
    "reporting",
}
IGNORED_DIRS = {"__pycache__"}

EXPECTED_FILES = (
    "action_test/action_bundle.py",
    "action_test/runner.py",
    "action_test/tracing.py",
    "action_test/bundles/__init__.py",
    "action_test/bundles/instagram.py",
    "action_test/bundles/tiktok.py",
    "registry/actions.py",
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
    "workflow_test/platforms/tiktok/dispatcher.py",
    "workflow_test/platforms/tiktok/runners.py",
    "workflow_test/platforms/tiktok/workflows/automation.py",
    "workflow_test/platforms/tiktok/workflows/dm.py",
    "workflow_test/platforms/tiktok/workflows/publish.py",
    "workflow_test/platforms/tiktok/workflows/scraping.py",
    "workflow_test/platforms/tiktok/workflows/unfollow.py",
    "workflow_test/reporting/report.py",
)


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def lab_entries() -> set[str]:
    """The file of each Lab bridge of the manifest (`bridges.tools.lab.<key>` -> `<key>.py`)."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))
    modules = [module for bridges in manifest.values() for module in bridges.values()]
    return {module.rsplit(".", 1)[1] + ".py" for module in modules if module.rsplit(".", 1)[0] == LAB_PACKAGE}


def collect_layout_errors() -> list[str]:
    errors: list[str] = []

    if not LAB_ROOT.exists():
        return [f"{relative(LAB_ROOT)} does not exist"]

    entries = lab_entries()
    if not entries:
        errors.append(f"no bridge of {relative(MANIFEST_PATH)} lives in {LAB_PACKAGE}")
    for entry in sorted(entries):
        if not (LAB_ROOT / entry).is_file():
            errors.append(f"missing Lab bridge entry: {relative(LAB_ROOT / entry)}")

    for expected_dir in sorted(ALLOWED_ROOT_DIRS):
        if not (LAB_ROOT / expected_dir).is_dir():
            errors.append(f"missing Lab subdomain directory: {relative(LAB_ROOT / expected_dir)}")

    for entry in sorted(LAB_ROOT.iterdir(), key=lambda item: item.name):
        if entry.is_file() and entry.name not in ALLOWED_ROOT_FILES | entries:
            errors.append(
                f"unexpected flat Lab file: {relative(entry)} "
                "(an entry is named as its key of the bridges manifest; support goes under "
                "action_test, selector_test, workflow_test, registry or youtube_action_test)"
            )
        if entry.is_dir() and entry.name not in ALLOWED_ROOT_DIRS and entry.name not in IGNORED_DIRS:
            errors.append(f"unexpected Lab root directory: {relative(entry)}")

    for expected_dir in sorted(ALLOWED_WORKFLOW_ROOT_DIRS):
        if not (WORKFLOW_TEST_ROOT / expected_dir).is_dir():
            errors.append(f"missing workflow-test subdomain directory: {relative(WORKFLOW_TEST_ROOT / expected_dir)}")

    for entry in sorted(WORKFLOW_TEST_ROOT.iterdir(), key=lambda item: item.name):
        if entry.is_file() and entry.name not in ALLOWED_WORKFLOW_ROOT_FILES:
            errors.append(
                f"unexpected flat workflow-test file: {relative(entry)} "
                "(move it under config, contracts, execution, observability, platforms or reporting)"
            )
        if entry.is_dir() and entry.name not in ALLOWED_WORKFLOW_ROOT_DIRS and entry.name not in IGNORED_DIRS:
            errors.append(f"unexpected workflow-test root directory: {relative(entry)}")

    for expected_file in EXPECTED_FILES:
        path = LAB_ROOT / expected_file
        if not path.is_file():
            errors.append(f"missing expected Lab module: {relative(path)}")

    return errors


def main() -> int:
    errors = collect_layout_errors()

    if errors:
        print("Lab layout audit failed:")
        for error in errors:
            print(f" - {error}")
        return 1

    print(f"Lab layout OK ({len(lab_entries())} Lab bridges at the root of {relative(LAB_ROOT)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
