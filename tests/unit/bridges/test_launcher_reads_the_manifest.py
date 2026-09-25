"""The launcher routes with `bridges.manifest.json`, the one bridge list.

It used to carry its own copy of the list; the build scripts already read the manifest, so the
copy could only drift.
"""
import json
import sys
from pathlib import Path

import pytest

from bridges import launcher

MANIFEST = Path(launcher.__file__).resolve().parent / "bridges.manifest.json"


def _flatten(manifest: dict) -> dict:
    modules = {}
    for platform_bridges in manifest.values():
        modules.update(platform_bridges)
    return modules


def test_the_routing_table_is_the_manifest():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    assert launcher.BRIDGE_MODULES == _flatten(manifest)
    assert "tiktok_bridge" in launcher.BRIDGE_MODULES


def test_a_frozen_build_finds_the_manifest_in_its_bundle(monkeypatch, tmp_path):
    bundle = tmp_path / "bundle"
    (bundle / "bridges").mkdir(parents=True)
    (bundle / "bridges" / "bridges.manifest.json").write_text(
        json.dumps({"tiktok": {"tiktok_bridge": "bridges.tiktok.workflows.dispatcher"}}),
        encoding="utf-8",
    )
    # The entry script of a PyInstaller build sits at the bundle root, next to nothing.
    monkeypatch.setattr(launcher, "__file__", str(tmp_path / "launcher.py"))
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)

    assert launcher.load_bridge_modules() == {"tiktok_bridge": "bridges.tiktok.workflows.dispatcher"}


def test_an_unreadable_manifest_is_reported_as_a_json_event(monkeypatch, capsys):
    monkeypatch.setattr(launcher, "BRIDGE_MODULES", {})
    monkeypatch.setattr(launcher, "_MANIFEST_ERROR", "FileNotFoundError: gone")
    monkeypatch.setattr(sys, "argv", ["taktik_launcher.exe", "tiktok_bridge"])

    with pytest.raises(SystemExit) as exit_info:
        launcher.main()

    assert exit_info.value.code == 1
    event = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert event["type"] == "error"
    assert "gone" in event["message"]
