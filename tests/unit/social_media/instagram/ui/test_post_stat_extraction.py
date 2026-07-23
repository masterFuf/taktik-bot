from types import SimpleNamespace

from taktik.core.social_media.instagram.ui.extractors import InstagramUIExtractors


class _Element:
    def __init__(self, text):
        self.info = {"text": text, "contentDescription": ""}


class _XPath:
    def __init__(self, elements):
        self._elements = elements
        self.exists = bool(elements)
        self.info = elements[0].info if elements else {}

    def all(self):
        return self._elements


class _Device:
    def __init__(self, buttons):
        self._buttons = buttons

    def xpath(self, selector):
        if selector == "buttons":
            return _XPath([_Element(text) for text in self._buttons])
        return _XPath([])


def _extractor(buttons):
    extractor = object.__new__(InstagramUIExtractors)
    extractor.device = _Device(buttons)
    extractor.post_selectors = SimpleNamespace(
        photo_imageview_selector="photos",
        button_like_selectors=("buttons",),
    )
    extractor.detection_selectors = SimpleNamespace(
        reel_like_count_selector="reel_likes",
        reel_comment_count_selector="reel_comments",
    )
    return extractor


def test_username_digits_are_not_parsed_as_like_count():
    assert _extractor(["titistar_2", "125"]).extract_likes_count_from_ui(
        is_reel=False
    ) == 125


def test_username_digits_are_not_parsed_as_comment_count():
    assert _extractor(["titistar_2", "125", "4"]).extract_comments_count_from_ui(
        is_reel=False
    ) == 4
