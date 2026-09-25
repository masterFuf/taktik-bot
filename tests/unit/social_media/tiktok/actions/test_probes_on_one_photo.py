"""TikTok's waiting probes read ONE photo per turn, not one dump per selector.

`_element_exists`, `_get_element_text` and `_get_element_content_desc` kept their timeout, their
pause between turns and "the first selector that answers"; each turn now asks all its selectors of
one photo of the screen (step 2 of the one-photo spec). The phone is uiautomator2's own
`XPathEntry` on invented screens; its clock only moves when the code dumps or sleeps.
"""

from types import SimpleNamespace

import pytest
from uiautomator2.xpath import XPathEntry

import taktik.core.social_media.tiktok.actions.core.base_action as base_action_module
from taktik.core.social_media.tiktok.actions.core.base_action import BaseAction

DUMP_S = 0.25


def _node(cls="TextView", text="", desc="", rid=""):
    return (f'<node class="android.widget.{cls}" text="{text}" content-desc="{desc}" '
            f'resource-id="{rid}" bounds="[0,0][10,10]" />')


def _screen(*nodes):
    return f'<hierarchy rotation="0">{"".join(nodes)}</hierarchy>'


SCREEN = _screen(
    _node(text="", rid="demo:id/first"),
    _node(text="  ", rid="demo:id/blank"),
    _node(text="demo_author", rid="demo:id/author"),
    _node(text="second", rid="demo:id/author"),
    _node("Button", desc="Profil demo_author", rid="demo:id/avatar"),
)


class _Phone:
    """A phone whose screens are dumped in turn (the last one stays); a screen may be an error."""

    wait_timeout = 1.0

    def __init__(self, clock, *screens):
        self.clock = clock
        self.screens = list(screens)
        self.dumps = 0
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        self.dumps += 1
        self.clock.now += DUMP_S
        screen = self.screens.pop(0) if len(self.screens) > 1 else self.screens[0]
        if isinstance(screen, Exception):
            raise screen
        return screen


@pytest.fixture
def clock(monkeypatch):
    fake = SimpleNamespace(now=1000.0)
    fake.time = lambda: fake.now
    fake.sleep = lambda seconds: setattr(fake, "now", fake.now + seconds)
    monkeypatch.setattr(base_action_module, "time", fake)
    return fake


def _action(clock, *screens):
    phone = _Phone(clock, *screens)
    return BaseAction(phone), phone


def test_a_turn_asks_every_selector_of_one_photo(clock):
    action, phone = _action(clock, SCREEN)
    absent = ['//*[@text="a"]', '//*[@text="b"]', '//*[@text="c"]', '//*[@text="d"]']
    assert action._element_exists(absent + ['//*[@resource-id="demo:id/author"]'], timeout=1) is True
    assert phone.dumps == 1


def test_an_absence_costs_one_photo_per_turn_until_the_timeout(clock):
    action, phone = _action(clock, SCREEN)
    absent = ['//*[@text="a"]', '//*[@text="b"]', '//*[@text="c"]', '//*[@text="d"]']
    started = clock.now
    assert action._element_exists(absent, timeout=1) is False
    # Turns start at 0, 0.55 and 1.1 s: the third is past the timeout. Before, each turn was
    # four dumps.
    assert phone.dumps == 2
    assert clock.now - started == pytest.approx(2 * (DUMP_S + 0.3))


def test_no_timeout_means_no_question(clock):
    action, phone = _action(clock, SCREEN)
    assert action._element_exists(['//*[@resource-id="demo:id/author"]'], timeout=0) is False
    assert action._get_element_text(['//*[@resource-id="demo:id/author"]'], timeout=0) is None
    assert phone.dumps == 0


def test_the_first_non_empty_text_wins_and_it_is_the_first_element_s(clock):
    action, phone = _action(clock, SCREEN)
    selectors = ['//*[@resource-id="demo:id/first"]', '//*[@resource-id="demo:id/author"]']
    assert action._get_element_text(selectors, timeout=1) == "demo_author"
    assert phone.dumps == 1


def test_a_blank_text_is_returned_stripped_as_it_always_was(clock):
    """`get_text()` of "  " is truthy: the old loop returned "" there, and so does the photo."""
    action, _ = _action(clock, SCREEN)
    assert action._get_element_text(['//*[@resource-id="demo:id/blank"]',
                                     '//*[@resource-id="demo:id/author"]'], timeout=1) == ""


def test_the_first_non_empty_content_desc_wins(clock):
    action, phone = _action(clock, SCREEN)
    selectors = ['//*[@resource-id="demo:id/author"]', '//*[@resource-id="demo:id/avatar"]']
    assert action._get_element_content_desc(selectors, timeout=1) == "Profil demo_author"
    assert phone.dumps == 1


def test_an_invalid_selector_is_skipped(clock):
    action, _ = _action(clock, SCREEN)
    assert action._element_exists(['//*[', '//*[@resource-id="demo:id/author"]'], timeout=1) is True
    assert action._get_element_text(['//*[', '//*[@resource-id="demo:id/author"]'], timeout=1) == "demo_author"


def test_a_failed_dump_finds_nothing_that_turn_and_the_wait_goes_on(clock):
    action, phone = _action(clock, RuntimeError("uiautomator2 server down"), _screen(), SCREEN)
    assert action._get_element_text(['//*[@resource-id="demo:id/author"]'], timeout=2) == "demo_author"
    assert phone.dumps == 3  # the error, an empty hierarchy, then the screen


def test_a_screen_already_read_answers_at_once(clock):
    action, phone = _action(clock, SCREEN)
    photo = action.device.snapshot()
    started, dumps = clock.now, phone.dumps
    assert action._element_exists(['//*[@text="absent"]'], timeout=5, screen=photo) is False
    assert action._get_element_text(['//*[@resource-id="demo:id/author"]'], timeout=5, screen=photo) == "demo_author"
    assert action._get_element_content_desc(['//*[@resource-id="demo:id/avatar"]'], timeout=5,
                                            screen=photo) == "Profil demo_author"
    assert (phone.dumps, clock.now) == (dumps, started)


def test_a_screen_that_could_not_be_read_answers_nothing(clock):
    action, phone = _action(clock, SCREEN)
    unread = SimpleNamespace(photo=None)
    assert action._element_exists(['//*[@resource-id="demo:id/author"]'], screen=unread) is False
    assert action._get_element_text(['//*[@resource-id="demo:id/author"]'], screen=unread) is None
    assert phone.dumps == 0
