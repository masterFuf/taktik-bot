"""Run one bridge the way the app does (the launcher, its config file) with one call that raises.

    python tests/unit/bridge_with_fault.py [--phone] [--import-error] [--passes <module>:<name>]... <module>:<name> <bridge> <config>

`<module>:<name>` (`<name>` may be `Class.method`) is replaced, before the bridge is imported, by a
function that raises `RuntimeError("fault injected by the test")`: the failure a run catches
(a workflow that breaks, a base that does not open) without a broken install; with `--import-error`,
`ModuleNotFoundError` (a module the call needs that did not import). `--phone` makes the
two connections of the engine (`ConnectionService.connect`, `DeviceManager.connect`) succeed on a
stand-in device, so that a run gets past its connection with no phone plugged in; `--passes` makes
one more step that would ask the phone (the app is installed, it restarted) return True. Nothing
may ask that device anything, the fault comes first.
Used by `tests/unit/bridges/test_a_caught_failure_carries_its_traceback.py`.
"""

from __future__ import annotations

import importlib
import sys

from bridge_without_module import import_path_of_a_bridge, run_launcher

FAULT = "fault injected by the test"
MISSING = "gate_missing_module"


class StandInPhone:
    """The device of a connection that succeeded. A bridge that asks it anything breaks the test."""


def _raise_the_fault(*args, **kwargs):
    raise RuntimeError(FAULT)


def _raise_an_import(*args, **kwargs):
    raise ModuleNotFoundError(f"No module named {MISSING!r}", name=MISSING)


def _connection_to_the_stand_in(connection) -> bool:
    connection._device = StandInPhone()
    connection._connected = True
    return True


def _device_manager_on_the_stand_in(manager, *args, **kwargs) -> bool:
    manager.device = StandInPhone()
    return True


def _passes(*args, **kwargs) -> bool:
    return True


def _replace(target: str, replacement) -> None:
    module_name, _, qualified_name = target.partition(":")
    owner = importlib.import_module(module_name)
    *path, name = qualified_name.split(".")
    for part in path:
        owner = getattr(owner, part)
    getattr(owner, name)  # a target that does not exist is a broken test, not a green one
    setattr(owner, name, replacement)


def main() -> None:
    args = sys.argv[1:]
    phone, passing, fault = False, [], _raise_the_fault
    while args[0].startswith("--"):
        if args[0] == "--phone":
            phone, args = True, args[1:]
        elif args[0] == "--import-error":
            fault, args = _raise_an_import, args[1:]
        elif args[0] == "--passes":
            passing.append(args[1])
            args = args[2:]
        else:
            raise SystemExit(f"unknown option {args[0]}")
    target, bridge_args = args[0], args[1:]
    import_path_of_a_bridge()
    if phone:
        _replace("taktik.core.shared.device.connection:ConnectionService.connect", _connection_to_the_stand_in)
        _replace("taktik.core.shared.device.manager:DeviceManager.connect", _device_manager_on_the_stand_in)
    for step in passing:
        _replace(step, _passes)
    _replace(target, fault)
    run_launcher(bridge_args)


if __name__ == "__main__":
    main()
