"""The launcher is built as a folder (taktik_launcher.exe + _internal/), never as one file, from one definition.

A one-file build unpacked its whole content (749 MB, 5,492 files) into %TEMP% at every bridge
launch, 14 to 28 s before the first event, and left it there when the desktop killed the bridge.
Three build definitions existed (the spec, `scripts/build/build_exe.py`, the arguments written in
the app's `build-all.ps1`) and had drifted apart: `build_exe.py` packed no `workflows.manifest.json`.
The spec is now the only one, and `build-all.ps1` runs it.
"""
import ast

import pytest
from unit.paths import CORE

BUILD_ALL = CORE.parent / "app" / "scripts" / "build" / "build-all.ps1"


def test_the_spec_collects_a_folder():
    tree = ast.parse((CORE / "taktik_launcher.spec").read_text(encoding="utf-8-sig"))
    calls = {n.func.id: n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}

    assert "COLLECT" in calls
    exe_kwargs = {k.arg: k.value for k in calls["EXE"].keywords}
    assert isinstance(exe_kwargs.get("exclude_binaries"), ast.Constant)
    assert exe_kwargs["exclude_binaries"].value is True


def test_the_spec_is_the_only_build_definition():
    assert not (CORE / "scripts/build/build_exe.py").exists()


@pytest.mark.skipif(not BUILD_ALL.is_file(), reason="the app repository is not beside core")
def test_the_app_build_runs_the_spec_and_ships_its_content():
    text = BUILD_ALL.read_text(encoding="utf-8-sig")

    assert "taktik_launcher.spec" in text
    # no build definition of its own: no option that would make it a second one
    assert "--hidden-import" not in text and "--add-data" not in text and "--onefile" not in text
    # the folder's content goes to app/python, so resources/python/taktik_launcher.exe stays put
    assert "dist\\taktik-bot\\taktik_launcher\\*" in text
