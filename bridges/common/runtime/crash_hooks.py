"""Last-resort crash reporting for bridge processes.

Every bridge is launched by `bridges/launcher.py`, which called `module.main()` with no guard and
no `sys.excepthook`. An exception nobody caught therefore printed a raw traceback on stderr and
exited 1: the desktop saw a dead process and an exit code, never a cause. Bridges that do have a
top-level `try` (the generic entrypoint, the TikTok and Threads dispatchers) send `str(exc)` and
no traceback; the ones that don't (`taktik_agent`, anything raising during import) send nothing.

These hooks are the floor under all of them. They emit ONE machine-readable event on stdout and
keep the human traceback on stderr, where the desktop's per-run log already captures it.

Written with `os.write` on a duplicated stdout descriptor and no project imports on purpose: this
has to work when the failure IS an import error, and when loguru or a stdout wrapper is the thing
that broke.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import traceback
from typing import Any

#: Tail of the traceback kept in the event. The cause is at the end (most recent call last), and
#: an unbounded traceback can be megabytes when a recursion blew up.
MAX_TRACEBACK_CHARS = 8000

_installed = False
_bridge_name: str | None = None
_stdout_fd: int | None = None


def _write_event(payload: dict[str, Any]) -> None:
    """Write one JSON line to the real stdout, swallowing every failure."""
    try:
        raw = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
    except Exception:
        return
    for fd in (_stdout_fd, 1):
        if fd is None:
            continue
        try:
            os.write(fd, raw)
            return
        except (OSError, ValueError):
            continue


def _format_traceback(exc_type, exc_value, exc_traceback) -> str:
    try:
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    except Exception:
        text = f"{exc_type.__name__}: {exc_value}"
    return text[-MAX_TRACEBACK_CHARS:]


def report_unhandled(exc_type, exc_value, exc_traceback, *, thread: str | None = None) -> None:
    """Emit the crash event for one uncaught exception."""
    payload: dict[str, Any] = {
        "type": "error",
        "error_code": "UNHANDLED_EXCEPTION",
        "error": f"{getattr(exc_type, '__name__', 'Exception')}: {exc_value}",
        "traceback": _format_traceback(exc_type, exc_value, exc_traceback),
    }
    if _bridge_name:
        payload["bridge"] = _bridge_name
    if thread:
        payload["thread"] = thread
    _write_event(payload)


def _excepthook(exc_type, exc_value, exc_traceback) -> None:
    # A Ctrl+C is not a crash: bridges treat it as a clean stop and finalize their session.
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    report_unhandled(exc_type, exc_value, exc_traceback)
    # Keep the readable traceback on stderr — that is what lands in the desktop run log.
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def _threading_excepthook(args) -> None:
    if issubclass(args.exc_type, SystemExit):
        return
    thread_name = getattr(args.thread, "name", None)
    report_unhandled(args.exc_type, args.exc_value, args.exc_traceback, thread=thread_name)
    try:
        traceback.print_exception(args.exc_type, args.exc_value, args.exc_traceback)
    except Exception:
        pass


def install_crash_hooks(bridge_name: str | None = None) -> None:
    """Install the process-wide hooks. Idempotent; safe to call from any entrypoint."""
    global _installed, _bridge_name, _stdout_fd

    _bridge_name = bridge_name or _bridge_name

    if _installed:
        return

    try:
        _stdout_fd = os.dup(1)
    except Exception:
        _stdout_fd = None

    sys.excepthook = _excepthook
    # Threads die silently by default: a watchdog or a capture thread raising took its own
    # traceback with it and left the main loop running against a dead helper.
    if hasattr(threading, "excepthook"):
        threading.excepthook = _threading_excepthook

    _installed = True
