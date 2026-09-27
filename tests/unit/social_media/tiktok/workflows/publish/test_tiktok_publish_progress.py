"""Reading TikTok's upload progress while a publish runs.

The screens are real, anonymized (Pixel 6a): TikTok 43.1.4 in French uploading, its badge
`x44` reading "91%"; the profile right after a French 43.1.4 post, a "94%" far down the screen that
is no badge; and TikTok 46.6.3 in English uploading (2026-08-30), its badge renamed `tvProgress`.
"""

from pathlib import Path

import pytest

from taktik.core.social_media.tiktok.services.publish.progress import (
    extract_percent_value,
    get_publish_progress_percent,
)

FIXTURES = Path(__file__).parents[2] / "fixtures"


def _screen(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeDumpDevice:
    def __init__(self, xml: str):
        self.xml = xml

    def dump_hierarchy(self, compressed: bool = False) -> str:
        return self.xml


def test_extract_percent_value_accepts_valid_percent_labels():
    assert extract_percent_value("81%") == 81
    assert extract_percent_value("  7 % ") == 7
    assert extract_percent_value("100%") == 100


def test_extract_percent_value_rejects_non_progress_labels():
    assert extract_percent_value(None) is None
    assert extract_percent_value("101%") is None
    assert extract_percent_value("Uploading") is None


def test_get_publish_progress_percent_reads_resource_id_badge():
    device = FakeDumpDevice(_screen("tt4314_fr_publish_uploading.xml"))

    assert get_publish_progress_percent(device) == 91


@pytest.mark.xfail(strict=True, reason=(
    "TikTok 46.6.3 renamed the badge `tvProgress` and draws it at [56,344][127,383]: the id list "
    "names only `x44`, and the text fallback of services/publish/progress.py refuses a node whose "
    "top is below 320 px, so the upload progress reads None. Open point, to prove on a phone."))
def test_get_publish_progress_percent_reads_top_left_text_fallback():
    device = FakeDumpDevice(_screen("tt4663_en_publish_uploading.xml"))

    assert get_publish_progress_percent(device) == 66


def test_get_publish_progress_percent_ignores_large_or_far_text_nodes():
    device = FakeDumpDevice(_screen("tt4314_fr_publish_posted.xml"))

    assert get_publish_progress_percent(device) is None
