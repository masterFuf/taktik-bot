"""`notifications.back_to_notifications` leaves what a mention test opened over the notifications.

`notifications.open_mention` opens the reply sheet of a mention (« Réponse à ... », the keyboard up,
the @mention prefilled) over the notifications list. On a Pixel 6a in French (Instagram 447, Lab
bench, October 2026) the next test of the plan ran under that sheet: the Filter tap landed through
it and the Back of its context left the notifications for the home feed, where the descent to the
suggestions made its 60 gestures. The plan now closes the sheet right after the test with this
action, the production return to the notifications (`_return_to_notifications`: Back until the
list is shown, the list under a sheet not counting as shown).

The screens are real dumps of that phone, anonymized together: the notifications list with a
mention row (`ig447_fr_notifications_with_mention.xml`) and the same list under the reply sheet
the test opened (`ig447_fr_notifications_mention_reply_sheet.xml`).
"""

import pytest

import taktik.core.social_media.instagram.workflows.notifications.notifications_workflow as notifications_workflow
from bridges.tools.lab.actions.instagram import ACTION_REGISTRY, register_actions
from bridges.tools.lab.action_test.bundles.instagram import (
    build_instagram_action_bundle,
    create_instagram_device_facade,
)
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from unit.social_media.instagram.actions.atomic.interaction.sheet_phone import SheetPhone, capture

LIST = capture("ig447_fr_notifications_with_mention.xml")
REPLY_SHEET = capture("ig447_fr_notifications_mention_reply_sheet.xml")


@pytest.fixture(autouse=True)
def _lab(monkeypatch):
    monkeypatch.setattr(notifications_workflow.time, "sleep", lambda *_a, **_k: None)
    register_actions()
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _back(screen, after):
    phone = SheetPhone(screen, after)
    bundle = build_instagram_action_bundle(create_instagram_device_facade(phone))
    return ACTION_REGISTRY["notifications.back_to_notifications"](bundle, {}), phone


def test_the_reply_sheet_is_left_for_the_list():
    result, phone = _back(REPLY_SHEET, LIST)

    assert result["success"] is True, result
    assert [gesture[0] for gesture in phone.gestures] == ["press"]


def test_on_the_list_nothing_is_pressed():
    result, phone = _back(LIST, LIST)

    assert result["success"] is True, result
    assert phone.gestures == []


def test_a_sheet_that_does_not_close_is_a_failure():
    result, phone = _back(REPLY_SHEET, REPLY_SHEET)

    assert result["success"] is False
    assert len(phone.gestures) == 3
