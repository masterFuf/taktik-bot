"""A comment or a reply written in another language than the one asked is refused, never published.

The audit of October 2026: five comments out of five that October asked in English ("Write in
English", in the stored prompt of each) came back French, and were published. The generator read
the model's answer for its JSON, its anchor and its agreements, never for its language. The texts
are the rewritten outputs of `unit.ai_written_texts`; the model is stubbed, nothing is called.
"""

from __future__ import annotations

import json

import pytest

from taktik.core.ai.providers.openrouter import AIService
from unit.ai_written_texts import FRENCH_SUMMARIES_WITH_IDEOGRAPHS, FRENCH_WHERE_ENGLISH_WAS_ASKED

CAPTION = "Golden hour over the harbour, shot on film last weekend"


def _service(answer: dict) -> AIService:
    svc = object.__new__(AIService)
    svc.ipc = None
    svc.model_generation = "test/model-generation"
    svc.text_completion = lambda *a, **k: {
        "success": True, "text": json.dumps(answer, ensure_ascii=False), "model": "m", "cost_usd": 0.0,
    }
    return svc


def _comment_answer(comment: str) -> dict:
    return {"anchor": "Golden hour", "reasoning": "the light", "comment": comment,
            "safe_comment": comment}


@pytest.mark.parametrize("comment", FRENCH_WHERE_ENGLISH_WAS_ASKED)
def test_a_french_comment_where_english_was_asked_is_refused(comment):
    out = _service(_comment_answer(comment)).generate_smart_comment(
        post_description="", username="someone", language="en", post_caption=CAPTION,
    )

    assert out["success"] is True
    assert out["comment"] == "" and out["should_comment"] is False
    assert out["wrong_language"] == "fr"


def test_the_same_comment_where_french_was_asked_goes_out():
    comment = FRENCH_WHERE_ENGLISH_WAS_ASKED[1]

    out = _service(_comment_answer(comment)).generate_smart_comment(
        post_description="", username="someone", language="fr", post_caption=CAPTION,
    )

    assert out["comment"] == comment and out["should_comment"] is True
    assert out["wrong_language"] is None


def test_ideographs_in_a_french_comment_are_refused():
    comment = "la lumière dorée rend ce port plus轻 ce soir"

    out = _service(_comment_answer(comment)).generate_smart_comment(
        post_description="", username="someone", language="fr", post_caption=CAPTION,
    )

    assert out["comment"] == "" and out["wrong_language"] == "letters of another script (轻)"


def test_the_check_runs_on_the_comment_that_goes_out_the_safe_one_included():
    """The anchor is not in the caption: the safe comment is the one published, and it is the
    one held to the language."""
    answer = {"anchor": "a turquoise boat", "reasoning": "r", "comment": "what a turquoise boat",
              "safe_comment": "la lumière dorée sur le port est sublime"}

    out = _service(answer).generate_smart_comment(
        post_description="", username="someone", language="en", post_caption=CAPTION,
    )

    assert out["used_safe_comment"] is True
    assert out["comment"] == "" and out["wrong_language"] == "fr"


@pytest.mark.parametrize("reply", FRENCH_WHERE_ENGLISH_WAS_ASKED[:2])
def test_a_french_reply_where_english_was_asked_is_refused(reply):
    answer = {"should_reply": True, "reasoning": "answers them", "comment": reply}

    out = _service(answer).generate_comment_reply(
        "Where was this taken? The light is amazing", "someone", language="en",
    )

    assert out["success"] is True
    assert out["comment"] == "" and out["should_reply"] is False
    assert out["wrong_language"] == "fr"


def test_a_reply_in_the_language_of_their_comment_is_not_checked_against_a_language():
    """`language="auto"`: the prompt asks for the language of their comment, nothing to hold it to."""
    answer = {"should_reply": True, "reasoning": "answers them", "comment": FRENCH_WHERE_ENGLISH_WAS_ASKED[0]}

    out = _service(answer).generate_comment_reply("Magnifique, c'est où ?", "someone")

    assert out["should_reply"] is True and out["wrong_language"] is None


def test_the_summaries_texts_are_letters_of_another_script_for_a_comment_too():
    out = _service(_comment_answer(FRENCH_SUMMARIES_WITH_IDEOGRAPHS[0])).generate_smart_comment(
        post_description="", username="someone", language="fr", post_caption=CAPTION,
    )

    assert out["comment"] == "" and out["wrong_language"].startswith("letters of another script")
