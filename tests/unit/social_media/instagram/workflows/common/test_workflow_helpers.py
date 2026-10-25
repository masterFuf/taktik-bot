import json
from types import SimpleNamespace

from taktik.core.social_media.instagram.workflows.common.workflow_helpers import (
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
        "taktik.core.social_media.instagram.workflows.common.workflow_helpers.time.time",
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


def test_a_page_left_open_after_the_restart_is_said(monkeypatch):
    """After the restart, a page detected and left open (here Instagram checking the account, a
    real capture of 410 in French) was logged as info, `closed=False`, and the session start went
    on as if the screen were clear. It is now a warning that names the page and what follows."""
    from loguru import logger
    from uiautomator2.xpath import XPathEntry

    from taktik.core.shared.diagnostics import run_halt
    from taktik.core.social_media.instagram.ui.selectors import locales
    from unit.paths import CORE

    challenge = (CORE / "tests/unit/social_media/instagram/fixtures/ig410_fr_account_challenge.xml"
                 ).read_text(encoding="utf-8")

    class _Phone:
        wait_timeout = 1.0

        def __init__(self):
            self.gestures = []
            self.xpath = XPathEntry(self)

        def dump_hierarchy(self, *_a, **_k):
            return challenge

        def app_current(self):
            return {"package": "com.instagram.android",
                    "activity": "com.instagram.challenge.activity.ChallengeActivity"}

        def press(self, key):
            self.gestures.append(key)

        def click(self, *args):
            self.gestures.append(args)

    phone = _Phone()
    lines = []
    sink = logger.add(lambda message: lines.append(message.record["message"]), level="WARNING")
    before = locales.active_locale()
    locales.set_active_locale("fr")
    run_halt.reinitialiser()
    try:
        WorkflowHelpers(SimpleNamespace(actions=SimpleNamespace(device=phone)))._handle_post_restart_popups()
    finally:
        logger.remove(sink)
        locales.set_active_locale(before)
        run_halt.reinitialiser()

    assert any("account_challenge detected and left open" in line for line in lines)
    assert phone.gestures == []
