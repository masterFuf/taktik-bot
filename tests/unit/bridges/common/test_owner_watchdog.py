"""A bridge whose desktop app disappeared must stop on its own, and through the normal stop.

Before, an orphan kept driving the phone: its events went into a dead pipe (the IPC writer
swallows the error), nobody could stop it, and the run ended hours later as `run_lost`.

Three levels here:

- the stop steps, with a fake owner and recorded actions (order, delays, nothing when the owner
  lives);
- the real owner probe of this OS, against real processes (alive, missing, PID reused);
- one real orphan: a fake desktop spawns a waiting bridge through the real launcher, dies
  without a word, and the bridge must be gone within seconds -- by the step its kind expects.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from bridges.common.runtime import owner_watchdog as wd
from taktik.core.shared.diagnostics import run_halt

CORE = Path(__file__).resolve().parents[4]
FIXTURE_DIR = Path(__file__).resolve().parent


# ------------------------------------------------------------------------- stop steps

class _FakeProbe:
    """An owner that dies at the chosen poll (never, when `gone_at` is None)."""

    pid = 4242

    def __init__(self, gone_at: int | None = 0):
        self._gone_at = gone_at
        self._polls = 0
        self.gone_reason = None
        self.closed = False

    def wait(self, timeout_s: float) -> bool:
        if self._gone_at is not None and self._polls >= self._gone_at:
            self.gone_reason = "exited"
            return True
        self._polls += 1
        time.sleep(min(timeout_s, 0.01))
        return False

    def close(self) -> None:
        self.closed = True


def _watchdog(probe, *, handled=True, signal_grace=0.05, exit_grace=0.05):
    calls: list[tuple[str, float, object]] = []
    exited = threading.Event()

    def record(name, value=None):
        calls.append((name, time.monotonic(), value))

    def interrupt():
        record("interrupt")
        return handled

    def exit_now():
        record("exit")
        exited.set()

    dog = wd.OwnerWatchdog(
        probe,
        bridge_name="fake_bridge",
        poll_interval_s=0.01,
        signal_grace_s=signal_grace,
        hard_exit_grace_s=exit_grace,
        silence=lambda: record("silence"),
        halt=lambda detail: record("halt", detail),
        interrupt=interrupt,
        exit_now=exit_now,
    )
    return dog, calls, exited


def test_a_dead_owner_runs_the_steps_in_order():
    dog, calls, exited = _watchdog(_FakeProbe(gone_at=2), signal_grace=0.1, exit_grace=0.1)
    dog.start()

    assert exited.wait(3), "the last step never came"
    dog.join(1)

    names = [name for name, _, _ in calls]
    # Silence first: the finalisation that follows prints its event, and a print on a dead pipe
    # raises before the session row is written.
    assert names == ["silence", "halt", "halt", "interrupt", "exit"]
    assert "desktop pid 4242" in calls[1][2] and "exited" in calls[1][2]

    at = {name: stamp for name, stamp, _ in calls}
    # The latch gets its grace before the signal, the signal its own before the exit.
    assert at["interrupt"] - calls[1][1] >= 0.09
    assert at["exit"] - at["interrupt"] >= 0.09
    assert dog.steps == ["silence", "halt", "interrupt", "exit"]


def test_a_living_owner_triggers_nothing():
    probe = _FakeProbe(gone_at=None)
    dog, calls, _ = _watchdog(probe)
    dog.start()

    time.sleep(0.2)
    dog.stop()
    dog.join(1)

    assert not dog.is_alive()
    assert calls == []
    assert probe.closed


def test_an_unhandled_sigint_still_ends_with_the_exit():
    dog, calls, exited = _watchdog(_FakeProbe(), handled=False)
    dog.start()

    assert exited.wait(3)
    assert dog.steps == ["silence", "halt", "interrupt-unhandled", "exit"]


def test_a_stopped_watchdog_takes_no_further_step():
    dog, calls, exited = _watchdog(_FakeProbe(), signal_grace=5)
    dog.start()
    time.sleep(0.2)

    dog.stop()
    dog.join(1)

    assert [name for name, _, _ in calls] == ["silence", "halt"]
    assert not exited.is_set()


def test_request_halt_raises_the_shared_latch():
    run_halt.reinitialiser()
    try:
        wd.request_halt("desktop pid 1: exited")

        halt = run_halt.arret_demande()
        assert halt["code"] == run_halt.DESKTOP_GONE
        assert halt["detail"] == "desktop pid 1: exited"
    finally:
        run_halt.reinitialiser()


def test_interrupt_main_leaves_an_unhandled_sigint_alone(monkeypatch):
    # With the C default action, raising SIGINT would kill the process on the spot: that is the
    # last step's job, after its grace, not this one's.
    sent = []
    monkeypatch.setattr(wd.signal, "getsignal", lambda signum: signal.SIG_DFL)
    monkeypatch.setattr(wd.signal, "raise_signal", lambda signum: sent.append(signum), raising=False)
    monkeypatch.setattr(wd.signal, "pthread_kill", lambda *args: sent.append(args), raising=False)

    assert wd.interrupt_main() is False
    assert sent == []


def test_interrupt_main_sends_sigint_to_a_handler(monkeypatch):
    sent = []
    monkeypatch.setattr(wd.signal, "getsignal", lambda signum: signal.default_int_handler)
    monkeypatch.setattr(wd.signal, "raise_signal", lambda signum: sent.append(signum), raising=False)
    monkeypatch.setattr(wd.signal, "pthread_kill", lambda ident, signum: sent.append(signum), raising=False)

    assert wd.interrupt_main() is True
    assert sent == [signal.SIGINT]


@pytest.mark.parametrize("value", [None, "", "not-a-pid", "0", "-3"])
def test_nothing_is_watched_without_a_desktop_pid(value):
    environ = {} if value is None else {wd.OWNER_PID_ENV: value}

    assert wd.start_owner_watchdog("fake_bridge", environ=environ) is None


def test_a_bridge_never_watches_itself():
    assert wd.start_owner_watchdog("fake_bridge", environ={wd.OWNER_PID_ENV: str(os.getpid())}) is None


# --------------------------------------------------------------- real probe, real processes

def _run_python(code: str, *args: str, timeout: float = 30) -> str:
    result = subprocess.run(
        [sys.executable, "-c", code, *args],
        cwd=str(CORE), capture_output=True, text=True, timeout=timeout,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


_PROBE_PARENT = (
    "import os\n"
    "from bridges.common.runtime.owner_watchdog import open_owner_probe\n"
    "p = open_owner_probe(os.getppid())\n"
    "print(p.watchable, p.wait(0.2), p.gone_reason)\n"
)


def test_the_probe_sees_a_living_owner_alive():
    # The child watches its parent -- this test process: older than it, and alive throughout.
    assert _run_python(_PROBE_PARENT) == "True False None"


def test_the_probe_sees_a_missing_pid_as_gone():
    probe = wd.open_owner_probe(2**31 - 4)
    try:
        assert probe.wait(0) is True
        assert probe.gone_reason == "no such process"
    finally:
        probe.close()


@pytest.mark.skipif(sys.platform != "win32", reason="PID reuse is checked through Windows handles")
def test_a_process_younger_than_us_is_a_reused_pid():
    # Alive, but created after this process: it cannot be the one that spawned us. That is what a
    # PID reused between the desktop's death and the opening of the handle looks like.
    younger = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        time.sleep(0.2)
        probe = wd.open_owner_probe(younger.pid)
        assert probe.gone_reason == "pid reused by a newer process"
        assert probe.wait(0) is True
        assert younger.poll() is None, "the younger process is still alive"
        probe.close()
    finally:
        younger.kill()
        younger.wait(10)


# --------------------------------------------------------------------- one real orphan

# The fake desktop: spawns the bridge the way Electron does (pipes on all three streams, its own
# PID in TAKTIK_DESKTOP_PID), waits until the bridge runs, then dies without a word.
_FAKE_DESKTOP = r'''
import os, subprocess, sys, time
core, fixture_dir, marker, config = sys.argv[1:5]
boot = """
import sys
core, fixture_dir, config = sys.argv[1:4]
sys.path[:0] = [core, fixture_dir]
from bridges.common.runtime import owner_watchdog as w
w.POLL_INTERVAL_S = 0.1
w.SIGNAL_GRACE_S = 1.0
w.HARD_EXIT_GRACE_S = 1.5
from bridges import launcher
launcher.BRIDGE_MODULES['fake_orphan_bridge'] = '_fake_orphan_bridge'
sys.argv = ['launcher.py', 'fake_orphan_bridge', config]
launcher.main()
"""
env = dict(os.environ, TAKTIK_DESKTOP_PID=str(os.getpid()))
bridge = subprocess.Popen(
    [sys.executable, "-c", boot, core, fixture_dir, config],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=core,
)
print(bridge.pid, flush=True)
deadline = time.time() + 60
while time.time() < deadline:
    if os.path.exists(marker) and "ready" in open(marker, encoding="utf-8").read():
        break
    time.sleep(0.05)
os._exit(0)
'''


class _ProcessWatch:
    """Follows a process that is not our child: exit and, on Windows, its exit code."""

    def __init__(self, pid: int):
        self.pid = pid
        self._handle = None
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            self._k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self._k32.OpenProcess.restype = wintypes.HANDLE
            self._k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
            self._k32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
            self._k32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
            self._k32.CloseHandle.argtypes = (wintypes.HANDLE,)
            self._handle = self._k32.OpenProcess(0x00100000 | 0x1000, False, pid)
            self._ctypes, self._wintypes = ctypes, wintypes

    def wait_exit(self, timeout_s: float) -> bool:
        if self._handle:
            return self._k32.WaitForSingleObject(self._handle, int(timeout_s * 1000)) == 0
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                os.kill(self.pid, 0)
            except ProcessLookupError:
                return True
            time.sleep(0.05)
        return False

    def exit_code(self):
        if not self._handle:
            return None
        code = self._wintypes.DWORD()
        self._k32.GetExitCodeProcess(self._handle, self._ctypes.byref(code))
        return code.value

    def kill(self) -> None:
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/pid", str(self.pid), "/F"], capture_output=True)
            else:
                os.kill(self.pid, signal.SIGKILL)
        except Exception:
            pass

    def close(self) -> None:
        if self._handle:
            self._k32.CloseHandle(self._handle)


@pytest.mark.parametrize(
    "mode, last_note, exit_code, within_s",
    [
        # Reads the latch: ends at the next decision point, well before the signal.
        ("latch", "latch:desktop_gone", 0, 0.9),
        # Asleep in time.sleep with a stop handler: woken by the signal after its grace.
        ("signal", "signal", 0, 2.4),
        # A handler that only reports: nothing stops it but the last step.
        ("stuck", "signal-ignored", wd.EXIT_CODE_ORPHANED, 3.9),
    ],
)
def test_an_orphan_bridge_stops_after_its_desktop_dies(tmp_path, mode, last_note, exit_code, within_s):
    marker = tmp_path / "marker.txt"
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"marker": str(marker), "mode": mode}), encoding="utf-8")

    desktop = subprocess.Popen(
        [sys.executable, "-c", _FAKE_DESKTOP, str(CORE), str(FIXTURE_DIR), str(marker), str(config)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    bridge = None
    try:
        bridge = _ProcessWatch(int(desktop.stdout.readline()))
        desktop.wait(timeout=90)
        died_at = time.monotonic()
        assert "ready" in marker.read_text(encoding="utf-8").split(), "the bridge never started"

        assert bridge.wait_exit(within_s + 10), f"the orphan ({mode}) was still running"
        elapsed = time.monotonic() - died_at

        notes = marker.read_text(encoding="utf-8").split()
        assert notes[-1] == last_note, notes
        # One poll, the graces of the steps before its own, and room for a slow machine.
        assert elapsed < within_s + 3, f"{mode}: {elapsed:.1f} s"
        if sys.platform == "win32":
            assert bridge.exit_code() == exit_code
    finally:
        if desktop.poll() is None:
            desktop.kill()
        if bridge is not None:
            if not bridge.wait_exit(0):
                bridge.kill()
            bridge.close()
