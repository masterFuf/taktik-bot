"""TikTok language detection must never commit to the WRONG language.

TikTok carried the exact bug Instagram was fixed for on 2026-07-12, and carried it until
2026-07-31: probes were tested as substrings of the RAW XML, which always holds English
identifiers (`:id/home_tab`, `:id/profile_tab`, `:id/inbox_tab`, `:id/friends_tab`,
`:id/create_button`). English therefore collected one free point per probe on every dump,
language-independently.

Measured on a French dump whose only visible strings were "Abonnements" and "Abonnés":
`en (FR=0.5, EN=2.5)` — a French app declared English. That is worse than 'unknown':
committing STRIPS the French selectors, where 'unknown' keeps every locale (overlay union).
"""

import pytest

from taktik.core.social_media.tiktok.ui import language


class _FakeDevice:
    def __init__(self, xml):
        self._xml = xml

    def get_xml_dump(self):
        return self._xml


@pytest.fixture(autouse=True)
def _reset_lang():
    """Leave the process exactly as found: deciding a language sets the active locale AND
    filters the shared selector dataclasses IN PLACE, so a decision that escapes hands the
    next test an amputated catalogue."""
    from taktik.core.social_media.tiktok.ui.selectors.locales import (
        active_locale, set_active_locale,
    )
    before = active_locale()
    language._DETECTION._detected_lang = None
    yield
    language._DETECTION._detected_lang = None
    set_active_locale(before)


@pytest.fixture
def _no_inplace_filtering(monkeypatch):
    monkeypatch.setattr(language._DETECTION, 'optimize_selector_dataclass', lambda inst, lang: 0)


# Present on EVERY TikTok dump, whatever the app language.
_ENGLISH_IDS = (
    '<node resource-id="com.zhiliaoapp.musically:id/home_tab" />'
    '<node resource-id="com.zhiliaoapp.musically:id/profile_tab" />'
    '<node resource-id="com.zhiliaoapp.musically:id/inbox_tab" />'
    '<node resource-id="com.zhiliaoapp.musically:id/friends_tab" />'
    '<node resource-id="com.zhiliaoapp.musically:id/create_button" />'
)


def test_english_resource_ids_alone_never_decide_the_language():
    """The exact regression: this dump used to score EN=2.5 and win."""
    assert language.detect_language(_FakeDevice(_ENGLISH_IDS)) == 'unknown'


def test_a_french_app_is_not_declared_english_by_its_resource_ids():
    """The dump that proved the bug: two French words against five English identifiers."""
    xml = _ENGLISH_IDS + (
        '<node content-desc="Abonnements" /><node content-desc="Abonnés" />'
    )
    assert language.detect_language(_FakeDevice(xml)) != 'en'


def test_a_french_screen_is_detected_french():
    xml = _ENGLISH_IDS + (
        '<node content-desc="Accueil" /><node content-desc="Profil" />'
        '<node content-desc="Abonnements" /><node content-desc="Abonnés" />'
        '<node text="J’aime" />'
    )
    assert language.detect_language(_FakeDevice(xml)) == 'fr'


def test_an_english_screen_is_detected_english():
    xml = _ENGLISH_IDS + (
        '<node content-desc="Home" /><node content-desc="Profile" />'
        '<node content-desc="Following" /><node content-desc="Followers" />'
        '<node text="Likes" />'
    )
    assert language.detect_language(_FakeDevice(xml)) == 'en'


def test_ambiguous_scores_stay_unknown():
    """A close call must not strip a locale."""
    xml = _ENGLISH_IDS + '<node content-desc="Accueil" /><node content-desc="Home" />'
    assert language.detect_language(_FakeDevice(xml)) == 'unknown'


def test_redetection_only_happens_while_the_language_is_undecided(_no_inplace_filtering):
    language._DETECTION._detected_lang = 'unknown'
    french = _ENGLISH_IDS + (
        '<node content-desc="Accueil" /><node content-desc="Profil" />'
        '<node content-desc="Abonnements" /><node text="J’aime" />'
    )
    assert language.redetect_if_unknown(_FakeDevice(french)) == 'fr'

    language._DETECTION._detected_lang = 'fr'
    english = _ENGLISH_IDS + '<node content-desc="Home" /><node content-desc="Followers" />'
    assert language.redetect_if_unknown(_FakeDevice(english)) == 'fr'
