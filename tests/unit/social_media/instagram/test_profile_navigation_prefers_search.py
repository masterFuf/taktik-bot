"""Opening a profile goes through the SEARCH BAR, not through an ADB intent.

A deep link is not an app gesture: `am start -a android.intent.action.VIEW -d
"https://www.instagram.com/<user>/"` is an external intent, visible as such to the system
and to the app. No human opens a profile that way, and it was the default NINE times out of
ten on every profile entry of every workflow — `deep_link_usage_percentage: int = 90`.

The knob existed to change that (`config.get('deep_link_percentage', 90)`), but no config,
no config builder and no page ever set the key, so 90 is what every run actually used.

Search is now tried first; the deep link remains the FALLBACK, so this inverts a preference
without removing a capability. These tests pin both halves — the second one is what keeps
"more discreet" from turning into "cannot reach the profile any more".
"""

import pytest

from taktik.core.social_media.instagram.actions.atomic.navigation.search_navigation import (
    SearchNavigationMixin,
)


class _Nav(SearchNavigationMixin):
    """Navigation with both routes stubbed, recording which one ran."""

    def __init__(self, search_ok=True, deeplink_ok=True):
        self.calls = []
        self._search_ok = search_ok
        self._deeplink_ok = deeplink_ok

        class _Log:
            def debug(self, *a, **k): pass
            def info(self, *a, **k): pass
            def warning(self, *a, **k): pass
            def error(self, *a, **k): pass

        self.logger = _Log()

    def _navigate_via_search(self, username):
        self.calls.append('search')
        return self._search_ok

    def _navigate_via_deep_link(self, username):
        self.calls.append('deeplink')
        return self._deeplink_ok

    def _check_and_close_problematic_pages(self):
        return None


@pytest.fixture(autouse=True)
def _stock_package(monkeypatch):
    """A CLONE package forces search on its own; pin the stock one so the tests measure the
    DEFAULT, not the clone rule."""
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.actions.atomic.navigation.search_navigation.get_active_package",
        lambda: "com.instagram.android",
    )


def test_search_is_the_route_taken_by_default():
    nav = _Nav()
    assert nav.navigate_to_profile("alice") is True
    assert nav.calls == ['search']


def test_the_deep_link_still_rescues_a_failed_search():
    """Discretion must not cost reachability: this is the whole reason the default could
    move at all."""
    nav = _Nav(search_ok=False, deeplink_ok=True)
    assert nav.navigate_to_profile("alice") is True
    assert nav.calls == ['search', 'deeplink']


def test_both_routes_failing_reports_failure():
    nav = _Nav(search_ok=False, deeplink_ok=False)
    assert nav.navigate_to_profile("alice") is False
    assert nav.calls == ['search', 'deeplink']


def test_an_explicit_percentage_can_still_ask_for_the_deep_link_first():
    """The parameter keeps its meaning — only its default changed."""
    nav = _Nav()
    assert nav.navigate_to_profile("alice", deep_link_usage_percentage=100) is True
    assert nav.calls == ['deeplink']


def test_force_search_never_touches_the_deep_link_even_as_a_fallback():
    nav = _Nav(search_ok=False, deeplink_ok=True)
    assert nav.navigate_to_profile("alice", force_search=True) is False
    assert nav.calls == ['search']


def test_a_clone_package_still_forces_search(monkeypatch):
    """Deep links are unsupported on cloned packages — that rule predates this change and
    must survive it."""
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.actions.atomic.navigation.search_navigation.get_active_package",
        lambda: "com.instagram.clone1",
    )
    nav = _Nav(search_ok=False, deeplink_ok=True)
    assert nav.navigate_to_profile("alice", deep_link_usage_percentage=100) is False
    assert nav.calls == ['search']


def test_the_target_workflow_no_longer_asks_for_the_deep_link():
    """The atomic's default is not enough: the target workflow passes the value EXPLICITLY,
    so a stale 90 there would have kept the old behaviour whatever the atomic said."""
    import inspect
    from taktik.core.social_media.instagram.actions.business.workflows.followers.workflows.direct import (
        main_loop,
    )
    source = inspect.getsource(main_loop)
    assert "config.get('deep_link_percentage', 0)" in source
