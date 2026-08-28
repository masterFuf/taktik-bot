"""The test that was missing for three months.

`extract_profile_from_screen` returned its defaults on every screen, on both app versions, since
around March 2026: it pulled a resource-id out of each selector with a regex that only matches
`@resource-id="…"`, while the profile catalogue writes `contains(@resource-id, ":id/…")`. Every
read took an `if rid:` false branch and nothing raised.

235 unit tests were green throughout, because none of them put a screen in front of the function.
This one does — a fake device answering xpath queries — and it fails if the reader stops reading.
"""

from taktik.core.social_media.tiktok.actions.business.workflows._internal.profile_extractor import (
    extract_profile_from_screen,
)
from taktik.core.social_media.tiktok.ui.selectors.surfaces.profile import PROFILE_SELECTORS


class _Element:
    def __init__(self, text):
        self.text = text


class _Query:
    def __init__(self, elements):
        self._elements = elements

    def all(self):
        return list(self._elements)


class _Collection:
    """uiautomator2's kwargs-selector result: `.exists`, `.count`, indexable."""

    def __init__(self, elements):
        self._elements = list(elements)

    @property
    def exists(self):
        return bool(self._elements)

    @property
    def count(self):
        return len(self._elements)

    def __getitem__(self, index):
        element = self._elements[index]

        class _Node:
            @staticmethod
            def get_text():
                return element.text

        return _Node()


class _FakeDevice:
    """Answers a selector with whatever the screen holds for it, and nothing for anything else.

    Keyed by the REAL catalogue selectors, so the test breaks the day the catalogue's anchors
    change shape again — which is the failure it exists to catch.

    `__call__` supports the kwargs API because the extractor legitimately uses it for the probes
    (`textContains`, `descriptionContains`) — that addressing mode was never the problem. What it
    refuses is `resourceId=`, the one that died: an id pulled out of an xpath by regex, which
    returned '' for every `contains()` anchor. If that pattern ever comes back, this fails loudly
    instead of returning defaults the way production did for three months.
    """

    def __init__(self, screen, probes=None):
        self._screen = screen
        self._probes = probes or {}

    def xpath(self, selector):
        return _Query(self._screen.get(selector, []))

    def __call__(self, **kwargs):
        if "resourceId" in kwargs:
            raise AssertionError(
                "resourceId= addressing is the path that died silently — read the selector list"
            )
        for key, value in kwargs.items():
            if (key, value) in self._probes:
                return _Collection(self._probes[(key, value)])
        return _Collection([])


def _screen_with(username="marvin", display="Marvin N.", bio="chat, cuisine et velo",
                 stats=(("1 363", "Abonnements"), ("5 215", "Abonnés"), ("39,7 K", "J’aime"))):
    """A French profile screen, on the catalogue's own selectors.

    The labels carry their accents and the counters their narrow no-break space, because that
    is what the device sends: `Abonnés` classifies, `Abonnes` does not, and a fixture that
    spelled it flat would test a screen no phone ever shows.
    """
    screen = {
        PROFILE_SELECTORS.username[0]: [_Element(f"@{username}")],
        PROFILE_SELECTORS.display_name[0]: [_Element(display)],
        PROFILE_SELECTORS.bio_text[0]: [_Element(bio)],
        PROFILE_SELECTORS.stat_value[0]: [_Element(value) for value, _ in stats],
        PROFILE_SELECTORS.stat_label[0]: [_Element(label) for _, label in stats],
    }
    return screen


def test_the_reader_actually_reads_a_profile():
    device = _FakeDevice(_screen_with())
    data = extract_profile_from_screen(device)

    assert data is not None
    assert data["username"] == "marvin"
    assert data["display_name"] == "Marvin N."
    assert data["bio"] == "chat, cuisine et velo"


def test_french_counters_reach_the_right_fields():
    """Two bugs met here: the dead reader, and the parser that returned 0 on a narrow space."""
    device = _FakeDevice(_screen_with())
    data = extract_profile_from_screen(device)

    assert data["following_count"] == 1363
    assert data["followers_count"] == 5215
    assert data["likes_count"] == 39700


def test_the_selector_list_is_an_ordered_set_of_alternatives():
    """Only the SECOND selector matches — the musically / trill package split. First wins is wrong."""
    screen = {PROFILE_SELECTORS.username[-1]: [_Element("@fallback")]}
    data = extract_profile_from_screen(_FakeDevice(screen))
    assert data["username"] == "fallback"


def test_an_empty_screen_returns_defaults_rather_than_raising():
    data = extract_profile_from_screen(_FakeDevice({}))
    assert data is not None
    assert data["username"] == ""
    assert data["followers_count"] == 0


def test_a_known_username_survives_an_unreadable_screen():
    data = extract_profile_from_screen(_FakeDevice({}), username="from_the_caller")
    assert data["username"] == "from_the_caller"
