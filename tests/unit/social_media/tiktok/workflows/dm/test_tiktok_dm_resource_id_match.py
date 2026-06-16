"""Tests du fix « resourceIdMatches » des actions inbox TikTok.

Bug confirmé sur device : les sélecteurs sont en forme xpath `contains(@resource-id, ":id/x")`
mais `_get_conversations`/`get_new_followers` faisaient `raw_device(resourceId=extract(...))` ;
`extract_resource_id` ne matche que la forme exacte `@resource-id="..."` → renvoyait '' →
`raw_device(resourceId='')` ne trouvait rien (0 conversation / 0 follower). Le fix passe par
`resourceIdMatches` (regex) via `_find_all_by_rid`. On exerce ici le VRAI chemin (pas de mock du
device complet) pour éviter de re-régresser.
"""

import re
import types

from taktik.core.social_media.tiktok.actions.atomic.dm_actions import DMActions
from taktik.core.social_media.tiktok.ui.selectors.surfaces.inbox import INBOX_SELECTORS


# --- helpers de faux device uiautomator2 -----------------------------------

class _FakeElem:
    def __init__(self, text):
        self._text = text

    def get_text(self):
        return self._text


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
        return _FakeElem(self._texts[i])


class _FakeXPath:
    def __init__(self, exists):
        self._exists = exists

    @property
    def exists(self):
        return self._exists


class _FakeRawDevice:
    """Reproduit l'API uiautomator2 d(resourceIdMatches=...) -> UiObject collection."""

    def __init__(self, usernames, activities):
        self._usernames = usernames
        self._activities = activities

    def __call__(self, resourceIdMatches=None, resourceId=None):
        # Le fix doit utiliser resourceIdMatches (regex), jamais resourceId exact.
        assert resourceId is None, "doit utiliser resourceIdMatches, pas resourceId exact"
        pattern = resourceIdMatches or ''
        if 'o0f' in pattern:
            return _FakeCollection(self._usernames)
        if 'nzo' in pattern:
            return _FakeCollection(self._activities)
        return _FakeCollection([])


class _FakeDevice:
    def __init__(self, usernames, activities, followable):
        self._device = _FakeRawDevice(usernames, activities)
        self._followable = set(followable)

    def xpath(self, selector):
        # selector = follow_back_for_username(name) -> on extrait le name pour décider l'existence
        m = re.search(r'\[@text="([^"]+)"\]', selector)
        name = m.group(1) if m else ''
        return _FakeXPath(name in self._followable)


def _make_actions(device):
    dm = DMActions.__new__(DMActions)
    dm.device = device
    dm.inbox_selectors = INBOX_SELECTORS
    dm.logger = types.SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        debug=lambda *a, **k: None,
    )
    return dm


# --- tests ------------------------------------------------------------------

def test_resource_id_pattern_contains_form():
    pat = DMActions._resource_id_pattern(['//*[contains(@resource-id, ":id/o0f")]'])
    # full-match regex qui matche un id complet avec package
    assert re.fullmatch(pat, 'com.zhiliaoapp.musically:id/o0f')
    assert not re.fullmatch(pat, 'com.zhiliaoapp.musically:id/zzz')


def test_resource_id_pattern_exact_form():
    pat = DMActions._resource_id_pattern(['//*[@resource-id="com.zhiliaoapp.musically:id/z05"]'])
    assert re.fullmatch(pat, 'com.zhiliaoapp.musically:id/z05')


def test_resource_id_pattern_empty_when_no_id():
    assert DMActions._resource_id_pattern(['//android.widget.Button[@text="X"]']) == ''


def test_get_new_followers_reads_via_resource_id_matches():
    device = _FakeDevice(
        usernames=['alice', 'bob', 'carol'],
        activities=['a commencé à te suivre', 'a commencé à te suivre', 'a commencé à te suivre'],
        followable=['alice', 'carol'],  # bob déjà suivi / privé
    )
    dm = _make_actions(device)

    followers = dm.get_new_followers(max_items=50)

    assert [f['username'] for f in followers] == ['alice', 'bob', 'carol']
    assert {f['username']: f['can_follow_back'] for f in followers} == {
        'alice': True,
        'bob': False,
        'carol': True,
    }
    # l'activité est appariée par index
    assert all(f['activity'] == 'a commencé à te suivre' for f in followers)


def test_get_new_followers_respects_max_items():
    device = _FakeDevice(usernames=['a', 'b', 'c', 'd'], activities=[], followable=['a', 'b', 'c', 'd'])
    dm = _make_actions(device)
    followers = dm.get_new_followers(max_items=2)
    assert [f['username'] for f in followers] == ['a', 'b']


def test_get_new_followers_empty_when_no_usernames():
    device = _FakeDevice(usernames=[], activities=[], followable=[])
    dm = _make_actions(device)
    assert dm.get_new_followers(max_items=10) == []
