import json
from types import SimpleNamespace

from taktik.core.social_media.instagram.workflows.support.workflow_helpers import (
    WorkflowHelpers,
)


def test_finalize_session_emits_frozen_duration(monkeypatch, capsys):
    automation = SimpleNamespace(
        session_finalized=False,
        stats={"start_time": 100.2},
        current_session_id=None,
    )
    helpers = WorkflowHelpers(automation)
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.workflows.support.workflow_helpers.time.time",
        lambda: 145.9,
    )
    monkeypatch.setattr(helpers, "_close_instagram", lambda: None)

    helpers.finalize_session(
        status="COMPLETED",
        reason="Session action cap reached (75/75)",
    )

    message = json.loads(capsys.readouterr().out.strip())
    assert message == {
        "type": "session_stop",
        "status": "COMPLETED",
        "reason": "Session action cap reached (75/75)",
        "duration_seconds": 45,
    }
    assert automation.session_finalized is True
