"""Duplex desktop client for premium per-profile decisions.

The public Bot owns no decision strategy. In ``decide`` mode it sends facts to Electron over
stdout and waits for one concrete plan on stdin. The reader is a single daemon for the whole
bridge: a timed-out request can therefore never leave a stale thread that steals the next reply.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import uuid
from typing import Any, BinaryIO, Callable, Mapping, Optional


class DesktopProfileDecisionClient:
    """Request/response transport over the bridge's existing JSON-lines stdio channel."""

    def __init__(
        self,
        *,
        ipc: Any,
        input_stream: Optional[BinaryIO] = None,
        timeout_seconds: float = 8.0,
        log: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self._ipc = ipc
        self._input = input_stream or sys.stdin.buffer
        self._timeout_seconds = max(0.1, float(timeout_seconds))
        self._log = log or (lambda _level, _message: None)
        self._lock = threading.Lock()
        self._pending: dict[str, dict[str, Any]] = {}
        self._closed = False
        self._stop = threading.Event()
        self._reader = threading.Thread(
            target=self._read_responses,
            name="instagram-profile-decision-reader",
            daemon=True,
        )
        self._reader.start()

    def close(self, join_timeout: float = 1.0) -> None:
        """Stop the response reader and release every waiting decision request.

        The real desktop stdin is polled at the OS pipe level, so this does not need
        to close Python's global buffered stdin from another thread. Test/dummy
        streams can expose ``cancel_read()`` to wake their own blocking ``readline``.
        """
        self._stop.set()
        self._close_pending()
        cancel_read = getattr(self._input, "cancel_read", None)
        if callable(cancel_read):
            try:
                cancel_read()
            except Exception:
                pass
        if (
            self._reader.is_alive()
            and threading.current_thread() is not self._reader
        ):
            self._reader.join(max(0.0, float(join_timeout)))

    def request_plan(self, facts: Mapping[str, Any]) -> dict[str, Any]:
        """Send profile facts and wait for Electron's concrete plan.

        Returns a normalized failure dictionary on timeout/disconnect instead of raising. The
        interaction engine treats every such failure as an empty, fail-closed decision plan.
        """
        request_id = uuid.uuid4().hex
        event = threading.Event()
        slot: dict[str, Any] = {"event": event, "response": None}
        with self._lock:
            if self._closed:
                return {"ok": False, "error": "desktop decision channel is closed"}
            self._pending[request_id] = slot

        try:
            self._ipc.send(
                "agent_profile_decision_request",
                requestId=request_id,
                **dict(facts),
            )
        except Exception as exc:  # noqa: BLE001 - transport failure is a closed decision
            with self._lock:
                self._pending.pop(request_id, None)
            self._log("warning", f"Profile decision request could not be sent: {exc}")
            return {"ok": False, "error": "desktop decision request could not be sent"}

        if not event.wait(self._timeout_seconds):
            with self._lock:
                self._pending.pop(request_id, None)
            self._log(
                "warning",
                f"Profile decision timed out after {self._timeout_seconds:.1f}s",
            )
            return {"ok": False, "error": "desktop decision timed out"}

        response = slot.get("response")
        if not isinstance(response, dict):
            return {"ok": False, "error": "desktop decision channel closed"}
        return response

    def _dispatch_response_line(self, raw_line: Any) -> None:
        try:
            if isinstance(raw_line, bytes):
                raw_line = raw_line.decode("utf-8")
            message = json.loads(str(raw_line).strip())
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if not isinstance(message, dict):
            return
        if message.get("type") != "agent_profile_decision_response":
            return
        request_id = message.get("requestId")
        if not isinstance(request_id, str):
            return
        with self._lock:
            slot = self._pending.pop(request_id, None)
        if slot is not None:
            slot["response"] = message
            slot["event"].set()

    def _read_os_pipe(self) -> bool:
        """Read a real stdin pipe without ever blocking in ``BufferedReader.readline``.

        Returns False when the supplied stream has no pollable file descriptor, in
        which case the injectable/test-stream fallback is used.
        """
        try:
            fd = int(self._input.fileno())
        except (AttributeError, OSError, TypeError, ValueError):
            return False

        buffer = b""
        if os.name == "nt":
            try:
                import ctypes
                import msvcrt
                from ctypes import wintypes

                handle = msvcrt.get_osfhandle(fd)
                peek = ctypes.WinDLL("kernel32", use_last_error=True).PeekNamedPipe
                peek.argtypes = [
                    wintypes.HANDLE,
                    wintypes.LPVOID,
                    wintypes.DWORD,
                    wintypes.LPDWORD,
                    wintypes.LPDWORD,
                    wintypes.LPDWORD,
                ]
                peek.restype = wintypes.BOOL
            except Exception:
                return False

            while not self._stop.is_set():
                available = wintypes.DWORD()
                if not peek(handle, None, 0, None, ctypes.byref(available), None):
                    error_code = ctypes.get_last_error()
                    # Broken/closing pipe: normal desktop shutdown.
                    if error_code in (109, 232):
                        break
                    return False
                if available.value == 0:
                    self._stop.wait(0.05)
                    continue
                chunk = os.read(fd, min(int(available.value), 65536))
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    raw_line, buffer = buffer.split(b"\n", 1)
                    self._dispatch_response_line(raw_line)
        else:
            try:
                import select
            except ImportError:
                return False
            while not self._stop.is_set():
                readable, _, _ = select.select([fd], [], [], 0.05)
                if not readable:
                    continue
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    raw_line, buffer = buffer.split(b"\n", 1)
                    self._dispatch_response_line(raw_line)

        if buffer.strip():
            self._dispatch_response_line(buffer)
        return True

    def _close_pending(self) -> None:
        with self._lock:
            self._closed = True
            pending = list(self._pending.values())
            self._pending.clear()
        for slot in pending:
            slot["event"].set()

    def _read_responses(self) -> None:
        try:
            if self._read_os_pipe():
                return
            while not self._stop.is_set():
                raw_line = self._input.readline()
                if not raw_line:
                    break
                self._dispatch_response_line(raw_line)
        except Exception as exc:  # noqa: BLE001 - transport failure must fail closed, not crash Bot
            self._log("warning", f"Desktop decision response reader stopped: {exc}")
        finally:
            self._close_pending()


__all__ = ["DesktopProfileDecisionClient"]
