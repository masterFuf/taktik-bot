"""`run_scope`: a run begins clean and its network watch stops when it ends, the same way in every host.

The behaviour of each host, two runs in one process, is tested where the host lives
(`tests/unit/cli/test_each_run_starts_clean.py`, `tests/unit/bridges/common/test_run_bridge_main.py`,
`tests/unit/bridges/tools/lab/test_action_session_run_halt.py`). Here: what `begin_run` clears, what `end_run`
stops, and the structure that keeps one way of doing it (every host runs inside `run_scope`; nothing
else lifts the latch or stops the watch).
"""
from __future__ import annotations

import ast
import threading
import time
from pathlib import Path
from typing import Iterator, List, Set, Tuple

import pytest

from taktik.core.shared.device import network_probe, network_watch
from taktik.core.shared.diagnostics import foreground_guard, miss_capture, run_halt, screen_ring
from taktik.core.shared.diagnostics.run_start import begin_run, end_run, run_scope
from unit.paths import CORE
from unit.ping_outputs import PING_INJOIGNABLE
from unit.previous_run import BASELINE, CLEAN, SERIAL, RunThatLosesItsNetwork, watches_alive, what_a_run_starts_with


def test_a_run_begins_without_the_latch_the_witness_or_the_watch_of_the_run_before(monkeypatch):
    told = []
    RunThatLosesItsNetwork(monkeypatch)()
    run_halt.configurer_temoin(told.append)

    begin_run()

    assert what_a_run_starts_with() == CLEAN
    # The witness of the run before is gone with its latch: a halt of this run tells nobody of that one.
    run_halt.demander_arret(run_halt.ACTION_BLOCKED, "try_again_later_page")
    assert told == []


def test_the_watch_is_stopped_before_the_latch_is_lifted(monkeypatch):
    # Stopped after, a watch measuring at that moment could set the latch of the run that begins.
    latch_when_stopped = []
    monkeypatch.setattr(network_watch, "stop_network_watch",
                        lambda: latch_when_stopped.append((run_halt.arret_demande() or {}).get("code")))
    run_halt.demander_arret(run_halt.NETWORK_LOST, "no route to the Internet")

    begin_run()

    assert latch_when_stopped == [run_halt.NETWORK_LOST]
    assert run_halt.arret_demande() is None


def test_the_counters_of_the_run_before_start_again(monkeypatch):
    monkeypatch.setattr(miss_capture, "_captures", miss_capture.MAX_PAR_RUN)
    monkeypatch.setattr(miss_capture, "_dernier_selecteur", "back_button")
    monkeypatch.setattr(miss_capture, "_repetitions", miss_capture.SEUIL_BLOCAGE)
    monkeypatch.setattr(miss_capture, "_blocage_signale", True)
    monkeypatch.setattr(foreground_guard, "_dernier_controle", 1.0e9)
    screen_ring._anneau.append({"fingerprint": "a run before"})

    begin_run()

    assert (miss_capture._captures, miss_capture._dernier_selecteur, miss_capture._repetitions,
            miss_capture._blocage_signale) == (0, None, 0, False)
    assert foreground_guard._dernier_controle == 0.0
    assert screen_ring._anneau == []


def test_a_run_that_raises_still_stops_its_watch(monkeypatch):
    run = RunThatLosesItsNetwork(monkeypatch)

    with pytest.raises(RuntimeError):
        with run_scope():
            run()
            raise RuntimeError("the run crashed")

    assert watches_alive() == []
    # The latch stays as the run left it, until the next run begins.
    assert run_halt.arret_demande()["code"] == run_halt.NETWORK_LOST


def test_a_run_that_ends_during_a_measure_waits_briefly_and_drops_its_verdict(monkeypatch):
    """The end of a run does not wait for adb: a measure under way is left to finish, its verdict
    dropped, and the start of the next run waits for it."""
    measuring, answer = threading.Event(), threading.Event()

    def _ping_until_answered(device_id, command, timeout=15):
        measuring.set()
        answer.wait(5)
        return PING_INJOIGNABLE

    monkeypatch.setattr(network_probe, "_shell", _ping_until_answered)
    monkeypatch.setattr(network_watch, "MEASURE_INTERVAL_S", 0.01)
    monkeypatch.setattr(network_watch, "END_OF_RUN_WAIT_S", 0.05)
    # Already suspected: the measure under way would confirm the loss and set the latch.
    network_watch.start_network_watch(SERIAL, BASELINE).suspected = "no route to the Internet"
    assert measuring.wait(5)

    started = time.monotonic()
    end_run()
    ended_in = time.monotonic() - started
    assert ended_in < 1.0 and watches_alive() == [network_watch.THREAD_NAME]

    threading.Timer(0.2, answer.set).start()
    begin_run()

    assert what_a_run_starts_with() == CLEAN


# ---------------------------------------------------------------------------------------------
# One way: every host runs its runs inside `run_scope`, and nothing else clears or ends a run.
# ---------------------------------------------------------------------------------------------

#: The hosts outside the CLI, by file and function: the entry of every bridge, the Lab session's loop.
HOSTS = (
    ("bridges/common/entrypoint.py", "run_bridge_main"),
    ("bridges/tools/lab/action_test/session.py", "run_action_session_bridge"),
)

#: The doors of the CLI the rule below must see, so that it never holds by seeing none.
CLI_DOORS = {
    "taktik/cli/commands/workflows.py::run_workflow",
    "taktik/cli/commands/instagram/agent.py::run_agent",
    "taktik/cli/commands/instagram/publish.py::_run",
    "taktik/cli/hosts/instagram.py::_run_through_handler",
    "taktik/cli/menus/registry.py::run_registry_menu",
}

#: Where the latch is lifted and the watch stopped: `run_start.py`, and the watch replacing itself.
CLEARERS = {"taktik/core/shared/diagnostics/run_start.py", "taktik/core/shared/device/network_watch.py"}


def _functions(path: Path) -> Iterator[ast.FunctionDef]:
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
        if isinstance(node, ast.FunctionDef):
            yield node


def _called_names(node: ast.AST) -> Set[str]:
    names = set()
    for call in ast.walk(node):
        if isinstance(call, ast.Call):
            func = call.func
            names.add(func.id if isinstance(func, ast.Name) else getattr(func, "attr", ""))
    return names


def _launchers_imported(tree: ast.AST) -> Set[str]:
    """The workflow launchers a module imports (`run_*` of an `agent_handler`), lazy imports too."""
    return {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and (node.module or "").endswith(".agent_handler")
        for alias in node.names
        if alias.name.startswith("run_")
    }


def _cli_doors() -> List[Tuple[str, Set[str]]]:
    """Each function of the CLI that runs a workflow (it calls a resolved `handler`, or a launcher),
    with the names it calls."""
    doors = []
    for path in sorted((CORE / "taktik" / "cli").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        runs_a_workflow = {"handler"} | _launchers_imported(tree)
        for function in _functions(path):
            called = _called_names(function)
            if called & runs_a_workflow:
                doors.append((f"{path.relative_to(CORE).as_posix()}::{function.name}", called))
    return doors


def test_every_host_runs_each_of_its_runs_inside_run_scope():
    missing = []
    for relative, name in HOSTS:
        function = next(f for f in _functions(CORE / relative) if f.name == name)
        if "run_scope" not in _called_names(function):
            missing.append(f"{relative}::{name}")
    doors = _cli_doors()
    assert CLI_DOORS <= {door for door, _ in doors}, "the rule no longer sees every door of the CLI"
    missing += [door for door, called in doors if "run_scope" not in called]

    assert missing == [], (
        "A host runs each of its runs inside `with run_scope():` (taktik/core/shared/diagnostics/run_start.py): "
        f"{missing}"
    )


def test_nothing_else_lifts_the_latch_or_stops_the_watch():
    clearing = []
    for root in ("taktik", "bridges"):
        for path in sorted((CORE / root).rglob("*.py")):
            relative = path.relative_to(CORE).as_posix()
            if relative in CLEARERS:
                continue
            called = _called_names(ast.parse(path.read_text(encoding="utf-8-sig")))
            clearing += [f"{relative}: {name}()" for name in ("reinitialiser", "stop_network_watch",
                                                               "begin_run", "end_run") if name in called]

    assert clearing == [], (
        "A run begins and ends in one place: `with run_scope():` (taktik/core/shared/diagnostics/run_start.py) "
        f"around the run, not its pieces: {clearing}"
    )
