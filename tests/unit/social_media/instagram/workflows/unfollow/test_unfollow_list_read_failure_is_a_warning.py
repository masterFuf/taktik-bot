"""A follow list that cannot be read says so as a warning: an unreadable list is not an empty one.

`_visible_follow_rows` answers every selector from one dump. When that read raises, the rows come
back empty and the engine then refuses to decide, which is safe; but the error was written in
`debug`, the level a run's journal does not keep. That is what hid, for a whole campaign, the
workflow bench whose selector tracer broke every list read (C3 campaign on a Pixel 3a, Instagram
410, 2026-09-28: « Error reading the follow list rows: ... takes 1 positional argument but 2 were
given », three times, visible only in a debug journal).

The screen is a real dump of Instagram 410 in English (the top of our own followers list, Pixel 3a,
2026-09-28, anonymized); the device answers it, but its `xpath` fails the way the tracer's did.
"""

import pytest
from loguru import logger

from fake_follow_list import FakeFacade, FakeScreen
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.workflow import UnfollowBusiness
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
SCREEN = (FIXTURES / "ig410_en_own_followers_newest_first_1.xml").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _english():
    set_active_locale("en")
    yield
    set_active_locale(None)


@pytest.fixture
def journal():
    records = []
    sink = logger.add(lambda message: records.append(message.record), level="DEBUG")
    yield records
    logger.remove(sink)


class _TracedDevice(FakeScreen):
    """The raw device under the bench's old tracer: `xpath` took the selector only."""

    def xpath(self, xpath, *args):
        if args:
            raise TypeError("instrumented_xpath() takes 1 positional argument but 2 were given")
        return super().xpath(xpath)


def test_an_unreadable_list_is_a_warning_not_a_debug_line(journal):
    rows = UnfollowBusiness(FakeFacade(_TracedDevice(SCREEN)))._visible_follow_rows()

    assert rows == []
    failures = [r for r in journal if "Error reading the follow list rows" in r["message"]]
    assert [r["level"].name for r in failures] == ["WARNING"]


def test_a_readable_list_writes_no_warning(journal):
    rows = UnfollowBusiness(FakeFacade(FakeScreen(SCREEN)))._visible_follow_rows()

    assert len(rows) >= 5
    assert not [r for r in journal if "Error reading the follow list rows" in r["message"]]
