"""The workflow bench reads a follow list as production does, its selector tracer attached.

The bench (`workflow_test_bridge`) attaches the tracer of `taktik.core.compat.selectors` to the raw
device, the object the unfollow reads its list from. That list read takes ONE dump and answers
every selector from it (`d.xpath(selector, dump)`). The tracer's wrapper took the selector only: in
the bench each read raised a TypeError, the rows came back empty, and an unfollow run stopped on
"following list not proven read (0 of 54)" before any decision (C3 campaign on a Pixel 3a,
Instagram 410, 2026-09-28).

The screen is a real dump of Instagram 410 in English (the top of our own followers list, Pixel 3a,
2026-09-28, anonymized); followers and following lists share the rows the read pairs.
"""

from pathlib import Path

import pytest

from fake_follow_list import FakeFacade, FakeScreen
from taktik.core.compat.selectors.tracer import SelectorTracer
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.workflow import UnfollowBusiness
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale

FIXTURES = Path(__file__).parents[2] / "fixtures"
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
    assert production_device.sources and all(production_device.sources)

    bench_device = _Device(SCREEN)
    SelectorTracer().attach(bench_device)

    assert _read(bench_device) == production_rows
    assert bench_device.sources == production_device.sources


def test_the_tracer_still_records_the_reads_it_passes_the_dump_to():
    bench_device = _Device(SCREEN)
    recorded = []
    SelectorTracer(on_xpath_call=recorded.append).attach(bench_device)

    _read(bench_device)

    assert len(recorded) == len(bench_device.sources)
    assert all(call.error is None for call in recorded)
    assert any(call.found for call in recorded)
