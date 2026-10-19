"""The cold DM opens the account it searched for, or nobody.

Instagram 447 (Pixel 6a, in French, 2026-09-28) no longer lists some accounts among the accounts its
search shows: typed "nasa", the screen held a "keyword" row whose subtitle names the account ("nasa •
104 M followers"), and account rows for others, the first of them @nasahubble. The production profile
search asks for the exact handle and opened nobody (it then falls back to the deep link). The cold DM
search, its own, took the first account row whose handle CONTAINED the query, or was contained in
it: on that screen it opened @nasahubble, and the DM would have gone to someone else. It now asks
for the row of the exact handle, with the production profile search's own selectors
(`search_result_selectors_for_username`), and opens nobody when it is not there.

The screen is that capture, anonymized (`anonymize_dump.py`), the anonymizer's names for the two
handles chosen so that the row shown keeps the query in its handle as on the phone: the searched
account is `user_3`, the row's `user_3x`. The phone answers `xpath` through uiautomator2's own engine
and `d(...)` from the same dump (the rig of `test_cold_dm_reads_only_a_profile.py`), behind the
clone proxy and the facade the bridge mounts. The keyboard is not what is tested: it types.
"""

import pytest

import taktik.core.social_media.instagram.workflows.cold_dm.search as cold_dm_search
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from test_cold_dm_reads_only_a_profile import FIXTURES, _Phone, _workflow

SEARCH_447 = (FIXTURES / "ig447_fr_search_account_only_in_keyword_row.xml").read_text(encoding="utf-8")
#: The account rows of the capture, by handle: their bounds.
ROWS = {"user_3x": (0, 1191, 1080, 1343), "user_2": (0, 1343, 1080, 1495)}


@pytest.fixture(autouse=True)
def _typed_and_no_waits(monkeypatch):
    monkeypatch.setattr(cold_dm_search, "ensure_taktik_keyboard", lambda *_a, **_k: True)
    monkeypatch.setattr(cold_dm_search, "type_text_checked", lambda *_a, **_k: True)
    monkeypatch.setattr(cold_dm_search, "resolve_device_id", lambda *_a, **_k: "demo-phone")
    monkeypatch.setattr(cold_dm_search.time, "sleep", lambda *_: None)
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _taps_in(phone, box):
    left, top, right, bottom = box
    return [tap for tap in phone.taps if left <= tap[0] <= right and top <= tap[1] <= bottom]


def test_an_account_the_results_do_not_list_opens_nobody():
    phone = _Phone(SEARCH_447)

    found = _workflow(phone).search_user("user_3")

    assert found is False
    # The search bar is tapped to type; no row is.
    assert not any(_taps_in(phone, box) for box in ROWS.values())


def test_an_account_the_results_list_is_opened():
    phone = _Phone(SEARCH_447)

    found = _workflow(phone).search_user("user_2")

    assert found is True
    assert len(_taps_in(phone, ROWS["user_2"])) == 1
    assert _taps_in(phone, ROWS["user_3x"]) == []
