"""Check workflow type registry consistency.

The JSON manifest is the cross-project documentation source. The Electron
registry is the typed runtime source that handlers can import progressively.
This audit catches drift between the two before we migrate more code.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "bot" / "workflows.manifest.json"
TS_REGISTRY_PATH = ROOT / "front" / "electron" / "services" / "app" / "workflows" / "registry" / "workflow-registry.ts"
RENDERER_TYPES_PATH = ROOT / "front" / "src" / "app" / "types" / "workflow.types.ts"

TS_ARRAY_RE = re.compile(
    r"export const (?P<name>[A-Z0-9_]+) = \[(?P<body>.*?)\] as const",
    re.S,
)
TS_STRING_RE = re.compile(r"'([^']+)'")

CHECKS = {
    "INSTAGRAM_AUTOMATION_WORKFLOWS": ("instagram", "automation"),
    "INSTAGRAM_SCRAPING_WORKFLOWS": ("instagram", "scraping"),
    "INSTAGRAM_ACCOUNT_WORKFLOWS": ("instagram", "account"),
    "INSTAGRAM_PANEL_WORKFLOWS": ("instagram", "panel"),
    "TIKTOK_AUTOMATION_WORKFLOWS": ("tiktok", "automation"),
    "TIKTOK_ACCOUNT_WORKFLOWS": ("tiktok", "account"),
    "TIKTOK_PANEL_WORKFLOWS": ("tiktok", "panel"),
    "THREADS_AUTOMATION_WORKFLOWS": ("threads", "automation"),
    "GMAIL_ACCOUNT_WORKFLOWS": ("gmail", "account"),
    "YOUTUBE_ACCOUNT_WORKFLOWS": ("youtube", "account"),
    "PUBLISH_WORKFLOWS": ("youtube", "publish"),
}


def load_ts_arrays() -> dict[str, list[str]]:
    text = TS_REGISTRY_PATH.read_text(encoding="utf-8-sig")
    arrays: dict[str, list[str]] = {}
    for match in TS_ARRAY_RE.finditer(text):
        arrays[match.group("name")] = TS_STRING_RE.findall(match.group("body"))
    renderer_text = RENDERER_TYPES_PATH.read_text(encoding="utf-8-sig")
    for match in TS_ARRAY_RE.finditer(renderer_text):
        arrays[match.group("name")] = TS_STRING_RE.findall(match.group("body"))
    return arrays


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))
    ts_arrays = load_ts_arrays()

    errors: list[str] = []
    for ts_name, path in CHECKS.items():
        expected = manifest[path[0]][path[1]]
        actual = ts_arrays.get(ts_name)
        if actual is None:
            errors.append(f"Missing TS array: {ts_name}")
            continue
        if actual != expected:
            errors.append(
                f"{ts_name} differs from manifest {path[0]}.{path[1]}: "
                f"expected={expected}, actual={actual}"
            )

    expected_session_workflows = (
        manifest["instagram"]["panel"]
        + manifest["tiktok"]["panel"]
    )
    actual_session_workflows = ts_arrays.get("SESSION_WORKFLOW_TYPES")
    if actual_session_workflows != expected_session_workflows:
        errors.append(
            "SESSION_WORKFLOW_TYPES differs from manifest instagram.panel + tiktok.panel: "
            f"expected={expected_session_workflows}, actual={actual_session_workflows}"
        )

    expected_tiktok_live_panel = manifest["tiktok"]["live_panel"]
    actual_tiktok_live_panel = ts_arrays.get("TIKTOK_LIVE_PANEL_WORKFLOW_TYPES")
    if actual_tiktok_live_panel != expected_tiktok_live_panel:
        errors.append(
            "TIKTOK_LIVE_PANEL_WORKFLOW_TYPES differs from manifest tiktok.live_panel: "
            f"expected={expected_tiktok_live_panel}, actual={actual_tiktok_live_panel}"
        )

    expected_instagram_scraping = manifest["instagram"]["scraping"]
    actual_instagram_scraping = ts_arrays.get("INSTAGRAM_SCRAPING_WORKFLOW_TYPES")
    if actual_instagram_scraping != expected_instagram_scraping:
        errors.append(
            "INSTAGRAM_SCRAPING_WORKFLOW_TYPES differs from manifest instagram.scraping: "
            f"expected={expected_instagram_scraping}, actual={actual_instagram_scraping}"
        )

    if errors:
        print("Workflow registry audit failed:")
        for error in errors:
            print(f" - {error}")
        return 1

    total = sum(len(ts_arrays[name]) for name in CHECKS if name in ts_arrays)
    print(f"Workflow registry OK ({total} typed entries checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
