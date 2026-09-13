import pytest

from taktik.core.social_media.tiktok.actions.core.device_facade import DeviceFacade
from tests.unit.social_media.tiktok.ui.test_tiktok_video_snapshot import VIDEO_43_XML


class _RawDevice:
    info = {"displayWidth": 720, "displayHeight": 1560}

    def dump_hierarchy(self, compressed=False):
        return VIDEO_43_XML


def test_tiktok_gesture_host_forwards_live_interactive_bounds():
    host = DeviceFacade(_RawDevice())._gesture_host()

    bounds = host._gesture_start_exclusion_bounds()

    assert (21, 1267, 580, 1333) in bounds
    assert (608, 861, 720, 966) in bounds


def test_tiktok_gesture_guard_has_a_central_fallback_band_when_dump_fails():
    class _Broken(_RawDevice):
        def dump_hierarchy(self, compressed=False):
            raise RuntimeError("adb unavailable")

    host = DeviceFacade(_Broken())._gesture_host()

    assert host._gesture_start_exclusion_bounds() is None
    assert host._gesture_fallback_safe_x_band() == (0.38, 0.62)


def test_feed_advance_requests_a_caption_free_vertical_start_band():
    class _Host:
        screen_height = 1560

        def __init__(self):
            self.kwargs = None

        def _strong_flick(self, **kwargs):
            self.kwargs = kwargs
            return True

    facade = DeviceFacade(_RawDevice())
    host = _Host()
    facade._gesture_host = lambda: host

    facade.swipe_up(coast=True, feed=True)

    assert host.kwargs["guard_start"] is True
    assert host.kwargs["start_band"] == pytest.approx((530.4, 967.2))
