"""Stdin stop-command listener for the Instagram Taktik Agent bridge."""

from __future__ import annotations

import json
import sys
import threading

from loguru import logger


def start_agent_stop_listener() -> None:
    def _listen():
        try:
            for raw in sys.stdin:
                line = raw.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    if msg.get("command") == "stop":
                        logger.info("[TaktikAgentBridge] Stop command received via stdin")
                        from bridges.common.runtime import signal_handler as _sig

                        if _sig._workflow and hasattr(_sig._workflow, "stop"):
                            _sig._workflow.stop()
                        break
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass

    t = threading.Thread(target=_listen, daemon=True, name="stdin-stop-listener")
    t.start()
