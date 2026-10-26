"""A run begins: what an earlier run of the same process left is cleared, in one place.

A bridge process serves one run. Two hosts serve several in one process: the CLI's interactive menu
(one run after another) and the Cartography Lab session (one action after another). What a run keeps
at module level belongs to that run: the stop latch (`run_halt`), the network watch its door started
(`shared/device/network_watch.py`), the cap and the series of the failure captures (`miss_capture`),
the screens of the black box (`screen_ring`), the clock of the foreground check (`foreground_guard`).
Left in place, the next run of the menu started with the latch of the run before and stopped before
its first gesture, under a motive that was not its own, while the watch went on pinging the phone.

Every host calls `begin_run()` where one of its runs begins, before the run touches anything:
`run_bridge_main` (the entry of every bridge), the Lab session before each action, and each door of
the CLI that runs a workflow. `tests/unit/shared/diagnostics/test_run_start.py` holds every host to
it, and holds that nothing else lifts the latch or stops the watch.

A host, never a launcher: a plan of the kernel (`kernel/executor.py`) runs several workflows as one
run, and a block seen by its first step must stop the next. In Symfony terms: the reset of the
services a worker clears between two messages (`ResetInterface`), done by the host that serves the
messages, never by a handler.
"""

from __future__ import annotations

from taktik.core.shared.device import network_watch
from taktik.core.shared.diagnostics import foreground_guard, miss_capture, run_halt, screen_ring


def begin_run() -> None:
    """Clear what an earlier run of this process left: its network watch, its latch, its counters.

    The watch first: stopped, it can no longer set the latch that is lifted next.
    """
    network_watch.stop_network_watch()
    run_halt.reinitialiser()
    miss_capture.reinitialiser()
    foreground_guard.reinitialiser()
    screen_ring.reinitialiser()


__all__ = ["begin_run"]
