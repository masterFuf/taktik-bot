"""The following list is sorted in French, and a sort counts only once the list's header names it.

The French options were never captured until a Pixel 3 on Instagram 410 showed them (2026-09-24):
"Par défaut", "Date de suivi : plus récent", "Date de suivi : plus ancien", with a non-breaking
space before the colon. Without them every French session read the whole list (1 928 accounts).

The screens are the dumps of that phone, anonymized (the sort header and the options keep their
own words): the following list in its default order, the sort sheet opened over it, and the list
once sorted by the latest follows (`fixtures/ig410_fr_following_list_*.xml`).
"""

import pytest

from fake_follow_list import FakeFacade, FakeScreen
from taktik.core.social_media.instagram.workflows.automation.unfollow.workflow import UnfollowBusiness
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from unit.paths import CORE

NBSP = "\u00a0"
OPTIONS = ("Par défaut", f"Date de suivi{NBSP}: plus récent", f"Date de suivi{NBSP}: plus ancien")
FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"


def _capture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


LIST_DEFAULT = _capture("ig410_fr_following_list_sorted_default.xml")
SHEET = _capture("ig410_fr_following_list_sort_sheet.xml")
LIST_LATEST = _capture("ig410_fr_following_list_sorted_latest.xml")


@pytest.fixture(autouse=True)
def _french(monkeypatch):
    set_active_locale("fr")
    monkeypatch.setattr(UnfollowBusiness, "sort_confirm_timeout", 0.0)
    yield
    set_active_locale(None)


def _business(*screens):
    screen = FakeScreen(*screens)
    return UnfollowBusiness(FakeFacade(screen)), screen


@pytest.mark.parametrize("order, expected", [
    ("latest", OPTIONS[1]), ("earliest", OPTIONS[2]), ("default", OPTIONS[0]),
])
def test_each_french_option_is_found_despite_the_non_breaking_space(order, expected):
    business, screen = _business(SHEET)
    found = [element.text for selector in business._unfollow_selectors[f"sort_option_{order}"]
             for element in screen.xpath(selector).all()]
    assert found == [expected]


def test_the_sort_counts_once_the_header_names_it():
    # list -> tap the sort icon -> the sheet -> tap "plus récent" -> the list, header updated
    business, screen = _business(LIST_DEFAULT, SHEET, LIST_LATEST)

    assert business._set_following_list_sort("latest") is True


def test_a_tapped_option_the_header_does_not_name_is_not_a_sort():
    """The sync stops at the first known account only in that order: an unconfirmed tap would
    have it stop after one row of a list still in its default order."""
    business, screen = _business(LIST_DEFAULT, SHEET, LIST_DEFAULT)

    assert business._set_following_list_sort("latest") is False
