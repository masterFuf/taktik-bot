"""The one rule of a DM written by an AI (`taktik/core/ai/dm_rules.py`): each reason, and what passes."""

from __future__ import annotations

import pytest

from taktik.core.ai.dm_rules import (
    AiDmRules,
    AiDmTextRefused,
    ai_dm_rules_from_payload,
    check_ai_dm_text,
    refuse_ai_dm_texts,
)
from taktik.core.contract.ai_dm import AI_DM_REFUSAL_REASON

FRENCH = AiDmRules(base_language="fr")
GOOD = "Bonjour Léa, ta boulangerie a l'air superbe, on en parle ?"


@pytest.mark.parametrize("text, reason", [
    pytest.param("Salut, ça va ?", "too_short", id="too_short"),
    pytest.param("Bonjour " + "a" * 500, "too_long", id="too_long"),
    pytest.param("Hello Lea, your bakery looks amazing, could we talk about it?", "language", id="language"),
    pytest.param("Bonjour, va voir maboutique.fr pour la suite, merci", "link", id="bare_domain"),
    pytest.param("Bonjour, tout est sur https://exemple.com/offre pour toi", "link", id="full_link"),
    pytest.param("Bonjour, écris-moi sur lea@exemple.fr pour en parler", "email", id="email"),
    pytest.param("Bonjour, appelle-moi au 06 12 34 56 78 quand tu veux", "phone", id="phone"),
    pytest.param("Bonjour, c'est GRATUIT pour toi pendant un mois entier", "forbidden_term", id="forbidden_term"),
    pytest.param("Bonjour, la gratuité dure un mois entier pour toi", "forbidden_term", id="term_accents_and_start"),
])
def test_each_rule_refuses_with_its_reason(text, reason):
    rules = AiDmRules(base_language="fr", forbidden_terms=("gratuit",))

    refusal = check_ai_dm_text(text, rules)

    assert refusal is not None and refusal.reason == reason
    assert refusal.reason in AI_DM_REFUSAL_REASON.values


def test_a_text_within_the_rules_passes():
    assert check_ai_dm_text(GOOD, FRENCH) is None


def test_the_length_is_measured_without_surrounding_spaces():
    refusal = check_ai_dm_text("   Merci beaucoup !   ", FRENCH)

    assert refusal.reason == "too_short" and refusal.detail == "16 characters, 20 at least"


def test_a_frame_that_allows_links_lets_links_email_and_phone_through():
    rules = AiDmRules(base_language="fr", links_allowed=True)

    for text in ("Bonjour, va voir maboutique.fr pour la suite, merci",
                 "Bonjour, écris-moi sur lea@exemple.fr pour en parler",
                 "Bonjour, appelle-moi au 06 12 34 56 78 quand tu veux"):
        assert check_ai_dm_text(text, rules) is None


def test_a_term_inside_a_word_is_not_a_forbidden_term():
    # "art" starts no word of this text; "partir" and "départ" hold it only inside.
    rules = AiDmRules(base_language="fr", forbidden_terms=("art",))

    assert check_ai_dm_text("Bonjour, je vais partir, c'est le départ pour toi aussi", rules) is None


def test_a_sentence_glued_to_the_next_is_not_a_link():
    assert check_ai_dm_text("Bonjour et merci.Bonne journée à toi et à toute ton équipe", FRENCH) is None


def test_a_text_too_short_to_be_recognised_passes_the_language_rule():
    # Two words of no language the detector knows: it cannot tell, the rule does not guess.
    assert check_ai_dm_text("Ciao Marco!!! 🙂 🙂 🙂 🙂 🙂 🙂", AiDmRules(base_language="de")) is None


def test_an_account_of_unknown_language_writes_french_or_english_only():
    unknown = AiDmRules()

    assert check_ai_dm_text(GOOD, unknown) is None
    assert check_ai_dm_text("Hello Lea, your bakery looks amazing, could we talk about it?", unknown) is None
    refusal = check_ai_dm_text("Hola Lea, tu panadería es muy bonita, ¿hablamos un día de esto?", unknown)
    assert refusal.reason == "language" and refusal.detail == "written in es, the account writes in fr or en"


def test_the_block_of_the_payload_gives_the_frame_and_the_account_language():
    rules = ai_dm_rules_from_payload({
        "linksAllowed": True,
        "forbiddenTerms": ["promo", "  "],
        "accountProfile": {"language": "English"},
    })

    assert rules == AiDmRules(base_language="en", links_allowed=True, forbidden_terms=("promo",))


def test_the_account_language_falls_back_on_the_language_of_its_persona():
    rules = ai_dm_rules_from_payload({"accountProfile": {"niche": "Coaching pour les instituts de beauté",
                                                         "targetAudience": "les gérantes et leurs équipes"}})

    assert rules.base_language == "fr"


def test_an_absent_block_is_the_most_prudent():
    assert ai_dm_rules_from_payload(None) == AiDmRules(base_language=None, links_allowed=False, forbidden_terms=())


@pytest.mark.parametrize("block", [["promo"], {"forbiddenTerms": "promo"}, {"forbiddenTerms": [3]}])
def test_an_unreadable_block_is_refused(block):
    with pytest.raises(ValueError):
        ai_dm_rules_from_payload(block)


def test_a_list_given_up_front_is_refused_on_its_first_broken_text_with_its_rank():
    with pytest.raises(AiDmTextRefused) as refused:
        refuse_ai_dm_texts([GOOD, "Bonjour " + "a" * 604], FRENCH)

    refusal = refused.value.refusal
    assert refusal.as_line() == {"reason": "too_long", "detail": "612 characters, 500 at most", "index": 2}
    assert refusal.describe() == "message 2: 612 characters, 500 at most"
    assert str(refused.value) == "Text refused: message 2: 612 characters, 500 at most"
