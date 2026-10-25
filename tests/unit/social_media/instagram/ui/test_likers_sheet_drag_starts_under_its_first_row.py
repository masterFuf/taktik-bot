"""The drag that scrolls the likers sheet starts under the sheet's first liker, as it was written to.

`scroll_likers_popup_up` looks for the first liker row to start its drag 100 px under it, and falls
back to a drag from 70 % to 45 % of the screen height. It looked for that row by
`follow_list_username`, an id Instagram 410 does not give the likers sheet (its rows carry
`row_user_primary_name`, which the reading of the likers uses): every drag of the C57 S session of
2026-10-25 logged "No username detected, fallback". It now looks for the row as the reading does
(`username_in_popup_selectors`).

A drag from the first row ends 400 px higher, but never above 35 % of the screen: with the first row
high on the screen (a sheet pulled up to full height) that path is short, or even goes down. Such a
drag, under `LIKERS_DRAG_MIN_TRAVEL` of the screen height, would hardly move the list, and two of them
would read as the end of the list: the proportional drag replaces it.

The screen is a real dump, anonymized: the likers sheet of a post liked twice (C57 S, Instagram 410
in English, 576x1280).
"""

import time

import pytest

import taktik.core.social_media.instagram.ui.extractors as extractors
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.device.ui_dump import parse_bounds, parse_ui_dump
from taktik.core.social_media.instagram.actions.base.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.extractors import InstagramUIExtractors
from unit.social_media.instagram.services.likers_sheet_phone import (
    C57S_H, ROW_NAME_ID, TWO_LIKERS, LikersSheetPhone,
)
from unit.social_media.instagram.services.profile_posts_phone import PKG, capture


@pytest.fixture(autouse=True)
def _no_waits(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_: None)


def test_the_drag_starts_under_the_first_liker_of_the_sheet():
    phone = LikersSheetPhone(capture(TWO_LIKERS), moves=False)
    rows = [parse_bounds(n.get("bounds")) for n in parse_ui_dump(phone.dump_hierarchy()).iter()
            if n.get("resource-id") == ROW_NAME_ID]
    _left, top, _right, bottom = rows[0]
    first_row_y = (top + bottom) // 2

    reader = InstagramUIExtractors(DeviceFacade(CloneAwareDeviceProxy(phone, PKG)))
    assert reader.scroll_likers_popup_up(verbose_logs=False) is True

    assert len(phone.drags) == 1
    start_y, end_y = phone.drags[0]
    assert start_y == first_row_y + 100, f"drag from y={start_y}, the first liker at y={first_row_y}"
    assert end_y < start_y


@pytest.mark.parametrize("first_row_y", [150, 300, 500])
def test_a_first_row_high_on_the_screen_gives_the_proportional_drag_never_a_short_one(first_row_y):
    from taktik.core.social_media.instagram.ui.extractors import likers_drag_path

    start_y, end_y = likers_drag_path(first_row_y, C57S_H)

    assert start_y - end_y >= int(C57S_H * extractors.LIKERS_DRAG_MIN_TRAVEL)
    assert (start_y, end_y) == (int(C57S_H * 0.70), int(C57S_H * 0.45))
