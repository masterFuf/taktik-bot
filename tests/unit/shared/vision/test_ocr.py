"""Unit tests for the shared OCR locate service (tesseract mocked — no binary needed)."""

import subprocess

from PIL import Image

from taktik.core.shared.vision.ocr import OcrService


_TSV_HEADER = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"


def _tsv(rows):
    lines = [_TSV_HEADER]
    for index, row in enumerate(rows, start=1):
        lines.append(
            "\t".join(
                str(value)
                for value in (
                    5, 1, 1, 1, 1, index,
                    row["left"], row["top"], row["width"], row["height"],
                    row["conf"], row["text"],
                )
            )
        )
    return "\n".join(lines)


def _patch(monkeypatch, rows):
    calls = []
    monkeypatch.setattr(
        OcrService,
        "_resolve_tesseract_cmd",
        classmethod(lambda cls: "tesseract"),
    )

    def fake_image_to_tsv(cls, command, image, *, lang, timeout_seconds):
        calls.append(
            {
                "command": command,
                "size": image.size,
                "lang": lang,
                "timeout_seconds": timeout_seconds,
            }
        )
        return _tsv(rows)

    monkeypatch.setattr(OcrService, "_image_to_tsv", classmethod(fake_image_to_tsv))
    return calls


def test_locate_finds_word_and_returns_center(monkeypatch):
    _patch(monkeypatch, [
        {"text": "Chez", "conf": "90", "left": 10, "top": 50, "width": 80, "height": 30},
        {"text": "cert", "conf": "88", "left": 120, "top": 50, "width": 90, "height": 30},
        {"text": "more", "conf": "95", "left": 300, "top": 50, "width": 70, "height": 30},
        {"text": "1w", "conf": "80", "left": 420, "top": 50, "width": 40, "height": 30},
    ])

    matches = OcrService.locate(Image.new("RGB", (640, 200)), ["more", "suite", "plus"])

    assert [match.text for match in matches] == ["more"]
    assert matches[0].center == (300 + 35, 50 + 15)


def test_region_offsets_coords_back_to_full_image(monkeypatch):
    calls = _patch(monkeypatch, [
        {"text": "more", "conf": "95", "left": 20, "top": 10, "width": 60, "height": 28},
    ])

    matches = OcrService.locate(
        Image.new("RGB", (1080, 600)),
        "more",
        region=(253, 300, 893, 500),
    )

    assert calls[0]["size"] == (640, 200)
    assert (matches[0].left, matches[0].top) == (20 + 253, 10 + 300)


def test_low_confidence_is_filtered(monkeypatch):
    _patch(monkeypatch, [
        {"text": "more", "conf": "20", "left": 0, "top": 0, "width": 9, "height": 9},
    ])

    assert OcrService.locate(
        Image.new("RGB", (50, 50)),
        "more",
        min_confidence=40,
    ) == []


def test_surrounding_punctuation_still_matches(monkeypatch):
    _patch(monkeypatch, [
        {"text": "«more»", "conf": "90", "left": 0, "top": 0, "width": 9, "height": 9},
    ])

    assert len(OcrService.locate(Image.new("RGB", (50, 50)), "more")) == 1


def test_unavailable_returns_empty(monkeypatch):
    monkeypatch.setattr(
        OcrService,
        "_resolve_tesseract_cmd",
        classmethod(lambda cls: None),
    )

    assert OcrService.locate(Image.new("RGB", (50, 50)), "more") == []


def test_tesseract_call_has_a_hard_timeout(monkeypatch):
    calls = _patch(monkeypatch, [])

    OcrService.locate(Image.new("RGB", (50, 50)), "more")

    assert calls[0]["timeout_seconds"] == 5.0


def test_tesseract_cli_receives_png_and_tsv_arguments(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, stdout=b"tsv", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = OcrService._image_to_tsv(
        "tesseract",
        Image.new("RGB", (20, 10), "black"),
        lang="eng",
        timeout_seconds=2.5,
    )

    args, kwargs = calls[0]
    assert args == ["tesseract", "stdin", "stdout", "-l", "eng", "--psm", "11", "tsv"]
    assert kwargs["input"].startswith(b"\x89PNG")
    assert kwargs["timeout"] == 2.5
    assert result == "tsv"
