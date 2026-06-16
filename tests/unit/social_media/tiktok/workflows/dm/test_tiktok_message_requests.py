"""Tests des demandes de messages (inbox v2 phase 3) : scrape + accept/decline/reply."""

import types

from taktik.core.social_media.tiktok.actions.atomic.dm_actions import DMActions
from taktik.core.social_media.tiktok.actions.business.workflows.dm.workflow import (
    DMConfig,
    DMWorkflow,
)
from taktik.core.social_media.tiktok.ui.selectors.surfaces.inbox import INBOX_SELECTORS


# --- scrape (DMActions.get_message_requests) -------------------------------

class _Coll:
    def __init__(self, texts):
        self._t = texts

    @property
    def exists(self):
        return len(self._t) > 0

    @property
    def count(self):
        return len(self._t)

    def __getitem__(self, i):
        return types.SimpleNamespace(get_text=lambda t=self._t[i]: t)


class _Raw:
    def __init__(self, usernames, previews, timestamps):
        self.u, self.p, self.t = usernames, previews, timestamps

    def __call__(self, resourceIdMatches=None, resourceId=None):
        assert resourceId is None
        pat = resourceIdMatches or ''
        if 'z05' in pat:
            return _Coll(self.u)
        if 'l35' in pat:
            return _Coll(self.p)
        if 'l3a' in pat:
            return _Coll(self.t)
        return _Coll([])


def _actions(usernames, previews, timestamps):
    dm = DMActions.__new__(DMActions)
    dm.device = types.SimpleNamespace(_device=_Raw(usernames, previews, timestamps))
    dm.inbox_selectors = INBOX_SELECTORS
    dm.logger = types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None, debug=lambda *a, **k: None)
    return dm


def test_get_message_requests_scrapes_fields():
    dm = _actions(
        usernames=['‎⁨NK19⁩', 'wifil'],
        previews=['Salut !', 'Coucou'],
        timestamps=['2 j', '5 j'],
    )
    reqs = dm.get_message_requests(max_items=30)
    assert [r['username'] for r in reqs] == ['NK19', 'wifil']  # bidi nettoyé
    assert reqs[0]['preview'] == 'Salut !'
    assert reqs[0]['timestamp'] == '2 j'


# --- traitement (DMWorkflow.process_message_requests) -----------------------

class FakeDM:
    def __init__(self, can_open=True, found=True, accept=True, decline=True, in_conv=True, sent=True):
        self._can_open = can_open
        self._found = found
        self._accept = accept
        self._decline = decline
        self._in_conv = in_conv
        self._sent = sent
        self.calls = []

    def open_message_requests_page(self):
        self.calls.append('open_page')
        return self._can_open

    def open_request(self, username):
        self.calls.append(('open', username))
        return self._found

    def accept_request(self):
        self.calls.append('accept')
        return self._accept

    def decline_request(self):
        self.calls.append('decline')
        return self._decline

    def is_in_conversation(self):
        return self._in_conv

    def send_text_message(self, msg):
        self.calls.append(('send', msg))
        return self._sent


def _workflow(fake):
    wf = DMWorkflow.__new__(DMWorkflow)
    wf.dm = fake
    wf._running = True
    wf.config = DMConfig(delay_between_conversations=0)
    wf._on_request_result_callback = None
    wf.logger = types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None, error=lambda *a, **k: None, debug=lambda *a, **k: None)
    return wf


def test_process_accept_with_reply():
    fake = FakeDM()
    wf = _workflow(fake)
    results = wf.process_message_requests([{'username': 'alice', 'action': 'accept', 'message': 'Bonjour !'}])
    assert results == [{'username': 'alice', 'action': 'accept', 'success': True, 'replied': True}]
    assert 'accept' in fake.calls and ('send', 'Bonjour !') in fake.calls


def test_process_decline():
    fake = FakeDM()
    wf = _workflow(fake)
    results = wf.process_message_requests([{'username': 'bob', 'action': 'decline'}])
    assert results[0]['success'] is True and results[0]['replied'] is False
    assert 'decline' in fake.calls and 'accept' not in fake.calls


def test_process_accept_without_message_does_not_reply():
    fake = FakeDM()
    wf = _workflow(fake)
    results = wf.process_message_requests([{'username': 'carol', 'action': 'accept'}])
    assert results[0]['success'] is True and results[0]['replied'] is False
    assert not any(isinstance(c, tuple) and c[0] == 'send' for c in fake.calls)


def test_process_request_not_found():
    fake = FakeDM(found=False)
    wf = _workflow(fake)
    results = wf.process_message_requests([{'username': 'ghost', 'action': 'accept'}])
    assert results[0]['success'] is False


def test_process_empty_is_noop():
    fake = FakeDM()
    wf = _workflow(fake)
    assert wf.process_message_requests([]) == []
    assert fake.calls == []
