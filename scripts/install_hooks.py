"""Install the leak guard (scripts/hooks/pre-commit) as the pre-commit, pre-merge-commit and commit-msg hooks.

The hooks directory comes from `git rev-parse --git-path hooks`, so a linked worktree installs into
the shared hooks of its repository and `core.hooksPath` is honoured. The installed hook runs the
guard of the worktree being committed, or the copy installed next to it on a branch that lacks one.

An existing hook that is not the leak guard is kept unless `--force` is given, which backs it up
as `<name>.before-leak-guard`.

Usage: python scripts/install_hooks.py [--force]
"""

from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys

CORE = pathlib.Path(__file__).resolve().parents[1]
SOURCE_DIR = CORE / "scripts" / "hooks"
HOOK_SOURCE = SOURCE_DIR / "pre-commit"
GUARD_SOURCE = SOURCE_DIR / "leak_guard.py"
# A merge that commits by itself runs pre-merge-commit instead of pre-commit.
HOOK_NAMES = ("pre-commit", "pre-merge-commit", "commit-msg")
MARKER = b"taktik-leak-guard"


def hooks_dir(core: pathlib.Path) -> pathlib.Path:
    out = subprocess.run(["git", "rev-parse", "--git-path", "hooks"], cwd=core, check=True,
                         capture_output=True, text=True).stdout.strip()
    return (core / out).resolve()


def install(hooks: pathlib.Path, force: bool = False) -> list:
    hook = HOOK_SOURCE.read_bytes().replace(b"\r\n", b"\n")
    hooks.mkdir(parents=True, exist_ok=True)
    for name in HOOK_NAMES:
        target = hooks / name
        if target.is_file() and MARKER not in target.read_bytes():
            if not force:
                raise SystemExit(f"{target} is another hook; rerun with --force to back it up and replace it.")
            shutil.copy2(target, target.with_name(f"{name}.before-leak-guard"))
    installed = []
    for name in HOOK_NAMES:
        target = hooks / name
        target.write_bytes(hook)
        target.chmod(0o755)
        installed.append(target)
    guard = hooks / GUARD_SOURCE.name
    shutil.copyfile(GUARD_SOURCE, guard)
    installed.append(guard)
    return installed


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="back up and replace a foreign hook")
    args = parser.parse_args(argv)
    for path in install(hooks_dir(CORE), force=args.force):
        print(f"installed {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
