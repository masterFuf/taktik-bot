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
"""

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
    language._detected_lang = None
    yield
    language._detected_lang = None
    set_active_locale(before)


@pytest.fixture
def _no_inplace_filtering(monkeypatch):
    """Neutralise the destructive half of `detect_and_optimize` (see above)."""
    monkeypatch.setattr(language, 'optimize_selector_dataclass', lambda inst, lang: 0)


# The English resource-ids that are present on EVERY Instagram dump, whatever the app language.
_ENGLISH_IDS = (
    '<node resource-id="com.instagram.android:id/profile_tab" />'
    '<node resource-id="com.instagram.android:id/search_tab" />'
    '<node resource-id="com.instagram.android:id/feed_tab" />'
    '<node resource-id="com.instagram.android:id/action_bar_button_back" />'
    '<node resource-id="com.instagram.android:id/activity_feed" />'
)


def test_english_resource_ids_alone_never_decide_the_language():
    """The exact regression: an English-id-only dump used to score EN=2.5 and win."""
    assert language.detect_language(_FakeDevice(_ENGLISH_IDS)) == 'unknown'


def test_french_app_with_english_resource_ids_is_detected_french():
    """A French nav bar must win despite the English ids sitting in the same dump."""
    xml = _ENGLISH_IDS + (
        '<node content-desc="Accueil" />'
        '<node content-desc="Rechercher et explorer" />'
        '<node content-desc="Profil" />'
        '<node text="Modifier le profil" />'
    )
    assert language.detect_language(_FakeDevice(xml)) == 'fr'


def test_english_app_is_detected_english():
    xml = _ENGLISH_IDS + (
        '<node content-desc="Home" />'
        '<node content-desc="Search" />'
        '<node content-desc="Profile" />'
        '<node text="Edit profile" />'
    )
    assert language.detect_language(_FakeDevice(xml)) == 'en'


def test_a_poor_screen_stays_unknown_instead_of_guessing():
    """The screen the bot actually started on: barely any visible words → keep every locale."""
    xml = _ENGLISH_IDS + '<node text="15:31" /><node content-desc="Les plus récents" />'
    assert language.detect_language(_FakeDevice(xml)) == 'unknown'


def test_ambiguous_scores_stay_unknown():
    """Close scores must not strip a locale (the 2.5-vs-1.5 coin flip)."""
    xml = '<node content-desc="Accueil" /><node content-desc="Home" />'
    assert language.detect_language(_FakeDevice(xml)) == 'unknown'


def test_unknown_keeps_all_selectors(monkeypatch):
    """'unknown' must not run the in-place filtering (that is what protects a bad detection)."""
    removed = []
    monkeypatch.setattr(language, 'optimize_selector_dataclass',
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

# Verbatim from the reel dumps of 31/07 (Instagram 410.0.0.53.71, French phone).
_REEL_FR = (
    '<node content-desc="Reel de dolce_cocoon. Appuyez deux fois pour lire ou mettre en pause." />'
    '<node content-desc="Nombre de J’aime : 14. Voir les J’aime" />'
    '<node content-desc="Nombre de commentaires : 6. Voir les commentaires" />'
    '<node content-desc="Envoyer" /><node text="Plus" /><node text="Audio original" />'
    '<node text="Suivre" />'
)

_REEL_EN = (
    '<node content-desc="Reel by john_doe. Double-tap to play or pause." />'
    '<node content-desc="Like number is14. View likes" />'
    '<node content-desc="Comment number is 6. View comments" />'
    '<node content-desc="Send" /><node text="More" /><node text="Original audio" />'
    '<node text="Follow" />'
)


def test_a_reel_screen_is_enough_to_decide_the_language():
    """No navigation bar on a reel — the five nav probes scored 0.0 against 0.0 there."""
    assert language.detect_language(_FakeDevice(_ENGLISH_IDS + _REEL_FR)) == 'fr'
    assert language.detect_language(_FakeDevice(_ENGLISH_IDS + _REEL_EN)) == 'en'


def test_a_feed_decides_even_when_the_tabs_carry_no_label():
    """The tab bar is not always labelled; the rest of the screen still says the language."""
    xml = _ENGLISH_IDS + (
        '<node content-desc="Ajouter à la story" /><node content-desc="Votre story" />'
        '<node content-desc="J’aime" /><node content-desc="Commenter" />'
        '<node content-desc="Envoyer" /><node content-desc="Ajouter aux enregistrements" />'
    )
    assert language.detect_language(_FakeDevice(xml)) == 'fr'


def test_a_single_stray_word_still_decides_nothing():
    """More vocabulary must not mean a lower bar: one word is not a language."""
    xml = _ENGLISH_IDS + '<node content-desc="Envoyer" />'
    assert language.detect_language(_FakeDevice(xml)) == 'unknown'


def test_a_french_screen_carrying_one_english_word_is_still_french():
    """The ratio margin tolerates a stray loser match instead of falling back to unknown."""
    xml = _ENGLISH_IDS + _REEL_FR + '<node text="Reels" /><node content-desc="Follow" />'
    assert language.detect_language(_FakeDevice(xml)) == 'fr'


def test_redetection_only_happens_while_the_language_is_undecided(_no_inplace_filtering):
    """Detection runs at startup on whatever screen the app opened on. This is the second
    chance the log promised and nothing ever performed — but a decided language must never
    be re-opened: a later screen could only turn a good answer into a worse one."""
    language._detected_lang = 'unknown'
    assert language.redetect_if_unknown(_FakeDevice(_ENGLISH_IDS + _REEL_FR)) == 'fr'

    # already decided -> the new dump is not even read
    language._detected_lang = 'fr'
    assert language.redetect_if_unknown(_FakeDevice(_ENGLISH_IDS + _REEL_EN)) == 'fr'


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
