"""Run one bridge the way the app does (the launcher, its config file) with one module that does not import.

    python tests/unit/bridge_without_module.py <module> <bridge> <config_path>

A broken install, played: importing `<module>` raises `ModuleNotFoundError`, whoever imports it and
whenever. Used by `tests/unit/bridges/test_import_error_has_the_bots_code.py` and by the app's gate
`npm run crash:bridges`, which reads what the real bridge says through the app's own capture.
`tests/unit/bridge_with_fault.py` runs the launcher the same way, through `run_launcher`.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORE = HERE.parents[1]
LAUNCHER = CORE / "bridges" / "launcher.py"


class _Missing:
    """A finder asked before every other one: the blocked module is not there."""

    def __init__(self, blocked: str):
        self.blocked = blocked

    def find_spec(self, name, path=None, target=None):
        if name == self.blocked:
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)
        return None


def import_path_of_a_bridge() -> None:
    """The import path the app gives a bridge: the engine, never the test packages of this folder
    (`shared`, `ai`...), which a bridge must not see."""
    sys.path[:] = [entry for entry in sys.path if entry and Path(entry).resolve() != HERE]
    if str(CORE) not in sys.path:
        sys.path.insert(0, str(CORE))


def run_launcher(bridge_args: list[str]) -> None:
    """`bridges/launcher.py <bridge> <config_path>`, in this process, as the app starts it."""
    sys.argv = [str(LAUNCHER)] + bridge_args
    runpy.run_path(str(LAUNCHER), run_name="__main__")


def main() -> None:
    blocked = sys.argv[1]
    import_path_of_a_bridge()
    sys.meta_path.insert(0, _Missing(blocked))
    run_launcher(sys.argv[2:])


if __name__ == "__main__":
    main()
