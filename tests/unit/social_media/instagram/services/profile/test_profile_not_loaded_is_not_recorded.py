"""A profile that has not loaded is not recorded as an empty one.

Pixel 3, 2026-09-28, a phone without mobile data: the visit of a public account reached its
profile, whose page stayed blank (the header container, no counter, no name). The counter readers
answered 0 for « not found », the extraction built a profile of 0 followers, 0 following and 0
posts, `save_profile_to_database` wrote it into `instagram_profiles`, and the run withdrew its like
for want of a post: a default value passed off as a measure. The proof that a profile has loaded
is a counter of its header read; without one, the extraction answers « not read » (None, as when
the screen is not a profile) and nothing is recorded.

The screens are real, Instagram 410.0.0.53.71 in French (Pixel 3), anonymized: the blank profile
of that run (`ig410_fr_profile_not_loaded.xml`, the bot's own dump of that visit), and a loaded profile
(`ig410_fr_profile_follow_back.xml`). They are read the way `d.xpath()` reads them
(`parse_ui_dump`); what the header readers do not decide (flags, name and bio, the button, the
avatar) answers as the screen would.
"""

from types import SimpleNamespace

import pytest
from loguru import logger

from taktik.core.shared.actions.utils import ActionUtils
from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.instagram.services.profile import persistence
from taktik.core.social_media.instagram.services.profile.extraction import ProfileExtraction
from taktik.core.social_media.instagram.ui.selectors.surfaces.profile import PROFILE_SELECTORS
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"


class _Found:
    def __init__(self, nodes):
        self._nodes = nodes

    @property
    def exists(self):
        return bool(self._nodes)

    def get_text(self):
        return self._nodes[0].get("text") if self._nodes else None


class _DumpPhone:
    """The facade's two reads the header counters use, answered from one dump."""

    app_id = "com.instagram.android"

    def __init__(self, name):
        self._tree = parse_ui_dump((FIXTURES / name).read_text(encoding="utf-8"))

    def xpath(self, selector):
        return _Found(self._tree.xpath(selector))

    def find(self, resourceId=None, **_kwargs):
        return _Found(self._tree.xpath(f'//*[@resource-id="{resourceId}"]'))


def _extraction(screen):
    extraction = object.__new__(ProfileExtraction)
    extraction.logger = logger
    extraction.utils = ActionUtils()
    extraction.device = _DumpPhone(screen)
    extraction.profile_selectors = PROFILE_SELECTORS
    extraction._random_sleep = lambda *_a, **_k: None
    extraction.detection_actions = SimpleNamespace(
        get_profile_flags_batch=lambda: {"is_private": False, "is_verified": False, "is_business": False},
        get_enriched_profile_data=lambda **_k: {"username": None, "full_name": None, "biography": None},
        get_username_from_profile=lambda: None,
        extract_profile_image=lambda: None,
    )
    extraction.click_actions = SimpleNamespace(get_follow_button_state=lambda: "unknown")
    return extraction


@pytest.fixture
def recorded(monkeypatch):
    saved = []
    monkeypatch.setattr(persistence, "save_profile_to_database", lambda info, log=None: saved.append(info))
    return saved


def test_a_blank_profile_is_not_read_nor_recorded(recorded):
    info = _extraction("ig410_fr_profile_not_loaded.xml").get_complete_profile_info(
        username="user_1", navigate_if_needed=False, emit_ipc=False)

    assert info is None
    assert recorded == []


def test_a_loaded_profile_is_read_and_recorded(recorded):
    info = _extraction("ig410_fr_profile_follow_back.xml").get_complete_profile_info(
        username="user_1", navigate_if_needed=False, emit_ipc=False)

    # Its header: 0 posts (a real zero, read as such), 92 followers, 142 following.
    assert (info["posts_count"], info["followers_count"], info["following_count"]) == (0, 92, 142)
    assert [saved["username"] for saved in recorded] == ["user_1"]


def test_a_counter_not_found_is_unknown_not_zero():
    extraction = _extraction("ig410_fr_profile_not_loaded.xml")

    assert extraction._get_followers_count_robust() is None
    assert extraction._get_following_count_robust() is None
    assert extraction._get_posts_count_robust() is None
