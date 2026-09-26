"""A Lab session closes on the command without a message: the app reads the process exit.

It used to answer `session_closed`, which `CartographyActionSessionService` never read; the
session's end is logged from the process `close` event and its exit code.
"""

import io
import types

import pytest

from bridges.compat.diagnostics.runtime.action_test import session


@pytest.mark.parametrize("command", ["shutdown", "stop", "close"])
def test_a_close_command_ends_the_session_silently(monkeypatch, command):
    import taktik.core.shared.device.manager as manager

    class _DeviceManager:
        def __init__(self, device_id):
            self.device = object()

        def connect(self, verify_atx=False):
            return True

    emitted = []
    monkeypatch.setattr(manager, "DeviceManager", _DeviceManager)
    config = {"device_id": "fake", "platform": "instagram"}
    monkeypatch.setattr(session, "_load_platform_runtime", lambda platform: ({}, lambda d: d, lambda f: {}))
    monkeypatch.setattr(session, "_detect_and_optimize_selectors", lambda *a, **k: {})
    monkeypatch.setattr(session, "_install_selector_tracer",
                        lambda *a, **k: types.SimpleNamespace(reset=lambda: None))
    monkeypatch.setattr(session, "emit", emitted.append)
    monkeypatch.setattr(session.sys, "stdin", io.StringIO(f'{{"type": "{command}"}}\n{{"type": "run_action"}}\n'))

    session.run_action_session_bridge(config)

    assert [payload["type"] for payload in emitted] == ["session_ready"]
