"""TikTok language detection must never commit to the WRONG language.

TikTok carried the exact bug Instagram was fixed for on 2026-07-12, and carried it until
2026-07-31: probes were tested as substrings of the RAW XML, which always holds English
identifiers (`:id/home_tab`, `:id/profile_tab`, `:id/inbox_tab`, `:id/friends_tab`,
`:id/create_button`). English therefore collected one free point per probe on every dump,
language-independently.

Measured on a French dump whose only visible strings were "Abonnements" and "Abonnés":
`en (FR=0.5, EN=2.5)` — a French app declared English. That is worse than 'unknown':
committing STRIPS the French selectors, where 'unknown' keeps every locale (overlay union).

The screens are real captures, anonymized, on phones whose Android runs in French (so every dump
also carries the French system bar, "Accueil" and "Retour"): TikTok's update prompt, whose app
nodes carry no word at all, and a French comment sheet (43.1.4 and 47.0.3); the French and the
English app on 46.9.3 (Pixel 6a); and the post screen of an English 43.1.4 (Pixel 3a), whose
English words tie with the French ones of the system bar.
"""

from pathlib import Path

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


FIXTURES = Path(__file__).parent / "fixtures"


def _screen(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


#: TikTok's English ids and not one word of the app: the 43.1.4 update prompt.
_ENGLISH_IDS = _screen("tt4314_fr_update_prompt.xml")
#: A French screen scoring low: the 47.0.3 comment sheet, four French labels and no English one.
_FRENCH_FEW_WORDS = _screen("tt4703_fr_comment_sheet.xml")
_FRENCH = _screen("tt4693_fr_inbox.xml")
_ENGLISH = _screen("tt4693_en_for_you_video.xml")
_TIED = _screen("tt4314_publish_post_screen.xml")


def test_english_resource_ids_alone_never_decide_the_language():
    """The exact regression: this dump used to score EN=2.5 and win."""
    assert "com.zhiliaoapp.musically" in _ENGLISH_IDS
    assert language.detect_language(_FakeDevice(_ENGLISH_IDS)) == 'unknown'


def test_a_french_app_is_not_declared_english_by_its_resource_ids():
    """The dump that proved the bug: a few French words against the English identifiers."""
    assert language.detect_language(_FakeDevice(_FRENCH_FEW_WORDS)) != 'en'


def test_a_french_screen_is_detected_french():
    assert language.detect_language(_FakeDevice(_FRENCH)) == 'fr'


def test_an_english_screen_is_detected_english():
    assert language.detect_language(_FakeDevice(_ENGLISH)) == 'en'


def test_ambiguous_scores_stay_unknown():
    """A close call must not strip a locale."""
    assert 'content-desc="Accueil"' in _TIED and 'text="Post"' in _TIED
    assert language.detect_language(_FakeDevice(_TIED)) == 'unknown'


def test_redetection_only_happens_while_the_language_is_undecided(_no_inplace_filtering):
    language._DETECTION._detected_lang = 'unknown'
    assert language.redetect_if_unknown(_FakeDevice(_FRENCH)) == 'fr'

    language._DETECTION._detected_lang = 'fr'
    assert language.redetect_if_unknown(_FakeDevice(_ENGLISH)) == 'fr'
