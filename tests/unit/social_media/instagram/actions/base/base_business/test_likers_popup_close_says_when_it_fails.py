"""Closing the likers popup says when it fails, instead of returning as if the sheet were closed.

`_close_likers_popup` (after the reading of the likers, the Lab's `post.read_likers`) drags the sheet
down five times at most. A sheet still open after the five, or a drag that raised, left no trace:
`except Exception: pass`, and nothing after the loop. The next step then ran on the sheet.

The screen is a real dump, anonymized: the likers sheet of a post liked twice (C57 S, Instagram 410
in English), on a phone where a drag down does not close it.
"""

import time

import pytest
from loguru import logger

from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.social_media.instagram.actions.base.base_business import BaseBusinessAction
from taktik.core.social_media.instagram.actions.base.device.facade import DeviceFacade
from unit.social_media.instagram.services.likers_sheet_phone import TWO_LIKERS, LikersSheetPhone
from unit.social_media.instagram.services.profile_posts_phone import PKG, capture


@pytest.fixture(autouse=True)
def _no_waits(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_: None)


@pytest.fixture
def warnings():
    lines = []
    sink = logger.add(lambda message: lines.append(message.record["message"]), level="WARNING")
    yield lines
    logger.remove(sink)


def _host(phone):
    host = BaseBusinessAction(DeviceFacade(CloneAwareDeviceProxy(phone, PKG)))
    host._human_like_delay = lambda *_a, **_kw: None
    return host


def test_a_sheet_still_open_after_the_drags_is_said(warnings):
    phone = LikersSheetPhone(capture(TWO_LIKERS), moves=False)

    assert _host(phone)._close_likers_popup() is False

    assert any("still open" in line for line in warnings), warnings


def test_a_drag_that_raises_is_said(warnings):
    host = _host(LikersSheetPhone(capture(TWO_LIKERS), moves=False))

    def drag_fails():
        raise RuntimeError("uiautomator2 is gone")

    host._close_popup_by_swipe_down = drag_fails

    assert host._close_likers_popup() is False
    assert any("uiautomator2 is gone" in line for line in warnings), warnings
