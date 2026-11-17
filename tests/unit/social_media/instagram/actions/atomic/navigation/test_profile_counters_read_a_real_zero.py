"""A header that says 0 followers is read as 0, a measure, not as a counter that could not be read.

On Instagram 447 (French), a new account shows « 0 publications », « 0 follower » (singular) and
« 0 suivi(e)s ». The followers and following readers took the value node, parsed its « 0 » and
dropped it because they only kept a count above 0 (the number parser also answers 0 for a text
without digits); the fallbacks then looked for the plural labels, found nothing, and the readers
said « unknown ». The visit then filed 0 for an unknown counter: right by luck. A « 0 » written
on the value node is now the measure.

The screen is the real dump of that profile, anonymised (Pixel 6a, Instagram 447.0.0.55.81,
French), replayed by the phone of `test_profile_grid_shown_before_read.py`, which also answers
uiautomator2's selector lookup by resource-id (`d(resourceId=...)`), the readers' first way.
"""

import re

from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.instagram.services.profile.extraction import ProfileExtraction

from test_profile_grid_shown_before_read import _Phone, _capture, _clock, _facade  # noqa: F401 (fixture)

NEW_ACCOUNT_447_FR = _capture("ig447_fr_direct_profile_after_absent_handle.xml")


class _Node:
    """What `d(resourceId=...)` gives back: whether the node is on screen, and its text."""

    def __init__(self, node):
        self._node = node
        self.exists = node is not None

    def get_text(self):
        return self._node.get("text") if self._node is not None else None


class _PhoneWithSelectors(_Phone):
    """The clone-aware proxy turns an exact `resourceId` into the regex `resourceIdMatches`."""

    def __call__(self, resourceIdMatches=None, **_selector):
        tree = parse_ui_dump(self.screen.encode("utf-8"))
        nodes = [
            node for node in tree.iter()
            if re.fullmatch(resourceIdMatches, node.get("resource-id") or "")
        ]
        return _Node(nodes[0] if nodes else None)


def _reader(screen):
    return ProfileExtraction(_facade(_PhoneWithSelectors({"profile": screen}, "profile")))


def test_zero_followers_in_the_singular_is_read_as_zero():
    reader = _reader(NEW_ACCOUNT_447_FR)

    assert reader._get_followers_count_robust() == 0


def test_zero_following_is_read_as_zero():
    reader = _reader(NEW_ACCOUNT_447_FR)

    assert reader._get_following_count_robust() == 0


def test_zero_posts_is_read_as_zero():
    reader = _reader(NEW_ACCOUNT_447_FR)

    assert reader._get_posts_count_robust() == 0
