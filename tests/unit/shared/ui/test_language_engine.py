"""The shared language engine — the scoring and classification both platforms rely on.

These rules used to be duplicated per platform, and the duplication is exactly what let
them drift. They are asserted once, here, on the owner.
"""

import pytest

from taktik.core.shared.ui import language_engine as engine


# ──────────────────────────────────────────────────────────────
# Scoring
# ──────────────────────────────────────────────────────────────

def test_a_word_does_not_score_inside_a_longer_word_of_another_language():
    """Whole-word matching, in both directions.

    The substring test this replaces scored FR "Profil" inside EN "Profile", and inside
    the `profile_tab` identifier as well — enough to declare a French phone English.
    """
    values = ["Profile", "Edit profile"]
    assert engine.score_patterns(engine.compile_vocabulary(["Profil"]), values)[0] == 0.0
    assert engine.score_patterns(engine.compile_vocabulary(["Profile"]), values)[0] == 1.0


def test_an_exact_value_outweighs_a_word_found_inside_a_sentence():
    patterns = engine.compile_vocabulary(["Abonnements"])
    assert engine.score_patterns(patterns, ["Abonnements"])[0] == 1.0
    assert engine.score_patterns(patterns, ["12 Abonnements au total"])[0] == 0.5


def test_the_matched_words_are_reported_so_an_undecided_run_can_explain_itself():
    _, matched = engine.score_patterns(engine.compile_vocabulary(["Accueil", "Profil"]),
                                       ["Accueil"])
    assert matched == ["Accueil"]


def test_only_visible_text_is_scored_never_the_resource_ids():
    """A dump always carries English identifiers, whatever language the app runs in."""
    xml = ('<node resource-id="com.app:id/profile_tab" class="android.widget.Button" '
           'content-desc="Profil" />')
    assert engine.visible_strings(xml) == ["Profil"]


# ──────────────────────────────────────────────────────────────
# Decision
# ──────────────────────────────────────────────────────────────

_FR = engine.compile_vocabulary(["Accueil", "Profil", "Abonnements", "Abonnés"])
_EN = engine.compile_vocabulary(["Home", "Profile", "Following", "Followers"])


def _dump(*values):
    return "".join(f'<node content-desc="{v}" />' for v in values)


def test_a_clear_winner_is_committed_to():
    assert engine.decide(_dump("Accueil", "Profil", "Abonnements", "Abonnés"),
                         _FR, _EN, min_score=3.0, min_ratio=2.0).language == "fr"
    assert engine.decide(_dump("Home", "Profile", "Following", "Followers"),
                         _FR, _EN, min_score=3.0, min_ratio=2.0).language == "en"


def test_a_close_call_stays_undecided_rather_than_stripping_the_wrong_locale():
    """A wrong language removes the selectors that would have worked; undecided keeps all."""
    decision = engine.decide(_dump("Accueil", "Home", "Profil", "Profile"),
                             _FR, _EN, min_score=3.0, min_ratio=2.0)
    assert decision.language == "unknown"


def test_a_high_but_unconvincing_lead_stays_undecided():
    """Above the floor, but the ratio is what settles it."""
    decision = engine.decide(_dump("Accueil", "Profil", "Abonnements", "Home", "Profile"),
                             _FR, _EN, min_score=3.0, min_ratio=2.0)
    assert decision.fr_score >= 3.0
    assert decision.language == "unknown"


def test_an_empty_screen_is_undecided_and_says_how_many_strings_it_saw():
    decision = engine.decide("", _FR, _EN, min_score=3.0, min_ratio=2.0)
    assert decision.language == "unknown"
    assert decision.values_seen == 0


# ──────────────────────────────────────────────────────────────
# Selector classification
# ──────────────────────────────────────────────────────────────

_FR_WORDS = {"Abonnés", "S'abonner", "Suivi"}
_EN_WORDS = {"Followers", "Follow", "Following"}


def _classify(xpath):
    return engine.classify_selector(xpath, _FR_WORDS, _EN_WORDS)


def test_a_selector_without_any_text_is_never_filtered():
    assert _classify('//*[@resource-id="com.app:id/row_button"]') == "neutral"
    assert _classify('//android.widget.Button[2]') == "neutral"


def test_a_localized_selector_is_attributed_to_its_language():
    assert _classify('//*[@text="Abonnés"]') == "fr"
    assert _classify('//*[@content-desc="Followers"]') == "en"


def test_a_selector_holding_both_languages_stays_neutral():
    """Keeping it costs a useless lookup; dropping it breaks the screen."""
    assert _classify('//*[@text="Abonnés" or @text="Followers"]') == "neutral"


def test_the_longest_match_settles_a_substring_collision():
    """FR "Suivi" is contained in EN "Following"'s translation neighbourhood."""
    assert _classify('//*[@text="Following"]') == "en"
    assert _classify('//*[@text="Suivi"]') == "fr"


def test_an_escaped_apostrophe_is_normalised_before_matching():
    assert _classify("""//*[@text="S\\'abonner"]""") == "fr"


def test_the_contains_form_is_read_like_the_equality_form():
    assert _classify('//*[contains(@content-desc, "Followers")]') == "en"


# ──────────────────────────────────────────────────────────────
# Filtering
# ──────────────────────────────────────────────────────────────

_SELECTORS = ['//*[@text="Abonnés"]', '//*[@text="Followers"]',
              '//*[@resource-id="com.app:id/row"]']


def test_filtering_drops_the_other_language_and_keeps_the_neutral_ones():
    assert engine.filter_selectors(_SELECTORS, "fr", _FR_WORDS, _EN_WORDS) == [
        '//*[@text="Abonnés"]', '//*[@resource-id="com.app:id/row"]']


@pytest.mark.parametrize("lang", ["unknown", ""])
def test_an_undecided_language_keeps_every_selector(lang):
    assert engine.filter_selectors(_SELECTORS, lang, _FR_WORDS, _EN_WORDS) == _SELECTORS


# ──────────────────────────────────────────────────────────────
# Dataclass optimization
# ──────────────────────────────────────────────────────────────

def test_only_the_list_fields_of_a_dataclass_are_filtered():
    from dataclasses import dataclass, field

    @dataclass
    class _Surface:
        rows: list = field(default_factory=lambda: list(_SELECTORS))
        label: str = "Abonnés"

        @property
        def everything(self):
            return self.rows

    surface = _Surface()
    removed = engine.optimize_selector_dataclass(surface, "fr", _FR_WORDS, _EN_WORDS)

    assert removed == 1
    assert surface.rows == ['//*[@text="Abonnés"]', '//*[@resource-id="com.app:id/row"]']
    assert surface.label == "Abonnés"
    # The property recomputes from the list this pass already filtered.
    assert surface.everything == surface.rows


def test_an_undecided_language_leaves_the_dataclass_untouched():
    from dataclasses import dataclass, field

    @dataclass
    class _Surface:
        rows: list = field(default_factory=lambda: list(_SELECTORS))

    surface = _Surface()
    assert engine.optimize_selector_dataclass(surface, "unknown", _FR_WORDS, _EN_WORDS) == 0
    assert surface.rows == _SELECTORS


# ──────────────────────────────────────────────────────────────
# Dump reading
# ──────────────────────────────────────────────────────────────

def test_the_dump_is_read_whatever_shape_the_device_object_has():
    class _Wrapper:
        def get_xml_dump(self):
            return "<hierarchy/>"

    class _Raw:
        def dump_hierarchy(self):
            return "<raw/>"

    class _Nested:
        device = _Raw()

    assert engine.read_dump(_Wrapper()) == "<hierarchy/>"
    assert engine.read_dump(_Raw()) == "<raw/>"
    assert engine.read_dump(_Nested()) == "<raw/>"
    assert engine.read_dump(object()) is None
