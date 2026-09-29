"""The Lab opens "Discover people" the way every suggestions pass does: "See all", the answer to the
contacts-access prompt Instagram shows right after it, then the screen.

On the Pixel 6a (Instagram 447 in French), the Lab's `suggestions.open_see_all` only tapped "See
all". Instagram then asked for the contacts, and the tests that need the screen open
(`suggestions.scan_rows`...) read the prompt instead: "no suggestion row on this screen". The
production passes answer it right after the tap (deny, their default).

The screens are real dumps of that phone, anonymized, in the order they came:
- `ig447_fr_feed_carousel_before_see_all.xml`: the home feed, the suggestions carousel and its
  "Voir tout" (a Compose node, no id);
- `ig447_fr_discover_people_contacts_prompt.xml`: the prompt that "Voir tout" opened (the dump holds
  the prompt's window only);
- `ig447_fr_discover_people.xml`: the discovery screen, taken after a later "Voir tout" of the same
  session, when Instagram did not ask; it stands for the screen behind the answered prompt.
"""

from types import SimpleNamespace

import pytest
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.device.facade as shared_facade_module
import taktik.core.social_media.instagram.actions.atomic.navigation.tab_navigation as tab_navigation
import taktik.core.social_media.instagram.actions.business.workflows.feed.suggestions as suggestions_module
import taktik.core.social_media.instagram.actions.core.device.facade as facade_module
from bridges.tools.lab.actions.instagram.suggestions import open_see_all
from bridges.tools.lab.action_test.bundles.instagram import build_instagram_action_bundle
from profile_posts_phone import PKG, bounds_of, capture
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale

FEED_WITH_CAROUSEL = capture("ig447_fr_feed_carousel_before_see_all.xml")
CONTACTS_PROMPT = capture("ig447_fr_discover_people_contacts_prompt.xml")
DISCOVER_PEOPLE = capture("ig447_fr_discover_people.xml")
DENY_ID = f"{PKG}:id/igds_alert_dialog_cancel_button"
ALLOW_ID = f"{PKG}:id/igds_alert_dialog_primary_button"
PIXEL_6A_HEIGHT = 2400


def _see_all(node):
    return (node.get("text") or "") == "Voir tout"


def _deny(node):
    return node.get("resource-id") == DENY_ID


class ScenePhone:
    """uiautomator2 on a phone that shows real captures one after the other: a tap on the element
    that leads on (`scenes`: capture, which node leads on) shows the next capture. Every tap is kept,
    with what it landed on."""

    wait_timeout = 1.0

    def __init__(self, scenes):
        self.scenes = list(scenes)
        self.info = {"displayWidth": 1080, "displayHeight": PIXEL_6A_HEIGHT}
        self.taps = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_args, **_kwargs):
        return self.scenes[0][0]

    def app_current(self):
        return {"package": PKG}

    def window_size(self):
        return 1080, PIXEL_6A_HEIGHT

    def press(self, key, meta=None):
        self.taps.append(("press", key))
        return True

    def long_click(self, x, y, duration=0.0):
        self.click(x, y)

    def click(self, x, y):
        xml, leads_on = self.scenes[0]
        hit = [node for node in parse_ui_dump(xml).iter()
               if node.get("bounds") and _inside((x, y), bounds_of(node))]
        self.taps.append((x, y, [n.get("resource-id") or n.get("text") for n in hit][-1:]))
        if leads_on is not None and any(leads_on(node) for node in hit) and len(self.scenes) > 1:
            self.scenes.pop(0)


def _inside(point, bounds):
    x, y = point
    left, top, right, bottom = bounds
    return left <= x <= right and top <= y <= bottom


@pytest.fixture(autouse=True)
def _french_phone_no_waits(monkeypatch):
    for module in (facade_module, shared_facade_module, suggestions_module, tab_navigation):
        monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _lab(phone):
    """The Lab's bundle, built by its own factory on the phone, its pacing cut."""
    bundle = build_instagram_action_bundle(DeviceFacade(CloneAwareDeviceProxy(phone, PKG)))
    bundle.feed._human_like_delay = lambda *_args, **_kwargs: None
    return bundle


def _node(xml, predicate):
    return next(node for node in parse_ui_dump(xml).iter() if predicate(node))


def test_the_labs_see_all_answers_the_contacts_prompt_then_reaches_the_screen():
    phone = ScenePhone([(FEED_WITH_CAROUSEL, _see_all), (CONTACTS_PROMPT, _deny), (DISCOVER_PEOPLE, None)])

    result = open_see_all(_lab(phone), {})

    taps = [tap for tap in phone.taps if tap[0] != "press"]
    assert len(taps) == 2, f"a tap on 'Voir tout' then one on the prompt expected, got {phone.taps}"
    assert _inside(taps[0][:2], bounds_of(_node(FEED_WITH_CAROUSEL, _see_all)))
    assert _inside(taps[1][:2], bounds_of(_node(CONTACTS_PROMPT, _deny))), (
        f"the prompt's answer went to {taps[1]}: the deny button is {bounds_of(_node(CONTACTS_PROMPT, _deny))}")
    assert phone.scenes[0][0] is DISCOVER_PEOPLE, "the discovery screen was never reached"
    assert result["success"] is True


def test_no_prompt_the_screen_opens_with_one_tap():
    phone = ScenePhone([(FEED_WITH_CAROUSEL, _see_all), (DISCOVER_PEOPLE, None)])

    result = open_see_all(_lab(phone), {})

    assert [tap for tap in phone.taps if tap[0] != "press"][1:] == []
    assert result["success"] is True


def test_another_alert_is_never_answered():
    # The same generic alert chassis with another headline (a restriction, an update): left
    # untouched, and the screen is not taken for reached.
    other_alert = CONTACTS_PROMPT.replace("Autoriser Instagram à accéder à vos contacts", "Réessayer plus tard")
    phone = ScenePhone([(FEED_WITH_CAROUSEL, _see_all), (other_alert, None)])
    lab = _lab(phone)
    # The way back to the feed (its own tests) looks for a tab bar this alert does not have, 3 s
    # per try: not what this test is about.
    lab.feed._return_to_feed = lambda: False

    result = open_see_all(lab, {})

    assert not any(_inside(tap[:2], bounds_of(_node(other_alert, _deny)))
                   or _inside(tap[:2], bounds_of(_node(other_alert, lambda n: n.get("resource-id") == ALLOW_ID)))
                   for tap in phone.taps if tap[0] != "press")
    assert result["success"] is False
    assert result["details"]["stop_reason"] == "blocked_by_dialog"


@pytest.mark.parametrize("run_pass", ["run_feed_suggestions_pass", "run_discover_visit_pass"])
def test_every_suggestions_pass_enters_through_the_step_the_lab_replays(run_pass):
    # The bulk follow and the qualified visit enter the screen by the very step `open_see_all`
    # runs: what the Lab proves is what a run does.
    feed = _lab(ScenePhone([(FEED_WITH_CAROUSEL, _see_all), (CONTACTS_PROMPT, _deny)])).feed
    entries = []

    def entry(contacts_choice="deny"):
        entries.append(contacts_choice)
        return {"entered": False, "contacts_dialog": "absent", "stop_reason": "cta_tap_failed",
                "returned_to_feed": False}

    feed.enter_discover_people_screen = entry
    result = getattr(feed, run_pass)({"suggestions_contacts_choice": "deny"})

    assert entries == ["deny"]
    assert result["stop_reason"] == "cta_tap_failed" and result["entered"] is False
