"""The following list is sorted in French, and a sort counts only once the list's header names it.

The French options were never captured until a Pixel 3 on Instagram 410 showed them (2026-09-24):
"Par défaut", "Date de suivi : plus récent", "Date de suivi : plus ancien", with a non-breaking
space before the colon. Without them every French session read the whole list (1 928 accounts).
The structure below follows that sheet; the texts are Instagram's own.
"""

import pytest

from fake_follow_list import FakeFacade, FakeScreen
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.workflow import UnfollowBusiness
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale

PKG = "com.instagram.android"
NBSP = "\u00a0"
OPTIONS = ("Par défaut", f"Date de suivi{NBSP}: plus récent", f"Date de suivi{NBSP}: plus ancien")


def _header(sorted_by):
    return (f'<node index="0" text="Trié par {sorted_by}" resource-id="{PKG}:id/sorting_entry_row_option" '
            f'class="android.widget.TextView" content-desc="Trié par {sorted_by} En-tête" bounds="[44,860][418,919]" />'
            f'<node index="1" text="" resource-id="{PKG}:id/sorting_entry_row_icon" class="android.widget.Button" '
            f'content-desc="Trier par" clickable="true" bounds="[981,862][1036,917]" />')


def _screen(body):
    return ('<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
            '<node index="0" text="" resource-id="" class="android.widget.FrameLayout" bounds="[0,0][1080,2160]">'
            + body + "</node></hierarchy>")


def _sheet(sorted_by="Par défaut"):
    rows = "".join(
        f'<node index="{i}" text="{text}" resource-id="{PKG}:id/follow_list_sorting_option" '
        f'class="android.widget.TextView" bounds="[44,{1652 + 132 * i}][926,{1701 + 132 * i}]" />'
        for i, text in enumerate(OPTIONS))
    title = (f'<node index="0" text="Trier par" resource-id="{PKG}:id/follow_list_sorting_options_fragment_title" '
             'class="android.widget.TextView" bounds="[0,1455][1080,1587]" />')
    return _screen(_header(sorted_by) + title + rows)


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
    business, screen = _business(_sheet())
    found = [element.text for selector in business._unfollow_selectors[f"sort_option_{order}"]
             for element in screen.xpath(selector).all()]
    assert found == [expected]


def test_the_sort_counts_once_the_header_names_it():
    # list -> tap the sort icon -> the sheet -> tap "plus récent" -> the list, header updated
    business, screen = _business(_screen(_header("Par défaut")), _sheet(),
                                 _screen(_header(f"Date de suivi{NBSP}: plus récent")))

    assert business._set_following_list_sort("latest") is True


def test_a_tapped_option_the_header_does_not_name_is_not_a_sort():
    """The sync stops at the first known account only in that order: an unconfirmed tap would
    have it stop after one row of a list still in its default order."""
    business, screen = _business(_screen(_header("Par défaut")), _sheet(),
                                 _screen(_header("Par défaut")))

    assert business._set_following_list_sort("latest") is False
