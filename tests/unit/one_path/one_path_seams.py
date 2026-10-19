"""Patching a name the product code copies, without leaving the double behind.

A rig replaces a seam at its source (`taktik.core.ai.factory.build_ai_service`). Some modules
copy that name when they are imported (`from taktik.core.ai.factory import build_ai_service`).
If such a module is imported for the first time WHILE the source holds the double, it keeps the
double: `monkeypatch` puts back the source, not the copy, and every test collected afterwards runs
on the double (12 contract tests failed that way behind the one-path rigs).

`patch_seam` finds the modules that copy the name at import time (read from the source tree, a
copy of a copy included), imports them first, then patches the source and each copy: the copies
are real when saved, so `monkeypatch` puts them back. The guard of `tests/unit/conftest.py` fails
any test that still leaves a double in a module it imported.
"""
from __future__ import annotations

import ast
import importlib
from functools import lru_cache
from unit.paths import CORE

PRODUCT_ROOTS = (CORE / "taktik", CORE / "bridges")


def _import_time_statements(body):
    """The statements Python runs when it imports the module: not the bodies of functions."""
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        yield node
        for field in ("body", "orelse", "finalbody", "handlers"):
            children = getattr(node, field, None)
            if isinstance(children, list):
                yield from _import_time_statements(children)


@lru_cache(maxsize=None)
def _sources(roots: tuple) -> tuple:
    """(module name, is a package, text) of every Python file under the roots."""
    found = []
    for root in roots:
        for path in root.rglob("*.py"):
            parts = path.relative_to(root.parent).with_suffix("").parts
            package = parts[-1] == "__init__"
            module = ".".join(parts[:-1] if package else parts)
            found.append((module, package, path.read_text(encoding="utf-8-sig")))
    return tuple(found)


@lru_cache(maxsize=None)
def _tree(text: str) -> ast.Module:
    return ast.parse(text)


def _absolute(module: str, package: bool, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""
    base = module.split(".") if package else module.split(".")[:-1]
    base = base[: len(base) - (node.level - 1)]
    return ".".join(base + ([node.module] if node.module else []))


@lru_cache(maxsize=None)
def copiers(source: str, name: str, roots: tuple = PRODUCT_ROOTS) -> tuple:
    """The modules that copy `source.name` when they are imported, and those that copy them."""
    direct = []
    for module, package, text in _sources(roots):
        if name not in text or module == source:
            continue
        for node in _import_time_statements(_tree(text).body):
            if isinstance(node, ast.ImportFrom) and _absolute(module, package, node) == source \
                    and any(alias.name == name and alias.asname in (None, name) for alias in node.names):
                direct.append(module)
                break
    found = list(direct)
    for module in direct:
        found.extend(m for m in copiers(module, name, roots) if m not in found)
    return tuple(found)


def patch_seam(monkeypatch, source: str, name: str, value, roots: tuple = PRODUCT_ROOTS,
               copies: bool = True) -> None:
    """Replace `source.name` by `value` for the test, in the source and in every module that copies it.

    `copies=False` replaces the source only: the copies are still imported first, so they keep the
    real one whatever the order of the tests (a rig whose run needs the real service where the
    code copied it).
    """
    imported = []
    for module in copiers(source, name, roots):
        try:
            imported.append(importlib.import_module(module))
        except ImportError:
            # A module that cannot be imported here cannot capture the double either.
            continue
    monkeypatch.setattr(importlib.import_module(source), name, value)
    for module in imported if copies else ():
        if hasattr(module, name):
            monkeypatch.setattr(module, name, value)


#: What the core probe reads on a phone with no route at all (ping: « Network is unreachable »).
NO_ROUTE = {"rtt_ms": None, "packet_loss_pct": None, "received": 0, "unreachable": True}


class RigNetwork:
    """The phone's network as the core probe reads it, from whichever host measures it.

    Each measure is recorded as `network_baseline <serial>` when `calls` is given; it answers
    unreadable (None) until `cut()`, then no route at all. The source is patched with every copy, so
    the probe answers the same to the bridges and to the core.
    """

    def __init__(self, monkeypatch, calls: list | None = None):
        self.calls = calls
        self.reachable = True
        patch_seam(monkeypatch, "taktik.core.shared.device.network_probe", "measure_network_baseline",
                   self._measure)

    def cut(self) -> None:
        """No mobile data, no Wi-Fi: ping answers « Network is unreachable »."""
        self.reachable = False

    def _measure(self, device_id):
        if self.calls is not None:
            self.calls.append(f"network_baseline {device_id}")
        return None if self.reachable else dict(NO_ROUTE)


def record_ip_rotations(monkeypatch, calls: list) -> None:
    """Record each IP rotation a bridge asks for as `ip_rotation <method>`, and answer it as verified.

    A rig is a recording phone: a rotation toggles the phone's radio, so it is recorded like a tap and
    never run. Without it, a payload that asks for a fresh IP would reach adb from a rig.
    """
    from bridges.common import network

    def rotate(device_id, method="data", ipc=None):
        calls.append(f"ip_rotation {method}")
        return network.NetworkResetOutcome(verdict="verified", method=method, old_ip="198.51.100.1",
                                           new_ip="198.51.100.2", attempts=1, commands_ok=True)

    patch_seam(monkeypatch, "bridges.common.network", "perform_network_reset", rotate)


def give_the_cli_a_connected_phone(monkeypatch, device_manager, device_id: str) -> None:
    """`taktik workflows run` drives `device_manager` (which holds its `device`) as its phone, already
    connected: the CLI connects nothing of its own."""
    from taktik.cli.commands import workflows as workflow_cmds
    from taktik.cli.hosts.phone import CliPhone

    monkeypatch.setattr(workflow_cmds, "_choose_phone", lambda _device_id: CliPhone(device_manager, device_id))


def record_cli_connections(monkeypatch, calls: list, connected_manager, device_id: str) -> None:
    """The CLI's own phone, recorded (`unit.cli_phone`): adb lists `device_id`, and connecting it
    appends `cli_connect <serial>`, then serves `connected_manager`'s device and app calls.

    The CLI runs its real path (`_choose_phone`, then `CliPhone.connect` when a launcher asks), so a
    test sees whether the CLI connected, and when. Only the source is patched: a module that copied
    `DeviceManager` keeps the real one.
    """
    from unit.cli_phone import recording_device_manager

    patch_seam(monkeypatch, "taktik.core.shared.device.manager", "DeviceManager",
               recording_device_manager(calls, device_id, connected_manager), copies=False)
