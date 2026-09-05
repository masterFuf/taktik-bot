from taktik.core.social_media.tiktok.actions.atomic.detection.video_detector import VideoDetector
from tests.unit.social_media.tiktok.ui.test_tiktok_video_snapshot import (
    CREATOR_PROFILE_43_XML,
    VIDEO_43_XML,
)


class _SnapshotOnlyDevice:
    info = {"displayWidth": 720, "displayHeight": 1560}

    def __init__(self):
        self.dumps = 0

    def dump_hierarchy(self, compressed=False):
        self.dumps += 1
        return VIDEO_43_XML

    def xpath(self, _selector):
        raise AssertionError("a complete snapshot must not fall back to serial XPath polling")


def test_get_video_info_uses_one_dump_for_reliable_metadata_without_xpath_waits():
    raw = _SnapshotOnlyDevice()

    info = VideoDetector(raw).get_video_info()

    assert raw.dumps == 1
    assert info["author"] == "Nympha Ophis"
    assert info["like_count"] == "63.9K"
    assert info["signature"]


def test_parsed_creator_profile_does_not_enter_slow_video_selector_fallback():
    raw = _SnapshotOnlyDevice()
    raw.dump_hierarchy = lambda compressed=False: CREATOR_PROFILE_43_XML

    info = VideoDetector(raw).get_video_info()

    assert info["video_visible"] is False
    assert info["author"] is None
    assert info["like_count"] is None
