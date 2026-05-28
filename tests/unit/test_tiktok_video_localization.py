from taktik.core.social_media.tiktok.actions.atomic.video_detector import VideoDetector
from taktik.core.social_media.tiktok.ui.language import filter_selectors
from taktik.core.social_media.tiktok.ui.selectors.video import VideoSelectors


class _DummyDevice:
    pass


def test_french_like_selectors_survive_language_filter():
    selectors = VideoSelectors()

    filtered = filter_selectors(selectors.like_button_unliked, "fr")

    assert filtered
    assert any("Attribuer un" in selector for selector in filtered)


def test_video_detector_parses_french_like_count(monkeypatch):
    detector = VideoDetector(_DummyDevice())

    monkeypatch.setattr(detector, "_get_element_text", lambda selectors, timeout=1: None)
    monkeypatch.setattr(
        detector,
        "_get_element_content_desc",
        lambda selectors, timeout=1: "Attribuer un « J'aime » à la vidéo. 68,5 K « J'aime »",
    )

    assert detector.get_video_like_count() == "68,5 K"


def test_video_detector_parses_french_comment_count(monkeypatch):
    detector = VideoDetector(_DummyDevice())

    monkeypatch.setattr(detector, "_get_element_text", lambda selectors, timeout=1: None)
    monkeypatch.setattr(
        detector,
        "_get_element_content_desc",
        lambda selectors, timeout=1: "Lire ou ajouter des commentaires. 368 commentaires",
    )

    assert detector.get_video_comment_count() == "368"


def test_video_detector_reads_french_profile_content_desc(monkeypatch):
    detector = VideoDetector(_DummyDevice())

    monkeypatch.setattr(detector, "_get_element_text", lambda selectors, timeout=1: None)
    monkeypatch.setattr(
        detector,
        "_get_element_content_desc",
        lambda selectors, timeout=1: "Profil Grindlabsofficial_",
    )

    assert detector.get_video_author() == "Grindlabsofficial_"
