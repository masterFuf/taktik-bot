"""Reading TikTok's upload progress while a publish runs.

The screens are real, anonymized (Pixel 6a, 1080x2400): TikTok 43.1.4 in French uploading, its
badge `x44` reading "91%"; the profile right after a French 43.1.4 post, a "94%" far down the
screen that is no badge; TikTok 46.6.3 in English uploading (2026-08-30), its badge renamed
`tvProgress` and drawn higher on the screen; and TikTok 47.0.3 in French uploading (2026-09-27),
the same `tvProgress` badge reading "99%".
"""

from pathlib import Path

import pytest

from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.shared.device.ui_dump import dump_screen_size, parse_ui_dump
from taktik.core.social_media.tiktok.services.publish.progress import (
    extract_percent_value,
    get_publish_progress_percent,
)
from taktik.core.social_media.tiktok.ui.selectors.flows.publish import (
    PUBLISH_PROGRESS_SELECTORS,
    PublishProgressSelectors,
)

FIXTURES = Path(__file__).parents[2] / "fixtures"

UPLOADING_43_1_4 = "tt4314_fr_publish_uploading.xml"
POSTED_43_1_4 = "tt4314_fr_publish_posted.xml"
UPLOADING_46_6_3 = "tt4663_en_publish_uploading.xml"
UPLOADING_47_0_3 = "tt4703_fr_publish_uploading.xml"


def _screen(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeDumpDevice:
    def __init__(self, xml: str):
        self.xml = xml

    def dump_hierarchy(self, compressed: bool = False) -> str:
        return self.xml


class UnreadableDevice:
    def dump_hierarchy(self, compressed: bool = False) -> str:
        raise ConnectionError("uiautomator server gone")


class CollectedLog:
    def __init__(self):
        self.lines = []

    def __call__(self, level: str, message: str) -> None:
        self.lines.append((level, message))


def _badge_texts_by_id(xml: str) -> list:
    """What the badge ids of the catalogue, as currently patched, find on a screen."""
    tree = parse_ui_dump(xml)
    return [
        node.get("text")
        for xpath in PUBLISH_PROGRESS_SELECTORS.publish_progress_indicator
        for node in tree.xpath(xpath)
    ]


@pytest.fixture
def on_46_6_3():
    apply_version_overrides("tiktok", "46.6.3")
    yield
    apply_version_overrides("tiktok", "43.1.4")


@pytest.fixture
def on_47_0_3():
    apply_version_overrides("tiktok", "47.0.3")
    yield
    apply_version_overrides("tiktok", "43.1.4")


def test_extract_percent_value_accepts_valid_percent_labels():
    assert extract_percent_value("81%") == 81
    assert extract_percent_value("  7 % ") == 7
    assert extract_percent_value("100%") == 100


def test_extract_percent_value_rejects_non_progress_labels():
    assert extract_percent_value(None) is None
    assert extract_percent_value("101%") is None
    assert extract_percent_value("Uploading") is None


def test_get_publish_progress_percent_reads_resource_id_badge():
    device = FakeDumpDevice(_screen(UPLOADING_43_1_4))

    assert get_publish_progress_percent(device) == 91


def test_get_publish_progress_percent_reads_top_left_text_fallback():
    """46.6.3 without its override: only the position of the label can find the badge."""
    device = FakeDumpDevice(_screen(UPLOADING_46_6_3))

    assert get_publish_progress_percent(device) == 66


def test_the_47_0_3_badge_is_found_by_its_position_too():
    device = FakeDumpDevice(_screen(UPLOADING_47_0_3))

    assert get_publish_progress_percent(device) == 99


def test_get_publish_progress_percent_ignores_large_or_far_text_nodes():
    device = FakeDumpDevice(_screen(POSTED_43_1_4))

    assert get_publish_progress_percent(device) is None


def test_the_screen_size_is_read_from_the_dump():
    for name in (UPLOADING_43_1_4, POSTED_43_1_4, UPLOADING_46_6_3, UPLOADING_47_0_3):
        assert dump_screen_size(parse_ui_dump(_screen(name))) == (1080, 2400)


# --- the version override: the 46.6.3 badge by its id ---------------------------------------


def test_the_baseline_ids_do_not_name_the_46_6_3_badge():
    assert _badge_texts_by_id(_screen(UPLOADING_46_6_3)) == []


def test_on_46_6_3_the_badge_is_read_by_its_id(on_46_6_3):
    assert _badge_texts_by_id(_screen(UPLOADING_46_6_3)) == ["66%"]


def test_on_47_0_3_the_46_6_3_entry_reads_the_badge_by_its_id(on_47_0_3):
    """An override key applies to its version and every later one."""
    assert _badge_texts_by_id(_screen(UPLOADING_47_0_3)) == ["99%"]


def test_on_46_6_3_the_43_1_4_badge_is_still_read_by_its_id(on_46_6_3):
    """The override carries the baseline entry along: it replaces the list."""
    assert _badge_texts_by_id(_screen(UPLOADING_43_1_4)) == ["91%"]


# --- nothing unread passes silently ---------------------------------------------------------


def test_an_unreadable_screen_is_logged_not_taken_for_a_finished_upload():
    log = CollectedLog()

    assert get_publish_progress_percent(UnreadableDevice(), log=log) is None
    assert [level for level, _ in log.lines] == ["warning"]
    assert "could not be dumped" in log.lines[0][1]


def test_a_dump_that_does_not_parse_is_logged():
    log = CollectedLog()

    assert get_publish_progress_percent(FakeDumpDevice("<not xml"), log=log) is None
    assert [level for level, _ in log.lines] == ["warning"]


def test_a_broken_selector_is_logged_and_the_next_one_still_reads():
    log = CollectedLog()
    selectors = PublishProgressSelectors(_publish_progress_rids=["//*[", *PUBLISH_PROGRESS_SELECTORS.publish_progress_indicator])

    assert get_publish_progress_percent(FakeDumpDevice(_screen(UPLOADING_43_1_4)), selectors, log=log) == 91
    assert len(log.lines) == 1 and log.lines[0][0] == "warning" and "//*[" in log.lines[0][1]
