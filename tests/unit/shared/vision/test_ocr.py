"""Unit tests for the shared OCR locate service (tesseract mocked — no binary needed)."""

from PIL import Image

from taktik.core.shared.vision.ocr import OcrService


class _FakePytesseract:
    class Output:
        DICT = "dict"

    def __init__(self, data):
        self._data = data

    def image_to_data(self, img, output_type=None, config=None, **kwargs):
        return self._data


def _patch(monkeypatch, data):
    fake = _FakePytesseract(data)
    monkeypatch.setattr(OcrService, "_pytesseract", classmethod(lambda cls: fake))


def test_locate_finds_word_and_returns_center(monkeypatch):
    _patch(monkeypatch, {
        "text": ["Chez", "cert", "more", "1w"],
        "conf": ["90", "88", "95", "80"],
        "left": [10, 120, 300, 420], "top": [50, 50, 50, 50],
        "width": [80, 90, 70, 40], "height": [30, 30, 30, 30],
    })
    matches = OcrService.locate(Image.new("RGB", (640, 200)), ["more", "suite", "plus"])
    assert [m.text for m in matches] == ["more"]
    assert matches[0].center == (300 + 35, 50 + 15)


def test_region_offsets_coords_back_to_full_image(monkeypatch):
    _patch(monkeypatch, {
        "text": ["more"], "conf": ["95"],
        "left": [20], "top": [10], "width": [60], "height": [28],
    })
    matches = OcrService.locate(Image.new("RGB", (1080, 600)), "more", region=(253, 300, 893, 500))
    assert (matches[0].left, matches[0].top) == (20 + 253, 10 + 300)


def test_low_confidence_is_filtered(monkeypatch):
    _patch(monkeypatch, {"text": ["more"], "conf": ["20"], "left": [0], "top": [0], "width": [9], "height": [9]})
    assert OcrService.locate(Image.new("RGB", (50, 50)), "more", min_confidence=40) == []


def test_surrounding_punctuation_still_matches(monkeypatch):
    _patch(monkeypatch, {"text": ["«more»"], "conf": ["90"], "left": [0], "top": [0], "width": [9], "height": [9]})
    assert len(OcrService.locate(Image.new("RGB", (50, 50)), "more")) == 1


def test_unavailable_returns_empty(monkeypatch):
    monkeypatch.setattr(OcrService, "_pytesseract", classmethod(lambda cls: None))
    assert OcrService.locate(Image.new("RGB", (50, 50)), "more") == []
