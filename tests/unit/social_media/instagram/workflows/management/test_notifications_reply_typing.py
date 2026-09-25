"""A reply from the notifications keeps the "@name " Instagram prefills, and is checked with it."""

import pytest

from taktik.core.social_media.instagram.workflows.management.notifications import notifications_workflow as nw


@pytest.mark.parametrize("composer,mention", [
    ("@ana ", "@ana "),
    ("@ana", "@ana "),
    ("Ajouter un commentaire…", ""),   # an empty composer reads its hint
    ("", ""),
    ("@", ""),
])
def test_the_prefilled_mention_is_recognised(composer, mention):
    assert nw._reply_mention(composer) == mention


def test_the_reply_is_checked_after_the_mention(monkeypatch):
    calls = []
    workflow = nw.NotificationsEngagementWorkflow.__new__(nw.NotificationsEngagementWorkflow)
    workflow.device = object()
    workflow.device_id = "PHONE-1"
    workflow.logger = type("L", (), {"warning": lambda *a, **k: None, "error": lambda *a, **k: None})()
    monkeypatch.setattr(nw, "ensure_taktik_keyboard", lambda _device_id: True)
    monkeypatch.setattr(nw, "tap_element_human", lambda *a, **k: True)
    monkeypatch.setattr(nw.time, "sleep", lambda _s: None)
    monkeypatch.setattr(nw, "read_focused_text", lambda device: "@ana ")
    monkeypatch.setattr(nw, "type_text_checked",
                        lambda device, device_id, text, prefix="": calls.append((text, prefix)) or True)

    assert workflow._type_into(object(), "merci !") is True
    assert calls == [("merci !", "@ana ")]
