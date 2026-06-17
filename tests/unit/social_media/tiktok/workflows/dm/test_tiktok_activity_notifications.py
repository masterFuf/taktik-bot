"""Tests de la lecture activité / notifications système (inbox v2 phase 4, lecture seule).

Données calquées sur un dump device réel (inbox 2026-06-16) : 3 sections s28 avec titre b8h
+ aperçu ln_ — Nouveaux followers / Activité / Notifications système.
"""

import types

from taktik.core.social_media.tiktok.actions.atomic.dm_actions import DMActions
from taktik.core.social_media.tiktok.ui.selectors.surfaces.inbox import INBOX_SELECTORS


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
    def __init__(self, titles, previews):
        self.titles, self.previews = titles, previews

    def __call__(self, resourceIdMatches=None, resourceId=None):
        assert resourceId is None
        pat = resourceIdMatches or ''
        if 'b8h' in pat:
            return _Coll(self.titles)
        if 'ln_' in pat:
            return _Coll(self.previews)
        return _Coll([])


def _actions(titles, previews):
    dm = DMActions.__new__(DMActions)
    dm.device = types.SimpleNamespace(_device=_Raw(titles, previews))
    dm.inbox_selectors = INBOX_SELECTORS
    dm.logger = types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None, debug=lambda *a, **k: None)
    return dm


def test_get_notifications_classifies_and_excludes_new_followers():
    dm = _actions(
        titles=['Nouveaux followers', 'Activité', 'Notifications système'],
        previews=[
            'NK19 a commencé à te suivre.',
            'Nico Lito, AvaBack Fa et 10 autres ont vu ton profil',
            'LIVE: Tes spectateur(trice)s veulent en voir plus',
        ],
    )
    notifs = dm.get_inbox_notifications(max_items=20)

    # Nouveaux followers exclu (phase 1) ; activité + système classés
    cats = {n['category']: n for n in notifs}
    assert set(cats) == {'activity', 'system'}
    assert cats['activity']['title'] == 'Activité'
    assert 'ont vu ton profil' in cats['activity']['preview']
    assert cats['system']['title'] == 'Notifications système'


def test_get_notifications_english():
    dm = _actions(
        titles=['Activity', 'System notifications'],
        previews=['Someone liked your video', 'LIVE reminder'],
    )
    notifs = dm.get_inbox_notifications()
    assert {n['category'] for n in notifs} == {'activity', 'system'}


def test_get_notifications_empty():
    dm = _actions(titles=[], previews=[])
    assert dm.get_inbox_notifications() == []
