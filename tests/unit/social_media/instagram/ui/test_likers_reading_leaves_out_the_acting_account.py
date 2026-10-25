"""The reading of the likers (`extract_usernames_from_likers_popup`) leaves out the account the run acts as.

Given the run (`automation`), the reading keeps the eligible likers only: the ones that account has
not handled before. The account itself, among the likers of a post it liked, was kept as eligible:
its own profile handed to whoever walks the list (C57 S, Instagram 410 in English, 2026-10-25). It is
left out now, by the account the run knows (`automation.active_username`). Without the run (the
scraping's reading), every liker shown is kept, as before.

The screen is the real likers sheet of a post of the test account that the account liked itself
(`likers_sheet_phone`, C57 S): five likers, the account the fourth. The host is the Lab's `a.popup`,
`BaseBusinessAction`, built by its own constructor on that phone; the base's answer is the only
stand-in.
"""

import time
from types import SimpleNamespace

import pytest

from unit.social_media.instagram.services.likers_sheet_phone import (
    OWN_ACCOUNT, OWN_ACCOUNT_AMONG_LIKERS, LikersSheetPhone,
)
from unit.social_media.instagram.services.profile_posts_phone import PKG, capture
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService
from taktik.core.social_media.instagram.actions.base.base_business import BaseBusinessAction
from taktik.core.social_media.instagram.actions.base.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale


@pytest.fixture(autouse=True)
def _english_phone_no_waits(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    monkeypatch.setattr(InstagramWorkflowStateService, "is_profile_already_processed",
                        staticmethod(lambda *_a, **_kw: False))
    set_active_locale("en")
    yield
    set_active_locale(None)


def _read_likers(phone, automation):
    host = BaseBusinessAction(DeviceFacade(CloneAwareDeviceProxy(phone, PKG)), automation=automation)
    host._human_like_delay = lambda *_a, **_kw: None
    return host._extract_likers_after_click(max_interactions=10, multiply_by=1)


def test_the_acting_account_is_not_an_eligible_liker():
    phone = LikersSheetPhone(capture(OWN_ACCOUNT_AMONG_LIKERS), moves=False)
    others = sorted(name for name in phone.likers_shown() if name != OWN_ACCOUNT)

    likers = _read_likers(phone, SimpleNamespace(active_account_id=1, active_username=OWN_ACCOUNT))

    assert sorted(likers) == others
    assert len(phone.likers_after_each_drag_up) == 2, "the reading still ends on the end of the list"


def test_without_the_run_every_liker_shown_is_kept():
    phone = LikersSheetPhone(capture(OWN_ACCOUNT_AMONG_LIKERS), moves=False)

    likers = _read_likers(phone, None)

    assert sorted(likers) == phone.likers_shown()
