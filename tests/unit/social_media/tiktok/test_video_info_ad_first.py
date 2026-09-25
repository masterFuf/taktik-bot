"""The ad check runs first in `get_video_info`, and an ad's caption is never tapped open."""

from taktik.core.social_media.tiktok.actions.atomic.detection.video_detector import VideoDetector


def _detector(is_ad, calls):
    detector = object.__new__(VideoDetector)

    def record(name, value):
        def reader(*_a, **_k):
            calls.append(name)
            return value
        return reader

    detector.is_ad_video = record("is_ad", is_ad)
    detector.is_live_preview = record("is_live", False)
    detector.get_video_description_parsed = record(
        "expand", {"description_text": "full caption", "hashtags": []})
    detector.get_video_description = record("raw", "Démarrez gratuitement")
    for name in ("get_video_author", "get_video_sound", "get_video_like_count",
                 "is_video_liked", "is_video_favorited"):
        setattr(detector, name, record(name, None))
    return detector


def test_the_ad_check_comes_before_every_other_read():
    calls = []
    _detector(False, calls).get_video_info()
    assert calls[0] == "is_ad"
    assert "expand" in calls


def test_an_ad_caption_is_read_without_expanding_it():
    calls = []
    info = _detector(True, calls).get_video_info()
    assert info["is_ad"] is True
    assert "expand" not in calls
    assert info["description"] == "Démarrez gratuitement"


def test_an_ad_about_to_be_skipped_is_read_no_further_than_its_author():
    calls = []
    info = _detector(True, calls).get_video_info(light_if_ad=True)
    assert info["is_ad"] is True
    assert calls == ["is_ad", "get_video_author"]


def test_an_ad_the_run_keeps_is_read_in_full():
    calls = []
    _detector(True, calls).get_video_info(light_if_ad=False)
    assert "get_video_sound" in calls
