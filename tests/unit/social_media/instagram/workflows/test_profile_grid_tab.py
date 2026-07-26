"""The profile's POSTS grid must be the active sub-tab before anyone looks for thumbnails.

Instagram remembers the last sub-tab a profile was left on. A device run landed on "Reposted": no
thumbnail selector could match, the flow reported "no posts in grid" on a profile that has posts,
then scrolled twice hunting for a grid that was not on the page at all.

The attribute values below are taken verbatim from the two real dumps — the run that failed with
"Reposted" active, and the run that succeeded with the grid active — so the fix is pinned against
both the defect and the case that already worked.
"""

import pytest

from taktik.core.social_media.instagram.ui.selectors.surfaces.profile import PROFILE_SELECTORS
from taktik.core.social_media.instagram.workflows.common.post_navigation import (
    ensure_profile_grid_tab,
)


class _Node:
    def __init__(self, selected):
        self.attrib = {"content-desc": "Grid view", "selected": selected}
        self.bounds = (0, 1567, 270, 1699)
        self.clicked = False

    def click(self):
        self.clicked = True


class _Element:
    def __init__(self, node):
        self._node = node
        self.exists = node is not None

    def get(self):
        return self._node


class _Device:
    """Answers the grid-tab selector and nothing else, like a screen showing only that row."""

    def __init__(self, selected, *, with_human_tap=False):
        self.node = _Node(selected)
        self.taps = []
        if with_human_tap:
            self.human_tap = self._human_tap

    def _human_tap(self, bounds):
        self.taps.append(bounds)
        return (1, 2)

    def xpath(self, selector):
        known = selector in PROFILE_SELECTORS.profile_grid_tab_selectors
        return _Element(self.node if known else None)


@pytest.fixture(autouse=True)
def _no_settle(monkeypatch):
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.workflows.common.post_navigation.time.sleep",
        lambda _s: None,
    )


def test_already_on_the_grid_taps_nothing():
    """The run that worked must keep working: selected=true is a no-op, not a redundant tap."""
    device = _Device("true", with_human_tap=True)

    assert ensure_profile_grid_tab(device) is True
    assert device.taps == []
    assert device.node.clicked is False


def test_another_sub_tab_selects_the_grid():
    device = _Device("false", with_human_tap=True)

    assert ensure_profile_grid_tab(device) is True
    assert device.taps == [(0, 1567, 270, 1699)]      # humanised point inside the tab, not a centre
    assert device.node.clicked is False


def test_falls_back_to_a_plain_click_without_a_humanised_tap():
    """Standalone flows hold a bare device; the tab must still be reachable there."""
    device = _Device("false")

    assert ensure_profile_grid_tab(device) is True
    assert device.node.clicked is True


def test_absent_tab_row_is_reported_rather_than_assumed():
    class _Blind:
        def xpath(self, _selector):
            return _Element(None)

    assert ensure_profile_grid_tab(_Blind()) is False


def test_business_flow_can_import_the_shared_helper():
    """Guards the import that an import-time check cannot see, because it sits in a function body.

    The first attempt used a relative form four levels up, which resolves to
    `instagram.actions.workflows` -- a package that does not exist. Nothing caught it: the audits
    pass, the module imports fine, and the statement only runs when a profile has no visible posts.
    """
    from taktik.core.social_media.instagram.actions.business.actions.like import post_navigation

    source = post_navigation.__loader__.get_source(post_navigation.__name__)
    assert "from taktik.core.social_media.instagram.workflows.common.post_navigation import" in source
