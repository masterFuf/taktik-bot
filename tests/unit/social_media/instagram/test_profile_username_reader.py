"""The profile username reader keeps a handle and refuses everything else.

The last username selector matched any text holding "@". On a profile whose action bar could not be
read it landed on the biography, the reader took the whole line, `clean_username` squeezed it into
one word, and that word was saved as a profile.

The screens of the batch and enriched reads are real, Instagram 410.0.0.53.71, anonymized: a
French profile (Pixel 3a) whose bio mentions another account ("@..."), the same profile with its
action bar title removed (derived: the read the action bar could not serve), and the English "Discover
people" screen (Pixel 3a), whose title is no handle. The pseudos and bio of the single-read
tests (no screen, only the text each selector answers) are invented.
"""

from pathlib import Path
from types import SimpleNamespace

from lxml import etree

from loguru import logger

from taktik.core.shared.actions.utils import ActionUtils
from taktik.core.shared.device.snapshot import ScreenSnapshot
from taktik.core.social_media.instagram.actions.atomic.detection.profile_extraction import (
    ProfileExtractionMixin,
    _handle_from_node,
)
from taktik.core.social_media.instagram.actions.business.management.profile.extraction import (
    ProfileExtraction,
)
from taktik.core.social_media.instagram.ui.selectors.surfaces.profile import PROFILE_SELECTORS

BIO = "Podcast et critiques dédiés aux films, animé par @lina.photo et @marc_studio"


FIXTURES = Path(__file__).parent / "fixtures"
PROFILE = (FIXTURES / "ig410_fr_profile_highlights_only.xml").read_text(encoding="utf-8")
DISCOVER = (FIXTURES / "ig410_en_discover_people.xml").read_text(encoding="utf-8")
TITLE_ID = "com.instagram.android:id/action_bar_title"


def _title(xml):
    return etree.fromstring(xml.encode("utf-8")).xpath(f'//node[@resource-id="{TITLE_ID}"]/@text')[0]


def _without_action_bar(xml):
    root = etree.fromstring(xml.encode("utf-8"))
    for node in root.xpath('//node[contains(@resource-id, "action_bar_title")]'):
        node.getparent().remove(node)
    return etree.tostring(root, encoding="unicode")


class _DumpDevice:
    def __init__(self, xml):
        self._xml = xml

    def get_xml_dump(self, **_kwargs):
        return self._xml

    def snapshot(self):
        # The facade's screen photo: one dump.
        return ScreenSnapshot(self.get_xml_dump())

    def snapshot_of(self, xml):
        return ScreenSnapshot(xml)


class _XPathDevice:
    """Answers `xpath()` with the text the screen holds for that selector, nothing otherwise."""

    def __init__(self, texts, descriptions=None):
        self._texts = texts
        self._descriptions = descriptions or {}

    def xpath(self, selector):
        text = self._texts.get(selector)
        description = self._descriptions.get(selector)
        return SimpleNamespace(
            exists=text is not None or description is not None,
            get_text=lambda: text,
            get_attribute=lambda _name, _default="": description or "",
        )


def _reader(device):
    reader = object.__new__(ProfileExtractionMixin)
    reader.device = device
    reader.selectors = PROFILE_SELECTORS
    reader.logger = logger
    return reader


def test_a_handle_is_kept_and_a_sentence_refused():
    assert _handle_from_node("@lina.photo") == "lina.photo"
    assert _handle_from_node("  lina.photo ") == "lina.photo"
    assert _handle_from_node(BIO) is None
    assert _handle_from_node("Envoyer un message") is None


def test_the_batch_read_does_not_take_the_bio_for_the_username():
    xml = _without_action_bar(PROFILE)
    assert "@user_" in xml
    reader = _reader(_DumpDevice(xml))

    assert reader.get_profile_text_batch()["username"] is None


def test_the_batch_read_still_reads_the_action_bar():
    reader = _reader(_DumpDevice(PROFILE))

    assert reader.get_profile_text_batch()["username"] == _title(PROFILE).strip()


def test_the_enriched_read_refuses_a_title_that_is_no_handle():
    assert _title(DISCOVER) == "Discover people"
    reader = _reader(_DumpDevice(DISCOVER))

    assert reader.get_enriched_profile_data()["username"] is None


def test_the_single_read_skips_the_bio_line():
    reader = _reader(_XPathDevice({PROFILE_SELECTORS.username[-1]: BIO}))

    assert reader.get_username_from_profile() is None


def test_the_single_read_keeps_a_handle_further_down_the_list():
    reader = _reader(_XPathDevice({
        PROFILE_SELECTORS.username[-1]: BIO,
        PROFILE_SELECTORS.username[1]: "lina.photo",
    }))

    assert reader.get_username_from_profile() == "lina.photo"


def test_without_the_action_bar_the_handle_the_caller_stands_on_wins():
    """The broad fallback could return a handle mentioned in the bio: someone else's profile."""
    extraction = object.__new__(ProfileExtraction)
    extraction.logger = logger
    extraction.utils = ActionUtils()
    extraction._random_sleep = lambda *_a, **_k: None
    extraction._get_followers_count_robust = lambda: 120
    extraction._get_following_count_robust = lambda: 80
    extraction._get_posts_count_robust = lambda: 12
    extraction.click_actions = SimpleNamespace(get_follow_button_state=lambda: "follow")
    extraction.detection_actions = SimpleNamespace(
        get_profile_flags_batch=lambda: {},
        get_enriched_profile_data=lambda: {"username": None, "biography": BIO},
        count_visible_posts=lambda: 3,
        get_username_from_profile=lambda: "marc_studio",
        extract_profile_image=lambda: None,
    )

    info = extraction.get_complete_profile_info(
        username="lina.photo", navigate_if_needed=False, emit_ipc=False, save_to_db=False
    )

    assert info["username"] == "lina.photo"
