"""The workflow bench reads a follow list as production does, its selector tracer attached.

The bench (`workflow_test_bridge`) attaches the tracer of `taktik.core.compat.selectors` to the raw
device, the object the unfollow reads its list from. That list read takes ONE dump and answers
every selector from it (`d.xpath(selector, dump)`). The tracer's wrapper took the selector only: in
the bench each read raised a TypeError, the rows came back empty, and an unfollow run stopped on
"following list not proven read (0 of 54)" before any decision (C3 campaign on a Pixel 3a,
Instagram 410, 2026-09-28).

The screen is a real dump of Instagram 410 in English (the top of our own followers list, Pixel 3a,
2026-09-28, anonymized); followers and following lists share the rows the read pairs.

Since step 4 of the one-photo spec the read asks its selectors of one photo of the screen, not of
`d.xpath()`: the tracer on the raw device no longer sees them, and can no longer break them.
"""

import pytest

from fake_follow_list import FakeFacade, FakeScreen
from taktik.core.compat.selectors.tracer import SelectorTracer
from taktik.core.social_media.instagram.workflows.automation.unfollow.workflow import UnfollowBusiness
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
SCREEN = (FIXTURES / "ig410_en_own_followers_newest_first_1.xml").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _english():
    set_active_locale("en")
    yield
    set_active_locale(None)


class _Device(FakeScreen):
    """The raw device, noting the dump each selector is answered from (None: the live screen)."""

    def __init__(self, *screens):
        super().__init__(*screens)
        self.sources = []

    def xpath(self, xpath, source=None):
        self.sources.append(source)
        return super().xpath(xpath, source)


def _read(raw_device):
    rows = UnfollowBusiness(FakeFacade(raw_device))._visible_follow_rows()
    return [(row["username"], row["state"]) for row in rows]


def test_the_bench_reads_the_same_rows_from_the_same_dump_as_production():
    production_device = _Device(SCREEN)
    production_rows = _read(production_device)
    assert len(production_rows) >= 5

    bench_device = _Device(SCREEN)
    SelectorTracer().attach(bench_device)

    assert _read(bench_device) == production_rows


def test_the_rows_are_read_on_one_photo_not_through_the_traced_xpath():
    bench_device = _Device(SCREEN)
    recorded = []
    SelectorTracer(on_xpath_call=recorded.append).attach(bench_device)

    assert _read(bench_device)

    assert bench_device.dumps == 1
    assert bench_device.sources == [] and recorded == []
