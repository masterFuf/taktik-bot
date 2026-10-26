"""A profile summary written in another language than asked is not stored as one.

The audit of October 2026: since the qualification moved to qwen, 363 summaries of a month, written
in French, carry Chinese ideographs in the middle of a sentence (4 to 9 % of the French ones), and
the profile card shows them. On the same month, 5 summaries asked in French came back English.
The summary goes through the rule every text written by an AI goes through
(`ai/written_language.py`); the rest of the qualification is kept. Texts: `unit.ai_written_texts`.
"""

from __future__ import annotations

import json

import pytest

from taktik.core.ai.providers.openrouter import AIService
from unit.ai_written_texts import FRENCH_SUMMARIES_WITH_IDEOGRAPHS

TAXONOMY = {"art_design": ["Photography"]}


def _classify(answer, response_language="fr", parsed=True):
    service = AIService(api_key="test-key", niche_taxonomy=TAXONOMY)

    def fake_vision_json_completion(system_prompt, user_prompt, image_path, **_):
        if parsed:
            return {"success": True, "text": json.dumps(answer), "payload": dict(answer)}
        # Both attempts unusable: the provider salvages the fields from the raw answer.
        return {"success": False, "error": "JSON parse error", "raw": json.dumps(answer, ensure_ascii=False)[:-1]}

    service.vision_json_completion = fake_vision_json_completion
    service._image_for_vision = lambda path: "data:image/jpeg;base64,AAAA"
    return service.classify_profile_niche(
        username="someone", screenshot_path=__file__, response_language=response_language,
    )


def _answer(summary):
    return {"niche_category": "art_design", "niche": "Photography", "summary": summary,
            "language": "fr", "gender": "female"}


@pytest.mark.parametrize("summary", FRENCH_SUMMARIES_WITH_IDEOGRAPHS)
def test_a_french_summary_with_ideographs_is_not_stored(summary):
    out = _classify(_answer(summary))

    assert out["success"] is True
    assert out["classification"]["summary"] == ""
    assert out["classification"]["niche"] == "Photography", "the rest of the qualification is kept"


def test_a_summary_salvaged_from_a_truncated_answer_goes_through_the_same_rule():
    out = _classify(_answer(FRENCH_SUMMARIES_WITH_IDEOGRAPHS[0]), parsed=False)

    assert out["success"] is True
    assert out["classification"]["niche_category"] == "art_design"
    assert out["classification"]["summary"] == ""


def test_an_english_summary_where_french_was_asked_is_not_stored():
    summary = ("Portrait photographer based in Essonne, specializing in family, children and pet "
               "sessions, with a warm and natural style.")

    assert _classify(_answer(summary))["classification"]["summary"] == ""


def test_a_french_summary_is_stored_as_written():
    summary = ("Photographe de portrait basée au Luxembourg, son compte sert de portfolio pour ses "
               "séances de famille et de couple.")

    assert _classify(_answer(summary))["classification"]["summary"] == summary


def test_the_same_english_summary_is_stored_where_english_was_asked():
    summary = ("Portrait photographer based in Essonne, specializing in family, children and pet "
               "sessions, with a warm and natural style.")

    assert _classify(_answer(summary), response_language="en")["classification"]["summary"] == summary
