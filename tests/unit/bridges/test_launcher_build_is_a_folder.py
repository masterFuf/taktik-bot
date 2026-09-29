"""The launcher is built as a folder (taktik_launcher.exe + _internal/), never as one file.

A one-file build unpacked its whole content (749 MB, 5,492 files) into %TEMP% at every bridge
launch, 14 to 28 s before the first event, and left it there when the desktop killed the bridge.
Three build definitions exist; each one is checked.
"""
import ast
from pathlib import Path

import pytest

CORE = Path(__file__).resolve().parents[3]
BUILD_ALL = CORE.parent / "app" / "scripts" / "build" / "build-all.ps1"


def _string_constants(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def test_build_exe_builds_a_folder():
    args = _string_constants(CORE / "scripts" / "build" / "build_exe.py")

    assert "--onedir" in args
    assert "--onefile" not in args


def test_the_spec_collects_a_folder():
    tree = ast.parse((CORE / "taktik_launcher.spec").read_text(encoding="utf-8-sig"))
    calls = {n.func.id: n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}

    assert "COLLECT" in calls
    exe_kwargs = {k.arg: k.value for k in calls["EXE"].keywords}
    assert isinstance(exe_kwargs.get("exclude_binaries"), ast.Constant)
    assert exe_kwargs["exclude_binaries"].value is True


@pytest.mark.skipif(not BUILD_ALL.is_file(), reason="the app repository is not beside core")
def test_the_app_build_builds_a_folder_and_ships_its_content():
    text = BUILD_ALL.read_text(encoding="utf-8-sig")

    assert '"--onedir"' in text
    assert '"--onefile"' not in text
    # the folder's content goes to app/python, so resources/python/taktik_launcher.exe stays put
    assert "dist\\taktik-bot\\taktik_launcher\\*" in text
