"""`post.open_commenter_profile` opens an author's profile from the thread and comes back, as the loop does.

The Lab could read the people of a comment thread (`post.read_commenters`) but not open one of
them: the tap the commenters interaction loop makes (`make_commenters_source`, its `click` and its
return to the thread) had no Lab action, so a wrong element went unseen. On Instagram 447 the
reader took a @mention for an author (Lab bench, October 2026): the tap would have opened the
mentioned person. The action runs the loop's own source: its authors, its tap, its return.

The screens are real dumps, anonymized, of a Pixel 6a in French (Instagram 447): the comment sheet
of a post (`ig447_fr_comment_sheet.xml`) and a profile opened from it (`ig447_fr_profile_opened_from_search.xml`,
a profile of the same build; the profile the tap opens is not captured with the sheet).
"""

import pytest

import taktik.core.social_media.instagram.workflows.common.list_sources as list_sources
from bridges.tools.lab.actions.instagram import ACTION_REGISTRY, register_actions
from bridges.tools.lab.action_test.bundles.instagram import (
    build_instagram_action_bundle,
    create_instagram_device_facade,
)
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from unit.social_media.instagram.actions.atomic.interaction.sheet_phone import SheetPhone, capture

SHEET = capture("ig447_fr_comment_sheet.xml")
PROFILE = capture("ig447_fr_profile_opened_from_search.xml")


@pytest.fixture(autouse=True)
def _lab(monkeypatch):
    monkeypatch.setattr(list_sources.time, "sleep", lambda *_a, **_k: None)
    register_actions()
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _open(screens, params=None):
    phone = SheetPhone(SHEET, screens)
    bundle = build_instagram_action_bundle(create_instagram_device_facade(phone))
    return ACTION_REGISTRY["post.open_commenter_profile"](bundle, params or {}), phone


def _author_box(handle):
    """Bounds of the author's name on the sheet, as uiautomator2 reads them."""
    [label] = SheetPhone(SHEET, SHEET).xpath(
        f'//android.widget.TextView[starts-with(@content-desc, "{handle} ")]').all()
    return label.bounds


def test_the_first_author_is_opened_and_the_thread_is_back():
    result, phone = _open([PROFILE, SHEET])

    assert result["success"] is True, result
    assert result["details"]["username"] == "user_1"
    kind, x, y = phone.gestures[0]
    left, top, right, bottom = _author_box("user_1")
    assert kind == "click" and left <= x <= right and top <= y <= bottom
    assert phone.gestures[1][0] == "press"


def test_a_mentioned_person_is_not_an_author_to_open():
    result, phone = _open([PROFILE, SHEET], {"username": "user_4"})

    assert result["success"] is False
    assert "user_4" not in result["details"]["visible"]
    assert phone.gestures == []


def test_the_profile_is_waited_for_as_the_loop_waits(monkeypatch):
    """Checked at once after the tap, the profile read as not opened on the Pixel 6a (Instagram 447,
    October 2026: one tap, then the Back of the return): it was still loading. The loop waits for
    it (`wait_for_profile_screen`, 8 s); the action waits the same way."""
    phone = SheetPhone(SHEET, [PROFILE, SHEET])
    bundle = build_instagram_action_bundle(create_instagram_device_facade(phone))
    waited = []
    loaded_late = lambda timeout=0: waited.append(timeout) or True
    monkeypatch.setattr(bundle.detection, "is_on_profile_screen", lambda: False)
    monkeypatch.setattr(bundle.detection, "wait_for_profile_screen", loaded_late)

    result = ACTION_REGISTRY["post.open_commenter_profile"](bundle, {})

    assert result["details"]["profile_opened"] is True, result
    assert waited == [8.0]
