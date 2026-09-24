"""The Cartography Lab session serves one action after another in the same process.

A bridge process serves one run and starts with the run's stop lock lifted; a Lab session is one
process for many actions. Without a lift per action, a block or a lost phone seen by one action
ended every workflow action after it while the session stayed open (2026-09-24).
"""

import io
import json
import types

from bridges.compat.diagnostics.runtime.action_test import session
from taktik.core.shared.diagnostics import run_halt


def test_each_action_of_a_session_starts_without_the_previous_stop(monkeypatch):
    import taktik.core.shared.device.manager as manager

    class _DeviceManager:
        def __init__(self, device_id):
            self.device = object()

        def connect(self, verify_atx=False):
            return True

    locks_seen = []

    def _execute_action(registry, action_id, *a, **k):
        locks_seen.append(run_halt.arret_demande())
        # The first action runs into Instagram's rate-limit dialog.
        run_halt.demander_arret(run_halt.ACTION_BLOCKED, "try_again_later_page")

    monkeypatch.setattr(manager, "DeviceManager", _DeviceManager)
    monkeypatch.setattr(session, "_load_config", lambda: {"device_id": "fake", "platform": "instagram"})
    monkeypatch.setattr(session, "_load_platform_runtime",
                        lambda platform: ({"detection.dump_xml": None}, lambda d: d, lambda f: {}))
    monkeypatch.setattr(session, "_detect_and_optimize_selectors", lambda *a, **k: {})
    monkeypatch.setattr(session, "_install_selector_tracer",
                        lambda *a, **k: types.SimpleNamespace(reset=lambda: None))
    monkeypatch.setattr(session, "_execute_action", _execute_action)
    monkeypatch.setattr(session, "emit", lambda payload: None)
    command = json.dumps({"type": "run_action", "action_id": "detection.dump_xml", "request_id": "r"})
    monkeypatch.setattr(session.sys, "stdin", io.StringIO(f"{command}\n{command}\n" + '{"type": "close"}\n'))

    try:
        session.run_action_session_bridge()
    finally:
        run_halt.reinitialiser()

    assert locks_seen == [None, None]
