"""The inbox row and the Activity page of TikTok 47.0.3, read by the production.

The row that opens the page is renamed « Activité et nouveaux abonnés », the new followers having
moved into Activity (the inbox says so in a banner: « Les nouveaux followers déménagent. Retrouve-le
dans Activité »). The row is the inbox's Activity section, one definition
(`INBOX_SELECTORS.activity_section`, locale key `inbox.activity_section`), read by the production
that opens the page and by the one that lists the inbox sections.

The page it opens has no « Filtres » control any more: the filter is the arrow of its « Activité »
tab, beside a « Nouveaux followers » tab. `activity.page_indicator` names that tab under "47.0.3" in
the overrides; its rows, « Tout voir » and the suggested accounts read as on 43.1.4.

The screens are real captures, anonymized: the inbox of the Pixel 6a (TikTok 47.0.3 in French,
2026-09-29), taken before `tt.activity.open` in the Lab auto-test, and the page that tap opened
(the Lab pass of the same day, where the page went unrecognised). Evaluated by uiautomator2's
`d.xpath()` engine, as on the phone.
"""

import time
from pathlib import Path

import pytest
from uiautomator2.xpath import XPathEntry

from bridges.compat.diagnostics.actions.tiktok import ACTION_REGISTRY, register_actions
from bridges.compat.diagnostics.runtime.action_test.bundles.tiktok import build_tiktok_action_bundle
from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.social_media.tiktok.actions.atomic.interaction.activity_actions import ActivityActions
from taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions import DMActions
from taktik.core.social_media.tiktok.actions.core.device_facade import DeviceFacade
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale

FIXTURES = Path(__file__).parent / "fixtures"
INBOX_4703 = (FIXTURES / "tt4703_fr_inbox_activity_and_new_followers.xml").read_text(encoding="utf-8")
ACTIVITY_PAGE = "tt4703_fr_activity_page.xml"
PAGE_4703 = (FIXTURES / ACTIVITY_PAGE).read_text(encoding="utf-8")
SCREENS_4703 = sorted(path.name for path in FIXTURES.glob("tt4703_*.xml"))
#: The clickable row « Activité et nouveaux abonnés » of the inbox capture (left, top, right, bottom).
ACTIVITY_ROW = (0, 878, 1080, 1067)


def _inside(point, box):
    (x, y), (left, top, right, bottom) = point, box
    return left <= x <= right and top <= y <= bottom


class _Phone:
    """uiautomator2 as the production touches it: `xpath()`, one dump, and the taps it injects.

    `leads_to` is where a tap goes: (the area it has to land in, the screen that then shows), as the
    real phone went from the inbox to the Activity page.
    """

    wait_timeout = 0.2

    def __init__(self, xml, leads_to=None):
        self.xml = xml
        self.leads_to = leads_to
        self.xpath = XPathEntry(self)
        self.taps = []

    def dump_hierarchy(self, *_a, **_k):
        return self.xml

    def app_current(self):
        return {"package": "com.zhiliaoapp.musically", "activity": "demo.Activity"}

    def window_size(self):
        return (1080, 2400)

    def click(self, x, y):
        self.taps.append((x, y))
        if self.leads_to and _inside((x, y), self.leads_to[0]):
            self.xml = self.leads_to[1]


@pytest.fixture
def french_4703(monkeypatch):
    """A French phone on TikTok 47.0.3, as its connection and language detection leave the catalogues."""
    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)
    apply_version_overrides("tiktok", "47.0.3")
    set_active_locale("fr")
    yield
    set_active_locale(None)
    apply_version_overrides("tiktok", "43.1.4")


def _inbox_opening_the_page():
    return _Phone(INBOX_4703, leads_to=(ACTIVITY_ROW, PAGE_4703))


def test_the_activity_row_of_the_inbox_is_the_one_tapped(french_4703):
    phone = _Phone(INBOX_4703)
    # A still photo: the page never comes up. What is proven is the row found and tapped.
    ActivityActions(DeviceFacade(phone)).open_activity(expand=False)
    assert len(phone.taps) == 1
    assert _inside(phone.taps[0], ACTIVITY_ROW)


def test_the_inbox_lists_its_activity_section(french_4703):
    """The new followers have no section of their own any more; Activity and the system notifications do."""
    sections = DMActions(DeviceFacade(_Phone(INBOX_4703)))._get_notification_sections()
    assert [section["notification_type"] for section in sections] == ["activity", "system"]


def test_the_activity_page_opens_from_the_inbox(french_4703):
    """The Lab pass of 2026-09-29: one tap on the row, then « could not open it » on this very page."""
    phone = _inbox_opening_the_page()
    assert ActivityActions(DeviceFacade(phone)).open_activity(expand=False) is True
    assert len(phone.taps) == 1


@pytest.mark.parametrize("name", SCREENS_4703)
def test_the_page_is_recognised_on_its_capture_and_on_no_other_47_0_3_screen(french_4703, name):
    """The video editor of 47.0.3 has a « Filtres » button: the reference's entry would take it for
    this page, so the override does not carry it along."""
    phone = _Phone((FIXTURES / name).read_text(encoding="utf-8"))
    assert ActivityActions(DeviceFacade(phone)).is_on_activity_page() is (name == ACTIVITY_PAGE)


def test_the_rows_of_the_page_are_read(french_4703):
    """Newest first, as the page lists them. The follow row's 47.0.3 wording (« a commencé à te
    suivre ») is not in the row parser: it says so rather than guess (the new followers of 47.0.3
    are a later lot)."""
    rows = ActivityActions(DeviceFacade(_Phone(PAGE_4703))).read_activity(max_rows=4)
    assert [row.kind for row in rows] == ["follow_request_approved", "unknown", "like_video", "save_video"]


@pytest.fixture
def lab_4703(french_4703):
    register_actions()


def _lab(phone):
    return build_tiktok_action_bundle(DeviceFacade(phone))


def test_the_lab_opens_the_summary_the_suggestions_are_read_on(lab_4703):
    """`activity-summary-open`, the context of the suggested accounts' tests, which was blocked."""
    phone = _inbox_opening_the_page()
    result = ACTION_REGISTRY["tt.activity.open"](_lab(phone), {"expand": False})
    assert result["success"] is True
    accounts = ACTION_REGISTRY["tt.activity.suggested.read"](_lab(phone), {})
    assert accounts["success"] is True
    assert len(accounts["details"]["accounts"]) == 5


def test_the_lab_reads_the_rows_of_the_page(lab_4703):
    result = ACTION_REGISTRY["tt.activity.read"](_lab(_Phone(PAGE_4703)), {"max": 4})
    assert result["success"] is True
    assert result["details"]["unknown"]
