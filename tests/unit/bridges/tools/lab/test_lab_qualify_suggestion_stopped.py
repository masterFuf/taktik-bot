"""The Lab's qualification of a suggested profile says a stop caught it: not a success.

`notifications.qualify_suggestion_profile` read success as « not an error »: a profile the run's stop
caught (STOPPED) would have read as qualified. The pipeline is the production one, played here by its
outcome; the session and the screen reads are the stand-ins.
"""

from contextlib import contextmanager
from types import SimpleNamespace

from bridges.tools.lab.actions.instagram import notifications as lab_notifications
from taktik.core.social_media.instagram.actions.base.base_business.profile_processing import (
    ProfileProcessingResult,
)


def _qualify(monkeypatch, status):
    @contextmanager
    def _session(p, source):
        yield None

    pipeline = SimpleNamespace(
        wait_for_profile=lambda timeout=0: True,
        read_username=lambda: "alice",
        process=lambda username: ProfileProcessingResult(status, username),
    )
    monkeypatch.setattr(lab_notifications, "lab_suggestion_session", _session)
    monkeypatch.setattr(lab_notifications, "_pipeline", lambda a, p, session_id=None: pipeline)
    return lab_notifications.qualify_suggestion_profile(SimpleNamespace(), {})


def test_a_stopped_qualification_is_not_a_success(monkeypatch):
    result = _qualify(monkeypatch, ProfileProcessingResult.STOPPED)

    assert result["success"] is False
    assert result["details"]["status"] == "stopped"


def test_a_qualified_profile_is_a_success(monkeypatch):
    assert _qualify(monkeypatch, ProfileProcessingResult.SUCCESS)["success"] is True
