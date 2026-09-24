"""Stop a bridge cleanly when the desktop app that launched it disappears.

The desktop stops a bridge by killing it and then writing the end of the run itself (session
status, app closed, device released). When the desktop is the one that dies -- a crash, a forced
stop, a window closed without its shutdown -- nothing of that happens: the bridge keeps driving
the phone, its JSON events go into a pipe nobody reads, and the run ends hours later as
``run_lost``, dated at the next start of the app.

**Who the owner is.** The desktop puts its own PID in ``TAKTIK_DESKTOP_PID`` for every bridge it
spawns (``BridgeProcessRunner.ts``, the one place every spawn goes through). The bridge's parent
is NOT the owner: in production ``taktik_launcher.exe`` is a PyInstaller one-file build, whose
bootloader is the parent and survives the desktop; in a Windows venv the parent is the
``python.exe`` redirector. Without the variable (the bot run on its own), nothing is watched.

**Why not the PID alone.** Windows reuses PIDs quickly. On Windows the watchdog holds a handle on
the owner, which pins its process object for as long as we wait on it, and first checks that the
owner was created before this process: a PID reused before the handle was opened belongs to a
process created after the owner died, therefore after us. On POSIX the desktop is the direct
parent (no bootloader in development), and a change of ``getppid()`` is immune to reuse; when it
is not the direct parent, ``kill(pid, 0)`` is polled, without the reuse check.

**How it stops: the existing stop, in three steps.** No new stop path is invented here.

1. At once: stdout/stderr are pointed at the null device (the pipes are dead, and a ``print`` on
   a dead pipe raises -- which would abort the very finalisation this is trying to reach), then
   the shared halt latch is raised with ``DESKTOP_GONE``. The runs that read it (Instagram
   sessions, TikTok video and followers loops) end through their normal path at the next
   decision point: motive written to the session, app closed.
2. After ``SIGNAL_GRACE_S``: SIGINT is delivered to the main thread -- what Ctrl+C does, and
   what each family already handles (the Instagram automation finalizes its session, TikTok
   scraping stops its workflow, the others unwind through ``KeyboardInterrupt`` and their
   ``finally`` blocks). On Windows ``raise_signal`` also wakes a main thread asleep in
   ``time.sleep``, which ``_thread.interrupt_main`` does not.
3. After ``HARD_EXIT_GRACE_S`` more: ``os._exit``. A last resort for a main thread stuck in a
   blocking call, or a family whose handler only reports: an orphan must not run unbounded. It
   is what the desktop's own stop does from the start (``taskkill /F``).

A Job Object on the desktop side was set aside: the kernel would kill the bridge in the middle
of a gesture with no end of session, it needs a native module, and it is Windows-only. The end
of stdin was set aside too: several bridges already read stdin (payload, stop orders, decision
replies), a second reader would steal their bytes.
"""

from __future__ import annotations

import os
import signal
import sys
import threading
import time
from typing import Callable, Optional

from loguru import logger

#: Set by the desktop on every bridge it spawns (`BridgeProcessRunner.ts`).
OWNER_PID_ENV = "TAKTIK_DESKTOP_PID"

#: How often the owner is checked. On Windows this only bounds how fast `stop()` is honoured:
#: the wait itself returns the moment the owner exits.
POLL_INTERVAL_S = 1.0

#: Time given to the runs that read the halt latch before the stop signal is sent.
SIGNAL_GRACE_S = 15.0

#: Time given to the stop signal before the process is ended without further ceremony.
HARD_EXIT_GRACE_S = 30.0

#: Exit code of an orphan ended by the last step. Nobody is there to read it; it tells a test,
#: or a later look at an event log, that the watchdog had to go that far.
EXIT_CODE_ORPHANED = 86


# ---------------------------------------------------------------------------- owner probes

class _WindowsOwnerProbe:
    """Holds a handle on the owner; the kernel signals it when the owner exits."""

    _SYNCHRONIZE = 0x00100000
    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    _WAIT_OBJECT_0 = 0x0
    _ERROR_INVALID_PARAMETER = 87

    def __init__(self, pid: int):
        import ctypes
        from ctypes import wintypes

        self._ctypes = ctypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
        k32.GetProcessTimes.restype = wintypes.BOOL
        k32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        k32.WaitForSingleObject.restype = wintypes.DWORD
        k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        k32.CloseHandle.restype = wintypes.BOOL
        k32.GetCurrentProcess.argtypes = ()
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        self._k32 = k32
        self._wintypes = wintypes

        self.pid = pid
        self.gone_reason: Optional[str] = None
        self.watchable = True
        self._handle = None

        handle = k32.OpenProcess(self._SYNCHRONIZE | self._PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            error = ctypes.get_last_error()
            if error == self._ERROR_INVALID_PARAMETER:
                self.gone_reason = "no such process"
            else:
                # Access denied or anything else: the owner may well be alive. Not knowing is
                # not a reason to stop a run.
                self.watchable = False
            return
        self._handle = handle

        owner_created = self._creation_time(handle)
        own_created = self._creation_time(k32.GetCurrentProcess())
        if owner_created is not None and own_created is not None and owner_created > own_created:
            # Created after us, so it cannot have spawned us: the PID was reused after the owner
            # died, before we could hold it.
            self.gone_reason = "pid reused by a newer process"
            self.close()

    def _creation_time(self, handle) -> Optional[int]:
        ft = self._wintypes.FILETIME
        created, exited, kernel, user = ft(), ft(), ft(), ft()
        byref = self._ctypes.byref
        if not self._k32.GetProcessTimes(handle, byref(created), byref(exited), byref(kernel), byref(user)):
            return None
        return (created.dwHighDateTime << 32) | created.dwLowDateTime

    def wait(self, timeout_s: float) -> bool:
        """Block up to `timeout_s`; True as soon as the owner is gone."""
        if self.gone_reason:
            return True
        if self._handle is None:
            time.sleep(timeout_s)
            return False
        result = self._k32.WaitForSingleObject(self._handle, max(0, int(timeout_s * 1000)))
        if result == self._WAIT_OBJECT_0:
            self.gone_reason = "exited"
            return True
        return False

    def close(self) -> None:
        if self._handle:
            self._k32.CloseHandle(self._handle)
            self._handle = None


class _PosixOwnerProbe:
    """Reparenting when the owner is the direct parent, `kill(pid, 0)` otherwise."""

    def __init__(self, pid: int):
        self.pid = pid
        self.watchable = True
        self.gone_reason: Optional[str] = None
        self._direct_parent = os.getppid() == pid
        self._check()

    def _check(self) -> bool:
        if self._direct_parent:
            if os.getppid() != self.pid:
                self.gone_reason = "parent exited (reparented)"
        else:
            try:
                os.kill(self.pid, 0)
            except ProcessLookupError:
                self.gone_reason = "no such process"
            except OSError:
                pass  # EPERM: it exists, under another user
        return self.gone_reason is not None

    def wait(self, timeout_s: float) -> bool:
        if self.gone_reason or self._check():
            return True
        time.sleep(timeout_s)
        return self._check()

    def close(self) -> None:
        pass


def open_owner_probe(pid: int):
    """The probe for this platform, already checked once."""
    if sys.platform == "win32":
        return _WindowsOwnerProbe(pid)
    return _PosixOwnerProbe(pid)


# ------------------------------------------------------------------------- stop steps

def silence_stdio() -> None:
    """Point stdout and stderr at the null device: their reader is dead.

    Everything written from here on (the ``session_stop`` event, logs) used to fail on the dead
    pipe, and a ``print(..., flush=True)`` that raises aborts the finalisation before its DB
    write. Descriptor-level, so ``print``, loguru and ``sys.stdout`` all follow; the IPC writer's
    duplicated descriptor still points at the pipe and already swallows its errors.
    """
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
    except OSError:
        return
    try:
        for fd in (1, 2):
            try:
                os.dup2(devnull, fd)
            except OSError:
                pass
    finally:
        os.close(devnull)


def request_halt(detail: str) -> None:
    """Raise the shared halt latch; the runs that read it end through their normal path."""
    try:
        from taktik.core.shared.diagnostics import run_halt

        run_halt.demander_arret(run_halt.DESKTOP_GONE, detail)
    except Exception:  # noqa: BLE001 -- a missing latch must not stop the next steps
        pass


def interrupt_main() -> bool:
    """Deliver SIGINT to the main thread, as Ctrl+C would. False when nothing would handle it.

    Only when a Python handler is installed (the default one raises KeyboardInterrupt): with the
    C default action, raising the signal would terminate the process on the spot, which is the
    next step's job, not this one's.
    """
    if not callable(signal.getsignal(signal.SIGINT)):
        return False
    try:
        if sys.platform == "win32":
            signal.raise_signal(signal.SIGINT)
        else:
            # Aimed at the main thread so that its blocking call is interrupted (EINTR); a
            # process-wide signal could land on this thread instead.
            signal.pthread_kill(threading.main_thread().ident, signal.SIGINT)
    except (OSError, ValueError, AttributeError):
        return False
    return True


def hard_exit() -> None:
    os._exit(EXIT_CODE_ORPHANED)


# --------------------------------------------------------------------------- watchdog

class OwnerWatchdog(threading.Thread):
    """Watches the owner from a daemon thread and runs the stop steps once it is gone."""

    def __init__(
        self,
        probe,
        *,
        bridge_name: Optional[str] = None,
        poll_interval_s: Optional[float] = None,
        signal_grace_s: Optional[float] = None,
        hard_exit_grace_s: Optional[float] = None,
        silence: Callable[[], None] = silence_stdio,
        halt: Callable[[str], None] = request_halt,
        interrupt: Callable[[], bool] = interrupt_main,
        exit_now: Callable[[], None] = hard_exit,
    ):
        super().__init__(name="taktik-owner-watchdog", daemon=True)
        self._probe = probe
        self._bridge_name = bridge_name or "bridge"
        # Read at construction, not bound as default values: a test (or a later tuning) that
        # changes the module constants must be obeyed.
        self._poll = POLL_INTERVAL_S if poll_interval_s is None else poll_interval_s
        self._signal_grace = SIGNAL_GRACE_S if signal_grace_s is None else signal_grace_s
        self._exit_grace = HARD_EXIT_GRACE_S if hard_exit_grace_s is None else hard_exit_grace_s
        self._silence = silence
        self._halt = halt
        self._interrupt = interrupt
        self._exit_now = exit_now
        self._stopped = threading.Event()
        #: Steps taken, in order. Read by the tests; harmless otherwise.
        self.steps: list[str] = []

    def stop(self) -> None:
        """Stop watching (tests; a bridge never needs to)."""
        self._stopped.set()

    def run(self) -> None:
        try:
            while not self._stopped.is_set():
                if self._probe.wait(self._poll):
                    if not self._stopped.is_set():
                        self._on_owner_gone()
                    return
        except Exception as exc:  # noqa: BLE001 -- a broken watchdog must not take the run down
            logger.warning(f"Owner watchdog stopped watching: {exc}")
        finally:
            self._probe.close()

    def _on_owner_gone(self) -> None:
        detail = f"desktop pid {self._probe.pid}: {self._probe.gone_reason}"
        logger.warning(f"Desktop app gone ({detail}): stopping {self._bridge_name}")

        self._silence()
        self.steps.append("silence")
        self._halt(detail)
        self.steps.append("halt")

        if self._stopped.wait(self._signal_grace):
            return
        # Again: `run_bridge_main` clears the latch when a run starts, and the owner may have died
        # while the bridge was still importing.
        self._halt(detail)
        self.steps.append("interrupt" if self._interrupt() else "interrupt-unhandled")

        if self._stopped.wait(self._exit_grace):
            return
        self.steps.append("exit")
        self._exit_now()


def start_owner_watchdog(bridge_name: Optional[str] = None, environ=None) -> Optional[OwnerWatchdog]:
    """Start watching the desktop named by `TAKTIK_DESKTOP_PID`. None when there is nothing to watch.

    Called once by `bridges/launcher.py`, before the bridge is even imported, so that every
    bridge is covered without a line of its own.
    """
    raw = (environ if environ is not None else os.environ).get(OWNER_PID_ENV)
    if not raw:
        return None
    try:
        pid = int(raw)
    except ValueError:
        logger.warning(f"{OWNER_PID_ENV}={raw!r} is not a PID: the desktop app is not watched")
        return None
    if pid <= 0 or pid == os.getpid():
        return None

    try:
        probe = open_owner_probe(pid)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Cannot watch the desktop app (pid {pid}): {exc}")
        return None
    if not probe.watchable:
        logger.warning(f"Cannot watch the desktop app (pid {pid}): access refused")
        probe.close()
        return None

    watchdog = OwnerWatchdog(probe, bridge_name=bridge_name)
    watchdog.start()
    return watchdog


__all__ = [
    "OWNER_PID_ENV",
    "EXIT_CODE_ORPHANED",
    "OwnerWatchdog",
    "open_owner_probe",
    "start_owner_watchdog",
]
