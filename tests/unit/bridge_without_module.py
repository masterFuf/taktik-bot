"""Run one bridge the way the app does (the launcher, its config file) with one module that does not import.

    python tests/unit/bridge_without_module.py <module> <bridge> <config_path>

A broken install, played: importing `<module>` raises `ModuleNotFoundError`, whoever imports it and
whenever. Used by `tests/unit/bridges/test_import_error_has_the_bots_code.py` and by the app's gate
`npm run crash:bridges`, which reads what the real bridge says through the app's own capture.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAUNCHER = HERE.parents[1] / "bridges" / "launcher.py"


class _Missing:
    """A finder asked before every other one: the blocked module is not there."""

    def __init__(self, blocked: str):
        self.blocked = blocked

    def find_spec(self, name, path=None, target=None):
        if name == self.blocked:
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)
        return None


def main() -> None:
    blocked = sys.argv[1]
    # The folder of this script holds test packages (`shared`, `ai`...) a bridge must not see.
    sys.path[:] = [entry for entry in sys.path if entry and Path(entry).resolve() != HERE]
    sys.meta_path.insert(0, _Missing(blocked))
    sys.argv = [str(LAUNCHER)] + sys.argv[2:]
    runpy.run_path(str(LAUNCHER), run_name="__main__")


if __name__ == "__main__":
    main()
