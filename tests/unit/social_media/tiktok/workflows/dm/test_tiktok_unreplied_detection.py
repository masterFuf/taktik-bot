"""Tests de la détection « non-répondu » (inbox v2 phase 2).

Données calquées sur un dump device réel (inbox 2026-06-16) :
- ligne « Demandes de messages » (l35 « Tu as reçu 3 demandes ») -> exclue
- Matthiasbrtl_ : aperçu = leur message -> non-répondu
- wifil : aperçu = « Envoyé il y a 5 j » -> on a parlé en dernier -> répondu
"""

import types

from taktik.core.social_media.tiktok.actions.atomic.dm_actions import DMActions
from taktik.core.social_media.tiktok.ui.selectors.surfaces.inbox import INBOX_SELECTORS


class _FakeCollection:
    def __init__(self, texts):
        self._texts = texts

    @property
    def exists(self):
        return len(self._texts) > 0

    @property
    def count(self):
        return len(self._texts)

    def __getitem__(self, i):
        return types.SimpleNamespace(get_text=lambda t=self._texts[i]: t)


class _FakeRawDevice:
    def __init__(self, usernames, previews):
        self._usernames = usernames
        self._previews = previews

    def __call__(self, resourceIdMatches=None, resourceId=None):
        assert resourceId is None, "doit utiliser resourceIdMatches"
        pat = resourceIdMatches or ''
        if 'z05' in pat:
            return _FakeCollection(self._usernames)
        if 'l35' in pat:
            return _FakeCollection(self._previews)
        return _FakeCollection([])


class _FakeDevice:
    def __init__(self, usernames, previews):
        self._device = _FakeRawDevice(usernames, previews)


def _make_actions(usernames, previews):
    dm = DMActions.__new__(DMActions)
    dm.device = _FakeDevice(usernames, previews)
    dm.inbox_selectors = INBOX_SELECTORS
    dm.logger = types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None, debug=lambda *a, **k: None)
    return dm


def test_unreplied_detection_from_real_inbox():
    dm = _make_actions(
        usernames=['Demandes de messages', 'Matthiasbrtl_', 'wifil'],
        previews=['Tu as reçu 3 demandes', '.. Salut, je suis intéressé', 'Envoyé il y a 5\xa0j'],
    )
    convos = dm.get_inbox_conversations(max_items=30)

    # La ligne "Demandes de messages" est exclue (phase 3)
    names = [c['username'] for c in convos]
    assert names == ['Matthiasbrtl_', 'wifil']

    by_name = {c['username']: c['unreplied'] for c in convos}
    assert by_name['Matthiasbrtl_'] is True   # leur message en dernier
    assert by_name['wifil'] is False          # "Envoyé ..." -> on a parlé en dernier


def test_unreplied_detection_seen_marker_is_replied():
    dm = _make_actions(usernames=['alice', 'bob'], previews=['Vu', 'coucou ça va ?'])
    convos = dm.get_inbox_conversations()
    by_name = {c['username']: c['unreplied'] for c in convos}
    assert by_name['alice'] is False  # "Vu" -> on a parlé en dernier
    assert by_name['bob'] is True     # leur message


def test_unreplied_detection_english_sent_marker():
    dm = _make_actions(usernames=['carol'], previews=['Sent 2d ago'])
    convos = dm.get_inbox_conversations()
    assert convos[0]['unreplied'] is False  # "Sent ..." (EN)


def test_unreplied_detection_empty():
    dm = _make_actions(usernames=[], previews=[])
    assert dm.get_inbox_conversations() == []
