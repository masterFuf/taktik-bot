"""A bridge that only waits, for the owner-watchdog integration test.

Not a test module (no `test_` prefix): `test_owner_watchdog.py` registers it in the REAL launcher
of a child process, so the bridge runs exactly as a production one does -- launcher, crash hooks,
owner watchdog, `run_bridge_main` (which clears the halt latch when the run starts).

Each mode stands for one kind of bridge:

- ``latch``  reads the shared halt latch, like the Instagram sessions and the TikTok loops;
- ``signal`` stops on SIGINT from a main thread asleep in ``time.sleep``, like a family handler;
- ``stuck``  has a SIGINT handler that only reports, like the account bridges' ``_shutdown``.

Every step is appended to the marker file named in the config, so the test can tell which step
of the watchdog ended the bridge.
"""

import signal
import sys
import time

from bridges.common.runtime.entrypoint import run_bridge_main


class _WaitingBridge:
    def __init__(self, config: dict):
        self.marker = config["marker"]
        self.mode = config["mode"]

    def _note(self, text: str) -> None:
        with open(self.marker, "a", encoding="utf-8") as handle:
            handle.write(text + "\n")

    def run(self) -> int:
        if self.mode == "signal":
            def on_stop(signum, frame):
                self._note("signal")
                sys.exit(0)

            signal.signal(signal.SIGINT, on_stop)
        elif self.mode == "stuck":
            signal.signal(signal.SIGINT, lambda signum, frame: self._note("signal-ignored"))

        self._note("ready")

        if self.mode == "latch":
            from taktik.core.shared.diagnostics import run_halt

            while run_halt.arret_demande() is None:
                time.sleep(0.05)
            self._note("latch:" + run_halt.arret_demande()["code"])
            return 0

        while True:
            time.sleep(3600)


def main() -> None:
    run_bridge_main(_WaitingBridge)
