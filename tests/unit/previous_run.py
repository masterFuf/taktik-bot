"""What a run leaves in its process, and what the next run of the same process starts with.

A host that serves several runs in one process (the CLI's interactive menu, the Lab session) handed
the second run what the first one left: the stop latch (`run_halt`) it set, and the network watch
(`network_watch`) its door started, a thread still pinging the phone. A test hands a host
`RunThatLosesItsNetwork` as the workflow it runs, twice, and reads `started_with`: each run must
start with `CLEAN`.

Imported as `unit.previous_run`, like `unit.ping_outputs`.
"""
from __future__ import annotations

import threading
from typing import Any, Dict, List

from taktik.core.shared.device import network_probe, network_watch
from taktik.core.shared.diagnostics import run_halt
from unit.ping_outputs import PING_COMPLET

#: The phone of a test run: no adb is reached, the probe's shell is replaced.
SERIAL = "emulator-5554"

#: The door's measure at the start of the run: three replies.
BASELINE = {"rtt_ms": 30.0, "packet_loss_pct": 0.0, "received": 3, "unreachable": False}

#: What a run starts with when nothing of the run before it is left: no latch, no watch.
CLEAN = {"halt": None, "watches": []}


def watches_alive() -> List[str]:
    """The network watches running in this process, by thread name."""
    return [t.name for t in threading.enumerate() if t.name == network_watch.THREAD_NAME and t.is_alive()]


def what_a_run_starts_with() -> Dict[str, Any]:
    """The latch's code (None when lifted) and the watches alive, as a run finds them."""
    return {"halt": (run_halt.arret_demande() or {}).get("code"), "watches": watches_alive()}


class RunThatLosesItsNetwork:
    """A workflow run, as a host calls it (a handler, a launcher): any arguments, a success.

    It notes what it starts with, then ends as the run of October 2026 ends in a process that serves
    another run after it: its network watch still running, its latch set to `network_lost`. The watch
    measures with the probe's real parser on a phone that answers (`PING_COMPLET`), never adb.
    """

    def __init__(self, monkeypatch):
        monkeypatch.setattr(network_probe, "_shell", lambda device_id, command, timeout=15: PING_COMPLET)
        self.started_with: List[Dict[str, Any]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        self.started_with.append(what_a_run_starts_with())
        network_watch.start_network_watch(SERIAL, BASELINE)
        run_halt.demander_arret(
            run_halt.NETWORK_LOST,
            "no route to the Internet (ping: network is unreachable), measured twice 3 s apart",
            device_id=SERIAL,
        )
        return {"success": True}


__all__ = ["BASELINE", "CLEAN", "RunThatLosesItsNetwork", "SERIAL", "watches_alive", "what_a_run_starts_with"]
