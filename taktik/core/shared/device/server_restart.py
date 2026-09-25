"""Reads cut by a dying uiautomator2 server are read again on a fresh one.

A uiautomator2 client kills the server it launched when its process exits, without waiting
for it to stop. A process that connects within that second finds the server still answering,
reuses it, and its next call is cut when it dies: `RemoteDisconnected`, which uiautomator2
does not retry (it only retries its own `HTTPError`). Every one-shot Lab action is such a
process. Only reads are retried: a cut gesture may already have landed on the screen.
"""

import http.client
import time
from typing import Any, Callable

from loguru import logger

SERVER_CUT_ERRORS = (ConnectionError, http.client.HTTPException)

READ_ONLY_METHODS = frozenset({
    "deviceInfo", "dumpWindowHierarchy", "takeScreenshot", "exist", "count", "objInfo",
    "getText", "getParent", "childByText", "childByDescription", "childByInstance",
    "getClipboard", "getLastToast", "getLastTraversedText", "waitForExists", "waitUntilGone",
})

_MARKER = "_taktik_reads_survive_server_restart"
_RESTART_ATTEMPTS = 2
_DYING_SERVER_GRACE_S = 1.0


def call_past_a_dying_server(call: Callable[[], Any]) -> Any:
    """Run `call`, and once more after the grace period if a dying server cut it."""
    try:
        return call()
    except SERVER_CUT_ERRORS as exc:
        logger.info(f"uiautomator2 server shutting down ({type(exc).__name__}), trying again")
        time.sleep(_DYING_SERVER_GRACE_S)
        return call()


def retry_cut_reads(device: Any) -> bool:
    """Make the read-only server calls of this uiautomator2 device survive a server restart.

    Returns True when the device is (now) wrapped. A device without `jsonrpc_call` and the
    server start/stop methods (a test double, another driver) is left as it is.
    """
    if getattr(device, _MARKER, False):
        return True
    original_rpc = getattr(device, "jsonrpc_call", None)
    stop = getattr(device, "stop_uiautomator", None)
    start = getattr(device, "start_uiautomator", None)
    if not (callable(original_rpc) and callable(stop) and callable(start)):
        return False

    def jsonrpc_call(method, params=None, timeout=10, *args, **kwargs):
        try:
            return original_rpc(method, params, timeout, *args, **kwargs)
        except SERVER_CUT_ERRORS as exc:
            if method not in READ_ONLY_METHODS:
                raise
            logger.info(f"uiautomator2 server cut {method} ({type(exc).__name__}): restarting it")
            _restart(stop, start)
            return original_rpc(method, params, timeout, *args, **kwargs)

    device.jsonrpc_call = jsonrpc_call
    setattr(device, _MARKER, True)
    return True


def _restart(stop: Callable[[], Any], start: Callable[[], Any]) -> None:
    # While it dies, the old server may still cut the liveness checks of stop/start themselves.
    for attempt in range(_RESTART_ATTEMPTS):
        try:
            stop()
            start()
            return
        except SERVER_CUT_ERRORS:
            if attempt + 1 < _RESTART_ATTEMPTS:
                time.sleep(_DYING_SERVER_GRACE_S)
