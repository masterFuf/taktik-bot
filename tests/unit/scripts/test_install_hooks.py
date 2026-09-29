"""The installer puts the leak guard on every hook through which git records a commit."""

import importlib.util
import pathlib

CORE = pathlib.Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location("install_hooks", CORE / "scripts" / "hooks" / "install_hooks.py")
install_hooks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(install_hooks)


def test_a_merge_that_commits_by_itself_runs_the_guard(tmp_path):
    # `git merge` without --no-commit runs pre-merge-commit, not pre-commit.
    installed = {path.name for path in install_hooks.install(tmp_path)}
    assert {"pre-commit", "pre-merge-commit", "commit-msg", "leak_guard.py"} <= installed
    for name in ("pre-commit", "pre-merge-commit", "commit-msg"):
        assert install_hooks.MARKER in (tmp_path / name).read_bytes()
