"""A cold DM Instagram shows waiting to be sent is neither sent nor failed.

The conversation is read after Send by the check of every DM send (`reply_check.reply_outcome`,
proven on the captures in `workflows/dm/test_dm_send_waiting_to_be_sent.py`). A message waiting
(no network) leaves by itself once the network is back: the run does not count it as sent, does
not announce it (`cold_dm_sent`), and writes the marker that keeps any later run from sending it
again (`sent_dms`, not a success).
"""

from __future__ import annotations

import pytest

from taktik.core.social_media.instagram.workflows.cold_dm import results
from taktik.core.social_media.instagram.workflows.cold_dm import workflow as module
from taktik.core.social_media.instagram.workflows.dm.reply_check import ReplyOutcome


@pytest.fixture
def markers(monkeypatch):
    written = {"sent": [], "pending": []}
    monkeypatch.setattr(results, "record_sent_dm",
                        lambda account_id, recipient, message, success, error, session_id:
                        written["sent"].append((recipient, success)))
    monkeypatch.setattr(results, "record_pending_dm",
                        lambda account_id, recipient, message, session_id:
                        written["pending"].append((recipient, message)))
    return written


def _run(monkeypatch, outcome):
    announced = []
    monkeypatch.setattr(module, "look_for_action_block", lambda *args, **kwargs: False)
    monkeypatch.setattr(module, "ProblematicPageDetector", lambda device: None)
    monkeypatch.setattr(module, "wait_before_next_cold_dm", lambda **kwargs: None)
    workflow = module.ColdDMWorkflow(object(), object(), sent=lambda **line: announced.append(line))
    workflow.open_recipient_profile = lambda recipient: True
    workflow.open_dm_from_profile = lambda policy=None, recipient=None: True
    workflow.send_message = lambda message: outcome
    workflow.go_home = lambda: None
    workflow.filter_pending_recipients = lambda recipients, account_id: list(recipients)
    workflow._detect_app_language = lambda: None
    return workflow.run(["demo_recipient"], ["Hello there"], account_id=7), announced


def test_a_cold_dm_waiting_is_marked_never_counted_nor_announced(monkeypatch, markers):
    summary, announced = _run(monkeypatch, ReplyOutcome.PENDING)

    assert (summary["dms_sent"], summary["dms_success"], summary["dms_failed"], summary["dms_pending"]) \
        == (0, 0, 0, 1)
    assert announced == []
    assert markers == {"sent": [], "pending": [("demo_recipient", "Hello there")]}


def test_a_cold_dm_the_conversation_shows_is_sent(monkeypatch, markers):
    summary, announced = _run(monkeypatch, ReplyOutcome.SENT)

    assert (summary["dms_sent"], summary["dms_success"], summary["dms_pending"]) == (1, 1, 0)
    assert [line["username"] for line in announced] == ["demo_recipient"]
    assert markers == {"sent": [("demo_recipient", True)], "pending": []}


def test_a_cold_dm_that_never_showed_is_a_failure_with_no_marker(monkeypatch, markers):
    summary, announced = _run(monkeypatch, ReplyOutcome.NOT_SENT)

    assert (summary["dms_sent"], summary["dms_failed"], summary["dms_pending"]) == (0, 1, 0)
    assert announced == [] and markers == {"sent": [], "pending": []}
