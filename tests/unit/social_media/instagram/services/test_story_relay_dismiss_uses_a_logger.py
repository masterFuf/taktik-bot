"""The story relay closes the share sheet it opened with a real logger.

`dismiss_share_sheet(device, log=...)` writes `log.debug(...)` / `log.info(...)`: it wants a
logger. The relay once handed it `self.logger.debug` (a bound method), so the first journal
line of the dismissal raised AttributeError ('function' object has no attribute 'debug') and
the "add to my story not offered" answer turned into a crash.
"""

import logging

from taktik.core.social_media.instagram.services.story_relay import StoryRelayBusiness


class _Element:
    exists = True


class _Device:
    """A share sheet that closes on the first back press."""

    def __init__(self):
        self.closed = False

    def xpath(self, _selector):
        element = _Element()
        element.exists = not self.closed
        return element

    def press(self, key):
        assert key == "back"
        self.closed = True

    def get_screen_size(self):
        return 1080, 2400


class _Clicks:
    def open_story_share_sheet(self):
        return True

    def tap_add_to_my_story(self):
        return False


def test_a_story_that_offers_no_relay_closes_the_sheet_and_answers_unavailable(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _s: None)
    relay = object.__new__(StoryRelayBusiness)
    relay.device = _Device()
    relay.logger = logging.getLogger("story-relay-test")
    relay.click_actions = _Clicks()

    result = relay.push_current_story_to_mine()

    assert result == {"status": "unavailable", "reason": "add_to_story_not_offered"}
    assert relay.device.closed is True
