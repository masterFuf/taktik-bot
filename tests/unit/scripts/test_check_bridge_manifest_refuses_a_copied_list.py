"""The manifest check refuses a bridge list written by hand in launcher.py again."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import check_bridge_manifest  # noqa: E402


def test_the_current_launcher_reads_the_manifest():
    assert check_bridge_manifest.launcher_hardcodes_its_list() is False


def test_a_hand_written_table_is_flagged(monkeypatch, tmp_path):
    launcher = tmp_path / "launcher.py"
    launcher.write_text('BRIDGE_MODULES = {"tiktok_bridge": "bridges.tiktok.workflows.dispatcher"}\n',
                        encoding="utf-8")
    monkeypatch.setattr(check_bridge_manifest, "LAUNCHER_PATH", launcher)

    assert check_bridge_manifest.launcher_hardcodes_its_list() is True


def test_the_empty_fallback_is_not_a_copy(monkeypatch, tmp_path):
    launcher = tmp_path / "launcher.py"
    launcher.write_text("try:\n    BRIDGE_MODULES = load()\nexcept Exception:\n    BRIDGE_MODULES = {}\n",
                        encoding="utf-8")
    monkeypatch.setattr(check_bridge_manifest, "LAUNCHER_PATH", launcher)

    assert check_bridge_manifest.launcher_hardcodes_its_list() is False
