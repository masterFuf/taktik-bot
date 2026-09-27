"""Language detection must never commit to the WRONG language.

Device bug (Instagram in FRENCH): detection returned
`en (FR=1.5, EN=2.5)`, stripped the French selectors, and `is_on_own_profile` then looked for
"Edit profile" on a screen showing "Modifier le profil" — the bot could never detect its own
account and every session aborted with "Cannot detect active Instagram account".

Two root causes, both covered here:
  1. probes were matched against the RAW XML, which always contains English resource-ids
     (profile_tab, search_tab, action_bar_button_back…) → English got a free, language-
     independent lead on every dump;
  2. no confidence margin → a 2.5-vs-1.5 coin flip was enough to strip a whole locale.
A wrong guess is worse than no guess: 'unknown' keeps every locale (overlay union).

The screens are real captures of Instagram 410.0.0.53.71, anonymized (Pixel 3 and Pixel 3a, whose
Android runs in French whatever the language of Instagram, so every dump also carries the French
system bar: "Accueil", "Retour"): own profiles in French and English, a reel in each language, a
French home feed, the English Explore grid, a story being watched, the story information window,
and a hashtag page of Instagram 447 in French (Pixel 6a).
"""

from pathlib import Path

import pytest

from taktik.core.social_media.instagram.ui import language


class _FakeDevice:
    def __init__(self, xml):
        self._xml = xml

    def get_xml_dump(self):
        return self._xml


@pytest.fixture(autouse=True)
def _reset_lang():
    """Leave the process exactly as found.

    Deciding a language is not a read-only act: `detect_and_optimize` sets the active locale
    AND filters the shared selector dataclasses IN PLACE. A test that lets a decision escape
    hands the next test an amputated catalogue — which is how this file first broke the post
    selector catalogs test, and only when the whole suite ran.
    """
    from taktik.core.social_media.instagram.ui.selectors.locales import (
        active_locale, set_active_locale,
    )
    before = active_locale()
    language._DETECTION._detected_lang = None
    yield
    language._DETECTION._detected_lang = None
    set_active_locale(before)


@pytest.fixture
def _no_inplace_filtering(monkeypatch):
    """Neutralise the destructive half of `detect_and_optimize` (see above)."""
    monkeypatch.setattr(language._DETECTION, 'optimize_selector_dataclass', lambda inst, lang: 0)


FIXTURES = Path(__file__).parent / "fixtures"


def _screen(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


#: Instagram's English ids and hardly a word: the story information window (24 strings, English).
_ENGLISH_IDS = _screen("ig410_en_story_share_information_window.xml")
_OWN_PROFILE_FR = _screen("ig410_fr_own_profile.xml")
_OWN_PROFILE_EN = _screen("ig410_en_own_profile.xml")
#: A story being watched: a few words, both languages scoring (the French ones are the system's).
_POOR_SCREEN = _screen("ig410_en_story_viewer.xml")
#: English Instagram under a French system bar: both languages match, too close to call.
_AMBIGUOUS = _screen("ig410_en_explore_grid.xml")
_REEL_FR = _screen("ig410_fr_reel_viewer.xml")
_REEL_EN = _screen("ig410_en_reel_viewer.xml")
_FEED_FR = _screen("ig410_fr_home_feed.xml")
#: Two French words and not one English: "Retour" (the system's) and "vidéo".
_TWO_WORDS = _screen("ig447_fr_hashtag_page.xml")


def test_english_resource_ids_alone_never_decide_the_language():
    """The exact regression: an English-id-only dump used to score EN=2.5 and win."""
    assert "com.instagram.android:id/" in _ENGLISH_IDS
    assert language.detect_language(_FakeDevice(_ENGLISH_IDS)) == 'unknown'


def test_french_app_with_english_resource_ids_is_detected_french():
    """A French nav bar must win despite the English ids sitting in the same dump."""
    assert 'text="Modifier le profil"' in _OWN_PROFILE_FR and "id/profile_tab" in _OWN_PROFILE_FR
    assert language.detect_language(_FakeDevice(_OWN_PROFILE_FR)) == 'fr'


def test_english_app_is_detected_english():
    assert 'text="Edit profile"' in _OWN_PROFILE_EN
    assert language.detect_language(_FakeDevice(_OWN_PROFILE_EN)) == 'en'


def test_a_poor_screen_stays_unknown_instead_of_guessing():
    """The screen the bot actually started on: barely any visible words → keep every locale."""
    assert language.detect_language(_FakeDevice(_POOR_SCREEN)) == 'unknown'


def test_ambiguous_scores_stay_unknown():
    """Close scores must not strip a locale (the 2.5-vs-1.5 coin flip)."""
    assert 'content-desc="Accueil"' in _AMBIGUOUS and 'content-desc="Home"' in _AMBIGUOUS
    assert language.detect_language(_FakeDevice(_AMBIGUOUS)) == 'unknown'


def test_unknown_keeps_all_selectors(monkeypatch):
    """'unknown' must not run the in-place filtering (that is what protects a bad detection)."""
    removed = []
    monkeypatch.setattr(language._DETECTION, 'optimize_selector_dataclass',
                        lambda inst, lang: removed.append(lang) or 0)
    lang = language.detect_and_optimize(_FakeDevice(_ENGLISH_IDS))
    assert lang == 'unknown'
    assert removed == []  # no locale was stripped


# ─────────────────────────────────────────────────────────────────────────────
# Run 714 (31/07): "Language detected: UNKNOWN" on an unmistakably French app.
#
# Detection scored five NAVIGATION probes (Accueil / Rechercher / Activité / Retour /
# Profil). Those words exist on the navigation bar and nowhere else, so any content
# screen scored 0.0 against 0.0 and detection gave up for the whole session — while the
# module carried a 113-word French vocabulary used only to classify our own selectors.
# ─────────────────────────────────────────────────────────────────────────────


def test_a_reel_screen_is_enough_to_decide_the_language():
    """No navigation bar on a reel — the five nav probes scored 0.0 against 0.0 there."""
    assert language.detect_language(_FakeDevice(_REEL_FR)) == 'fr'
    assert language.detect_language(_FakeDevice(_REEL_EN)) == 'en'


def test_a_feed_decides_even_when_the_tabs_carry_no_label():
    """The tab bar is not always labelled; the rest of the screen still says the language."""
    assert language.detect_language(_FakeDevice(_FEED_FR)) == 'fr'


def test_a_single_stray_word_still_decides_nothing():
    """More vocabulary must not mean a lower bar: a word or two is not a language."""
    assert language.detect_language(_FakeDevice(_TWO_WORDS)) == 'unknown'


def test_a_french_screen_carrying_one_english_word_is_still_french():
    """The ratio margin tolerates a stray loser match instead of falling back to unknown."""
    assert 'content-desc="Reels"' in _REEL_FR
    assert language.detect_language(_FakeDevice(_REEL_FR)) == 'fr'


def test_redetection_only_happens_while_the_language_is_undecided(_no_inplace_filtering):
    """Detection runs at startup on whatever screen the app opened on. This is the second
    chance the log promised and nothing ever performed — but a decided language must never
    be re-opened: a later screen could only turn a good answer into a worse one."""
    language._DETECTION._detected_lang = 'unknown'
    assert language.redetect_if_unknown(_FakeDevice(_REEL_FR)) == 'fr'

    # already decided -> the new dump is not even read
    language._DETECTION._detected_lang = 'fr'
    assert language.redetect_if_unknown(_FakeDevice(_REEL_EN)) == 'fr'


def test_the_undecided_log_names_what_it_saw():
    """An undecided detection is only actionable if the next reader can tell "empty screen"
    from "scores too close" — run 714 printed a score and nothing else."""
    from loguru import logger

    messages = []
    sink = logger.add(lambda msg: messages.append(str(msg)), level="INFO")
    try:
        language.detect_language(_FakeDevice(_ENGLISH_IDS))
    finally:
        logger.remove(sink)

    undecided = [m for m in messages if 'undecided' in m]
    assert undecided, messages
    assert 'visible strings' in undecided[0]
    assert 'FR matched nothing' in undecided[0]
