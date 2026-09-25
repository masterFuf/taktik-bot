"""`get_conversation_info` reads the group member count once, without waiting for it.

A one-to-one conversation has no member count, so the former polled read waited out its whole
timeout on every call: in the DM workflow's conversation read and in the send guard
`is_conversation_with`. The answer is unchanged; only the wait goes.
"""

import types

import pytest

import taktik.core.social_media.tiktok.actions.core.base_action as base_action
from taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions import DMActions
from taktik.core.social_media.tiktok.ui.selectors.surfaces.conversation import CONVERSATION_SELECTORS


class _Element:
    def __init__(self, text):
        self.text = text


class _Selection:
    def __init__(self, text):
        self._text = text

    @property
    def exists(self):
        return self._text is not None

    def get_text(self):
        return self._text

    def all(self):
        return [] if self._text is None else [_Element(self._text)]


class _Device:
    """Answers the conversation name, and the member count when there is one."""

    def __init__(self, member_count=None):
        self.member_count = member_count
        self.member_count_reads = 0

    def xpath(self, selector):
        if selector in CONVERSATION_SELECTORS.group_member_count:
            self.member_count_reads += 1
            return _Selection(self.member_count)
        if selector == CONVERSATION_SELECTORS.conversation_name[0]:
            return _Selection("Alex")
        return _Selection(None)


@pytest.fixture
def sleeps(monkeypatch):
    calls = []
    monkeypatch.setattr(base_action.time, "sleep", lambda seconds: calls.append(seconds))
    return calls


def _actions(device):
    dm = DMActions.__new__(DMActions)
    dm.device = device
    dm.conversation_selectors = CONVERSATION_SELECTORS
    dm.logger = types.SimpleNamespace(debug=lambda *a, **k: None, warning=lambda *a, **k: None)
    return dm


def test_a_one_to_one_conversation_is_read_once_without_waiting(sleeps):
    device = _Device()
    info = _actions(device).get_conversation_info()
    assert info == {"name": "Alex", "is_group": False, "member_count": None}
    assert device.member_count_reads == len(CONVERSATION_SELECTORS.group_member_count)
    assert sleeps == []


def test_a_group_still_reports_its_member_count(sleeps):
    info = _actions(_Device(member_count="29 membres")).get_conversation_info()
    assert info == {"name": "Alex", "is_group": True, "member_count": 29}
    assert sleeps == []
