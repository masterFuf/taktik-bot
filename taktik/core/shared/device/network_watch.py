"""The network watch of a run: the door measured the phone's network at the start, the watch goes on.

A run that lost its network said nothing of it (C57S, Instagram 410, October 2026): the mobile data and
the Wi-Fi went off after the door's measure, the profile the run looked for showed « User not found »
(the screen of a deleted account), and the session ended `completed`. Nothing measured the network
after the door, by design of the probe. The screen cannot tell: offline, a profile and a deleted
account look the same, and the feed shows its cache without failing anything.

**What it does.** From a daemon thread, the watch takes the door's measure again
(`network_probe.measure_network_baseline`) every `MEASURE_INTERVAL_S`, and sets the run's stop latch,
`run_halt.NETWORK_LOST`, once a lost network is confirmed. It touches nothing else: no gesture, no
screen, no stdout (the bridges' JSON lines stay the main thread's). The run ends at its next decision
point, through its normal path, as it does for the desktop gone (`bridges/common/owner_watchdog.py`).

In TypeScript terms: a `setInterval` that calls `controller.abort('network_lost')`, and loops that read
`signal.aborted` before each profile. In Symfony terms: Messenger's restart signal, a flag set
elsewhere that the worker reads between two messages.

**What a measure says.**

- No route at all (`unreachable`: airplane mode, no data, no Wi-Fi): lost.
- A route and not one reply out of three: lost, but only when the door's measure had replies. A
  network that lets no ping through from the start says nothing by its silence later; only the loss
  of its route counts.
- An unreadable measure (adb that does not answer, a shell without ping): no conclusion. A phone gone
  is `device_disconnected`'s business.
- Anything else, slow or lossy, is a network.

A loss is measured once more, `CONFIRMATION_DELAY_S` later, before the latch is set: a Wi-Fi to 4G
switch drops the route for a second. A loss that lasts beyond that stops the run (Kevin's decision,
no setting).

**Why fast.** A gesture made offline is not lost: a like given without network (C57S, Instagram 410,
October 2026) turned the heart red and was still there after the network came back and Instagram was
restarted. Instagram keeps it and sends it later, with every other gesture of the offline stretch, in
a burst a person would not make. The detection delay (at worst `MEASURE_INTERVAL_S` plus
`CONFIRMATION_DELAY_S`) is the size of that burst.

**Its life.** The door starts it when it measures the session's baseline, never before an IP
rotation, which cuts the network on purpose right after (`network_door.BEFORE_IP_ROTATION`). One
watch per process: a new door replaces the watch before it, and every host stops it when a run of
its ends (`run_start.end_run`) and again when the next begins (`run_start.begin_run`, before it
lifts the latch): the CLI's menu and the Lab session serve several runs in one process. It stops by itself once the latch is set, by it or by anyone. A daemon thread: it ends with
the bridge's process. An IP rotation in the middle of a run (none today: the rotations of the
bridges come before the door) would have to stop the watch first and have the door start it again.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional

from loguru import logger

from taktik.core.shared.device.network_probe import measure_network_baseline
from taktik.core.shared.diagnostics import run_halt

#: How often the phone's network is measured. The one place to change it: the phone proof sets it.
MEASURE_INTERVAL_S = 10.0

#: How long after a first lost measure the second one is taken. A loss confirmed by it stops the run.
CONFIRMATION_DELAY_S = 3.0

#: The thread's name, as `threading.enumerate()` and a stack dump show it.
THREAD_NAME = "taktik-network-watch"

#: How long `stop()` waits for a measure under way: beyond the probe's own adb timeout.
_JOIN_TIMEOUT_S = 25.0

#: How long the end of a run waits for a measure under way. A bridge exits right after, a menu goes
#: back to its prompt: neither waits for adb. A watch still measuring then drops its verdict, and the
#: start of the next run waits for it (`stop_network_watch`).
END_OF_RUN_WAIT_S = 1.0


def lost_network(measure: Optional[Dict[str, Any]], baseline: Dict[str, Any]) -> Optional[str]:
    """What is lost in `measure`, in words, or None when it shows a network or cannot be read."""
    if not measure:
        return None
    if measure.get("unreachable"):
        return "no route to the Internet (ping: network is unreachable)"
    if measure.get("received") == 0 and (baseline.get("received") or 0) > 0:
        return f"no ping reply out of 3, where the run started with {baseline['received']} of 3"
    return None


class NetworkWatch(threading.Thread):
    """The watch of one run: the rule in `tick()`, one measure at a time; the thread around it in `run()`."""

    def __init__(self, device_id: str, baseline: Dict[str, Any]):
        super().__init__(name=THREAD_NAME, daemon=True)
        self.device_id = device_id
        self.baseline = dict(baseline)
        #: The first lost measure, in words, while its confirmation is awaited.
        self.suspected: Optional[str] = None
        #: Measures taken. Read by the tests and by the end-of-watch log.
        self.measures = 0
        self._stopped = threading.Event()

    @property
    def stop_requested(self) -> bool:
        return self._stopped.is_set()

    def next_wait(self) -> float:
        # Read at each wait, not at construction: the one place to change them is the module.
        return CONFIRMATION_DELAY_S if self.suspected else MEASURE_INTERVAL_S

    def tick(self) -> bool:
        """Measure once and decide. True once the watch has nothing left to do (the latch is set)."""
        if run_halt.arret_demande() is not None:
            return True
        measure = measure_network_baseline(self.device_id)
        self.measures += 1
        if self.stop_requested:
            # Stopped while measuring: the run it watched is over, its verdict belongs to nobody.
            return True
        lost = lost_network(measure, self.baseline)
        if lost is None:
            if self.suspected:
                logger.info(f"Network watch: {self.device_id} answers again, the loss is not confirmed")
            self.suspected = None
            return False
        if self.suspected is None:
            self.suspected = lost
            logger.warning(
                f"Network watch: {self.device_id} {lost}; measured again in {CONFIRMATION_DELAY_S:g} s"
            )
            return False
        run_halt.demander_arret(
            run_halt.NETWORK_LOST,
            f"{lost}, measured twice {CONFIRMATION_DELAY_S:g} s apart",
            device_id=self.device_id,
        )
        return True

    def run(self) -> None:
        try:
            while not self._stopped.wait(self.next_wait()):
                if self.tick():
                    return
        except Exception as exc:  # noqa: BLE001 -- a broken watch must not take the run down
            logger.warning(f"Network watch stopped watching {self.device_id} after {self.measures} measure(s): {exc}")

    def stop(self, wait_s: float = _JOIN_TIMEOUT_S) -> bool:
        """Stop watching, and wait up to `wait_s` for a measure under way (its verdict is dropped).
        True once the thread is gone."""
        self._stopped.set()
        if self.is_alive() and self is not threading.current_thread():
            self.join(timeout=wait_s)
        return not self.is_alive()


_watch: Optional[NetworkWatch] = None


def start_network_watch(device_id: str, baseline: Dict[str, Any]) -> NetworkWatch:
    """Watch the phone's network for the run that starts, in place of any watch before it."""
    global _watch
    stop_network_watch()
    watch = NetworkWatch(device_id, baseline)
    watch.start()
    _watch = watch
    logger.info(f"Network watch: {device_id} measured every {MEASURE_INTERVAL_S:g} s during the run")
    return watch


def stop_network_watch(wait_s: float = _JOIN_TIMEOUT_S) -> None:
    """Stop the watch of the current run, if any, waiting up to `wait_s` for a measure under way.

    Called when a run begins, with the full wait (`run_start.begin_run`), and when it ends, with
    `END_OF_RUN_WAIT_S` (`run_start.end_run`). A watch still measuring after the short wait stays
    known here, its verdict dropped: the start of the next run waits for it.
    """
    global _watch
    watch = _watch
    if watch is None:
        return
    if watch.stop(wait_s):
        _watch = None
    elif wait_s < _JOIN_TIMEOUT_S:
        logger.info(f"Network watch on {watch.device_id}: a measure under way, its verdict dropped")
    else:
        _watch = None
        logger.warning(f"Network watch on {watch.device_id} still measuring after {wait_s:g} s")


__all__ = [
    "CONFIRMATION_DELAY_S",
    "END_OF_RUN_WAIT_S",
    "MEASURE_INTERVAL_S",
    "NetworkWatch",
    "THREAD_NAME",
    "lost_network",
    "start_network_watch",
    "stop_network_watch",
]
