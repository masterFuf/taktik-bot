"""Instagram supplies live post-action bounds to the shared gesture start guard.

The screens are real dumps of Instagram 410.0.0.53.71 in English, anonymized: a home feed post
with its action row (like, its count button, comment, share, save), and the connected account's
profile, which shows no post.
"""

from pathlib import Path

from taktik.core.shared.device.facade import BaseDeviceFacade
from taktik.core.shared.device.ui_dump import parse_ui_dump

from taktik.core.social_media.instagram.actions.atomic.scroll.base_scroll import BaseScrollMixin


FIXTURES = Path(__file__).parent / "fixtures"
FEED = (FIXTURES / "ig410_en_feed_carousel_framed.xml").read_text(encoding="utf-8")
PROFILE = (FIXTURES / "ig410_en_own_profile.xml").read_text(encoding="utf-8")


class _Log:
    def debug(self, *_args, **_kwargs):
        pass


class _Raw:
    def __init__(self, xml):
        self.xml = xml
        self.dumps = 0

    def dump_hierarchy(self):
        self.dumps += 1
        return self.xml


def _host(xml):
    host = object.__new__(BaseScrollMixin)
    host.device = BaseDeviceFacade(_Raw(xml))
    host.logger = _Log()
    return host


def test_reads_named_and_anonymous_action_row_bounds():
    host = _host(FEED)

    geometry = host._read_post_action_geometry()

    assert geometry["available"] is True
    assert geometry["post_visible"] is True
    # The share icon, and the clickable group around it that owns the touch target.
    assert geometry["roles"]["share"] == [(391, 500, 457, 627), (374, 500, 468, 627)]
    # The like count: a clickable button with no id, between like and comment.
    assert (110, 500, 126, 627) in geometry["roles"]["button"]
    assert host._gesture_start_exclusion_bounds() == geometry["bounds"]


def test_non_post_screen_has_no_exclusions():
    host = _host(PROFILE)

    assert host._gesture_start_exclusion_bounds() == []


def test_dump_failure_requests_ratio_fallback():
    host = _host("not xml")

    assert host._gesture_start_exclusion_bounds() is None
    assert host._gesture_fallback_safe_x_band() == (0.46, 0.70)


def test_existing_hierarchy_root_is_reused_then_invalidated():
    host = _host(FEED)
    root = parse_ui_dump(FEED)

    host._remember_post_action_geometry(root)
    bounds = host._gesture_start_exclusion_bounds()

    assert (391, 500, 457, 627) in bounds
    assert host.device._device.dumps == 0
    assert host._post_action_geometry_cache is None
