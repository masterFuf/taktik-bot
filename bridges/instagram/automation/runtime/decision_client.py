"""Duplex desktop client for premium per-profile decisions.

The public Bot owns no decision strategy. In ``decide`` mode it sends facts to Electron over
stdout and waits for one concrete plan on stdin. The reader is a single daemon for the whole
bridge: a timed-out request can therefore never leave a stale thread that steals the next reply.
"""

from __future__ import annotations

import json
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
        self._reader = threading.Thread(
            target=self._read_responses,
            name="instagram-profile-decision-reader",
            daemon=True,
        )
        self._reader.start()

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

    def _read_responses(self) -> None:
        try:
            while True:
                raw_line = self._input.readline()
                if not raw_line:
                    break
                try:
                    if isinstance(raw_line, bytes):
                        raw_line = raw_line.decode("utf-8")
                    message = json.loads(str(raw_line).strip())
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if not isinstance(message, dict):
                    continue
                if message.get("type") != "agent_profile_decision_response":
                    continue
                request_id = message.get("requestId")
                if not isinstance(request_id, str):
                    continue
                with self._lock:
                    slot = self._pending.pop(request_id, None)
                if slot is not None:
                    slot["response"] = message
                    slot["event"].set()
        except Exception as exc:  # noqa: BLE001 - transport failure must fail closed, not crash Bot
            self._log("warning", f"Desktop decision response reader stopped: {exc}")
        finally:
            with self._lock:
                self._closed = True
                pending = list(self._pending.values())
                self._pending.clear()
            for slot in pending:
                slot["event"].set()


__all__ = ["DesktopProfileDecisionClient"]
