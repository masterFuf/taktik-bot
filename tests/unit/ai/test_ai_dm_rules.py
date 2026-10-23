"""The one rule of a DM written by an AI (`taktik/core/ai/dm_rules.py`): each reason, and what passes."""

from __future__ import annotations

import pytest

from taktik.core.ai.dm_rules import (
    AiDmRules,
    AiDmTextRefused,
    ai_dm_rules_from_payload,
    check_ai_dm_text,
    check_ai_dm_texts,
    refuse_ai_dm_texts,
)
from taktik.core.contract.ai_dm import AI_DM_REFUSAL_REASON
from unit.ai_dm_texts import BROKEN_TEXTS, EACH_REASON, FRENCH_ACCOUNT, WITHIN_RULES

FRENCH = AiDmRules(base_language="fr")
GOOD = WITHIN_RULES


@pytest.mark.parametrize("reason, text", [
    *EACH_REASON,
    pytest.param("link", "Bonjour, tout est sur https://exemple.com/offre pour toi", id="full_link"),
    pytest.param("forbidden_term", "Bonjour, c'est GRATUIT pour toi pendant un mois entier", id="term_case"),
    pytest.param("forbidden_term", "Bonjour, la gratuité dure un mois entier pour toi", id="term_accents_and_start"),
])
def test_each_rule_refuses_with_its_reason(reason, text):
    rules = ai_dm_rules_from_payload(FRENCH_ACCOUNT)

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
    assert refusal.as_line() == {"reason": "too_long", "detail": "612 characters, 500 at most", "index": 2,
                                 "measure": 612, "limit": 500}
    assert refusal.describe() == "message 2: 612 characters, 500 at most"
    assert str(refused.value) == "Text refused: message 2: 612 characters, 500 at most"


# --- the measure, typed (the English `detail` is for a model; a screen says the rule from these) ---------


def test_a_text_too_short_or_too_long_says_what_was_measured_and_the_bound_it_broke_as_numbers():
    short = check_ai_dm_text("   Merci beaucoup !   ", FRENCH)
    long = check_ai_dm_text("Bonjour " + "a" * 604, FRENCH)

    assert (short.reason, short.measure, short.limit, short.term) == ("too_short", 16, 20, None)
    assert (long.reason, long.measure, long.limit, long.term) == ("too_long", 612, 500, None)


def test_a_forbidden_term_is_said_as_the_account_declared_it():
    rules = AiDmRules(base_language="fr", forbidden_terms=("gratuit",))

    refusal = check_ai_dm_text("Bonjour, la gratuité dure un mois entier pour toi", rules)

    assert (refusal.reason, refusal.term, refusal.measure, refusal.limit) == ("forbidden_term", "gratuit", None, None)


@pytest.mark.parametrize("reason", ["language", "link", "email", "phone"])
def test_a_rule_with_nothing_to_count_carries_no_measure(reason):
    refusal = check_ai_dm_text(BROKEN_TEXTS[reason], ai_dm_rules_from_payload(FRENCH_ACCOUNT))

    assert refusal.reason == reason
    assert (refusal.measure, refusal.limit, refusal.term) == (None, None, None)
    assert set(refusal.as_line()) == {"reason", "detail"}


def test_a_list_keeps_the_measure_of_each_refused_text_beside_its_rank():
    refusals = check_ai_dm_texts([GOOD, "Bonjour " + "a" * 604, "Salut !"], FRENCH)

    assert [(r.index, r.reason, r.measure, r.limit) for r in refusals] == [
        (2, "too_long", 612, 500),
        (3, "too_short", 7, 20),
    ]
    assert refusals[0].as_line() == {"reason": "too_long", "detail": "612 characters, 500 at most", "index": 2,
                                     "measure": 612, "limit": 500}


def test_a_term_found_in_a_list_is_kept_with_its_rank():
    rules = AiDmRules(base_language="fr", forbidden_terms=("promo",))

    with pytest.raises(AiDmTextRefused) as refused:
        refuse_ai_dm_texts([GOOD, "Bonjour Léa, une promo pour toi pendant un mois entier"], rules)

    assert refused.value.refusal.as_line() == {"reason": "forbidden_term", "detail": 'contains the forbidden term "promo"',
                                               "index": 2, "term": "promo"}


def test_the_measure_in_the_english_detail_is_the_typed_one():
    for text in ("Merci !", "Bonjour " + "a" * 604):
        refusal = check_ai_dm_text(text, FRENCH)

        assert refusal.detail.startswith(f"{refusal.measure} characters, {refusal.limit} ")


ENGLISH_REPLY = "Thanks a lot Lea, your bakery looks amazing, could we talk about it soon?"
ENGLISH_RECEIVED = "Hello, thank you for your message, I would love to hear more about what you do."
FRENCH_RECEIVED = "Bonjour, merci pour ton message, je serais ravie d'en savoir plus sur ce que tu fais."


def test_a_reply_may_be_in_the_language_of_the_message_it_answers():
    assert check_ai_dm_text(ENGLISH_REPLY, FRENCH, received_text=ENGLISH_RECEIVED) is None


def test_a_reply_may_still_be_in_the_account_language():
    assert check_ai_dm_text(GOOD, FRENCH, received_text=ENGLISH_RECEIVED) is None


def test_the_same_reply_to_a_french_message_is_refused():
    refusal = check_ai_dm_text(ENGLISH_REPLY, FRENCH, received_text=FRENCH_RECEIVED)

    assert refusal is not None and refusal.reason == "language"


def test_a_cold_dm_stays_in_the_account_language():
    # No received text: a cold DM and a welcome DM answer nobody.
    refusal = check_ai_dm_text(ENGLISH_REPLY, FRENCH)

    assert refusal is not None and refusal.reason == "language"


def test_a_received_message_too_short_to_be_recognised_allows_the_account_language_only():
    assert check_ai_dm_text(GOOD, FRENCH, received_text="ok") is None
    refusal = check_ai_dm_text(ENGLISH_REPLY, FRENCH, received_text="ok")

    assert refusal is not None and refusal.reason == "language"


def test_a_received_message_in_another_language_than_the_reply_lets_that_language_through_only():
    german = "Hallo, vielen Dank für deine Nachricht, ich würde gerne mehr darüber erfahren."

    refusal = check_ai_dm_text(ENGLISH_REPLY, FRENCH, received_text=german)

    assert refusal is not None and refusal.reason == "language"
