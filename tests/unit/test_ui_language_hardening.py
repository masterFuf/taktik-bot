"""Reading UI text must not depend on the phone's language — nor on an apostrophe shape.

Three runs in a row were lost to the same silent failure: an element found by a
language-neutral resource-id, then rejected because the WORD next to it was compared to a
hardcoded English string. Nothing raises in that situation — "I could not recognise it"
and "there is nothing there" produce the same empty result — so these are the locks.

The strings below are copied from real UI dumps (Instagram 410.0.0.53.71 and TikTok 43.1.4,
French phone), including their TYPOGRAPHIC apostrophe (U+2019), which is what the apps
actually render.
"""

import re
import xml.etree.ElementTree as ET

import pytest

from taktik.core.shared.text import normalize_ui_label
from taktik.core.social_media.instagram.ui.selectors import locales as ig_locales
from taktik.core.social_media.instagram.ui.selectors.locales import fr as ig_fr, en as ig_en
from taktik.core.social_media.tiktok.ui.selectors import locales as tt_locales
from taktik.core.social_media.tiktok.ui.selectors.locales import fr as tt_fr, en as tt_en
from taktik.core.social_media.tiktok.ui.labels import (
    classify_profile_stat_label,
    is_friends_button,
)
from taktik.core.social_media.instagram.ui.labels import (
    classify_action_button as _classify_action_button,
)
from taktik.core.social_media.instagram.workflows.management.notifications.dump_parsing import (
    find_inline_like_target,
)
from taktik.core.social_media.instagram.workflows.management.dm.dm_navigation import (
    DMNavigationMixin,
)

CURLY = "’"
STRAIGHT = "'"
IN_WORD_STRAIGHT = re.compile(r"[A-Za-zÀ-ÿ]'[A-Za-zÀ-ÿ]")
IN_WORD_CURLY = re.compile(r"[A-Za-zÀ-ÿ]’[A-Za-zÀ-ÿ]")

LOCALE_MODULES = [
    pytest.param(ig_fr, id="instagram/fr"),
    pytest.param(ig_en, id="instagram/en"),
    pytest.param(tt_fr, id="tiktok/fr"),
    pytest.param(tt_en, id="tiktok/en"),
]


@pytest.fixture(autouse=True)
def _union_locale():
    """Run in UNION mode, and leave the process as it was found.

    The active locale is a module global. Another test file setting it to "en" made these
    assertions fail only when the whole suite ran — and union is the mode that matters
    here: on Kevin's phone `detect_and_optimize` reports "Language unknown", so every
    language's labels are tried at once. A classifier must stay correct in that mode.
    """
    ig_before, tt_before = ig_locales.active_locale(), tt_locales.active_locale()
    ig_locales.set_active_locale(None)
    tt_locales.set_active_locale(None)
    yield
    ig_locales.set_active_locale(ig_before)
    tt_locales.set_active_locale(tt_before)


def _xpaths(module):
    for key, values in module.STRINGS.items():
        for value in values:
            if isinstance(value, str) and value.lstrip().startswith(("//", "(//", "./")):
                yield key, value


# --------------------------------------------------------------------------- apostrophes

@pytest.mark.parametrize("module", LOCALE_MODULES)
def test_no_selector_hinges_on_a_single_apostrophe_shape(module):
    """The apps render U+2019 ("J’aime"); catalogues get typed with the ASCII one. A
    selector naming only one of the two matches NOTHING — silently, which is how the FR
    like-count selector returned "found 0 elements" with the label on screen."""
    for key, value in _xpaths(module):
        has_straight = bool(IN_WORD_STRAIGHT.search(value))
        has_curly = bool(IN_WORD_CURLY.search(value))
        assert has_straight == has_curly, f"{key}: {value}"


@pytest.mark.parametrize("module", LOCALE_MODULES)
def test_every_selector_is_valid_xpath(module):
    """`//x[@text='J'aime']` is not valid XPath — the apostrophe closes the literal early.
    uiautomator2 swallows the parse error, so the selector is dead for good."""
    etree = pytest.importorskip("lxml.etree")
    for key, value in _xpaths(module):
        try:
            etree.XPath(value)
        except Exception as exc:                                   # pragma: no cover
            pytest.fail(f"{key}: {value}\n  {exc}")


@pytest.mark.parametrize("raw,expected", [
    ("J" + CURLY + "aime", "j'aime"),
    ("  S" + CURLY + "ABONNER  ", "s'abonner"),
    ("Don" + CURLY + "t allow", "don't allow"),
    (None, ""),
])
def test_normalize_folds_every_apostrophe_shape(raw, expected):
    assert normalize_ui_label(raw) == expected


# ------------------------------------------------------------------- TikTok stat labels

@pytest.mark.parametrize("label,expected", [
    ("Following", "following"),
    ("Followers", "followers"),
    ("Likes", "likes"),
    ("Abonnements", "following"),
    ("Abonnés", "followers"),
    ("J" + CURLY + "aime", "likes"),
    ("J'aime", "likes"),
    ("", None),
])
def test_tiktok_profile_stats_are_named_in_both_languages(label, expected):
    """The stat row is paired by position (resource-ids), but WHICH value you hold is in
    the label. Comparing it to English words made all three counts zero on a French phone."""
    assert classify_profile_stat_label(label) == expected


def test_following_is_tested_before_followers():
    """"Following" contains "Follow"; reversing the order misreports the following count."""
    assert classify_profile_stat_label("Following") == "following"
    assert classify_profile_stat_label("Followers") == "followers"


@pytest.mark.parametrize("locale,label", [
    ("fr", "Abonnés"),
    ("en", "Followers"),
])
def test_each_locale_resolves_its_own_label_once_the_language_is_known(locale, label):
    """Union mode is the fallback, not the target: when detection succeeds, `L(...)` narrows
    to that language and the classification must still hold."""
    tt_locales.set_active_locale(locale)
    assert classify_profile_stat_label(label) == "followers"


@pytest.mark.parametrize("text,expected", [
    ("Friends", True), ("Amis", True), ("Abonné", False), ("", False),
])
def test_mutual_follow_button_is_recognised_in_both_languages(text, expected):
    assert is_friends_button(text) is expected


# --------------------------------------------------------- Instagram post action buttons

@pytest.mark.parametrize("desc,expected", [
    ("Like", "like"),
    ("J" + CURLY + "aime", "like"),
    ("Comment", "comment"),
    ("Commentaire", "comment"),
    ("Send", "share"),
    ("Envoyer la publication", "share"),
    ("Save", "save"),
    ("Ajouter aux enregistrements", "save"),
    ("", None),
])
def test_post_action_buttons_are_named_in_both_languages(desc, expected):
    assert _classify_action_button(desc) == expected


def test_the_unliked_state_is_never_read_as_a_like_button():
    """"Je n’aime plus" must not be classified as the like button — that button sits next
    to the counter we then attribute, so a mismatch reports the wrong number."""
    assert _classify_action_button("Je" + CURLY + "n" + CURLY + "aime plus") is None


# ----------------------------------------------------------------- notifications row like

def _row_with(content_desc):
    return ET.fromstring(
        '<hierarchy><node resource-id="com.instagram.android:id/row" '
        'bounds="[0,100][1080,300]" text="alice a commente">'
        f'<node content-desc="{content_desc}" bounds="[900,150][1000,250]"/>'
        '</node></hierarchy>'
    )


def test_inline_like_is_found_despite_the_apostrophe_shape():
    """The catalogue says "Bouton J'aime", the device says "Bouton J’aime". A raw exact
    match found nothing — and "no control on this row" is a legitimate outcome, so the
    failure never surfaced."""
    root = _row_with("Bouton J" + CURLY + "aime")
    assert find_inline_like_target(root, "row", ["Bouton J'aime"], "alice") == (950, 200)


def test_the_already_liked_row_is_still_not_matched():
    """Normalising must not blur "Bouton J'aime" into "Bouton Je n'aime plus" — matching
    the second would UNLIKE the comment."""
    root = _row_with("Bouton Je" + CURLY + "n" + CURLY + "aime plus")
    assert find_inline_like_target(root, "row", ["Bouton J'aime"], "alice") is None


# ------------------------------------------------------------------------- DM presence

@pytest.mark.parametrize("value,is_status", [
    ("Active now", True),
    ("En ligne", True),
    ("Actif il y a 2 h", True),
    ("alice.dupont", False),
    ("", False),
])
def test_presence_status_is_not_taken_for_a_username(value, is_status):
    """A thread row opens on the contact's STATUS when they are online. The guard only knew
    the English form, so a French inbox returned "En ligne" as the conversation name."""
    navigator = DMNavigationMixin.__new__(DMNavigationMixin)
    assert navigator._is_presence_status(value) is is_status
