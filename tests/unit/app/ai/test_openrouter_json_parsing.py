"""Model answers that should be JSON: parsing, and one retry when they come back unusable.

Production incident (2026-07-20): a profile classification came back as the four characters
``` ```json\\n{\\n  "n ``` — an upstream cut-off. The call site's hand-rolled fence stripping
turned that into "Unterminated string starting at: line 2 column 3", the profile silently lost
its AI qualification, and nothing in the logs said the answer had been truncated.

Replaying the exact production call nine times returned clean JSON every time (~230-390
completion tokens against a 1100 ceiling), so the cut-off is intermittent and upstream — which
is precisely what a single retry fixes.
"""

import pytest

from taktik.core.app.ai.providers.openrouter import AIService, parse_json_response


# ── parse_json_response ────────────────────────────────────────────────────────

def test_plain_json():
    assert parse_json_response('{"niche": "Theater"}') == {"niche": "Theater"}


def test_fenced_json():
    assert parse_json_response('```json\n{"niche": "Theater"}\n```') == {"niche": "Theater"}


def test_fenced_json_without_language_tag():
    assert parse_json_response('```\n{"niche": "Theater"}\n```') == {"niche": "Theater"}


def test_prose_around_the_fence_is_ignored():
    text = 'Sure! Here you go:\n```json\n{"niche": "Theater"}\n```\nHope that helps.'
    assert parse_json_response(text) == {"niche": "Theater"}


def test_the_exact_truncated_production_answer_raises_valueerror():
    # The whole answer that broke the run. It must NOT raise IndexError, and the caller
    # must get one predictable exception type.
    with pytest.raises(ValueError):
        parse_json_response('```json\n{\n  "n')


def test_unclosed_fence_does_not_raise_indexerror():
    with pytest.raises(ValueError):
        parse_json_response('```json')


def test_empty_response_raises_valueerror():
    with pytest.raises(ValueError):
        parse_json_response('')


# ── partial extraction: salvage fields from a truncated classification ────────

def test_partial_extraction_salvages_country():
    # A truncated classification still often carries the early fields. `country` feeds the
    # audience-persona aggregates (stored as ai_account_based_in), so losing the whole answer
    # must not also lose an inferred country that made it into the text.
    svc = AIService(api_key="test-key")
    text = '{"niche_category": "cinema", "niche": "Actors", "country": "Switzerland", "tags": ["ac'

    partial = svc._extract_partial_classification(text)

    assert partial is not None
    assert partial["country"] == "Switzerland"


# ── vision_json_completion: one retry ──────────────────────────────────────────

class _Svc(AIService):
    """AIService with the network replaced by a scripted list of answers."""

    def __init__(self, answers):
        super().__init__(api_key="test-key")
        self._answers = list(answers)
        self.calls = 0

    def vision_completion(self, *_a, **_k):
        self.calls += 1
        return self._answers.pop(0)


def _ok(text, finish="stop"):
    return {"success": True, "text": text, "finish_reason": finish}


def test_good_answer_is_not_retried():
    svc = _Svc([_ok('{"niche": "Theater"}')])

    result = svc.vision_json_completion("sys", "user", "shot.jpg")

    assert svc.calls == 1
    assert result["payload"] == {"niche": "Theater"}


def test_truncated_answer_is_retried_once_and_recovers():
    svc = _Svc([_ok('```json\n{\n  "n', finish="length"), _ok('{"niche": "Theater"}')])

    result = svc.vision_json_completion("sys", "user", "shot.jpg")

    assert svc.calls == 2
    assert result["success"] is True
    assert result["payload"] == {"niche": "Theater"}


def test_two_unusable_answers_fail_with_the_raw_text_kept():
    svc = _Svc([_ok('```json\n{\n  "n'), _ok('still not json')])

    result = svc.vision_json_completion("sys", "user", "shot.jpg")

    assert svc.calls == 2
    assert result["success"] is False
    assert "JSON parse error" in result["error"]
    assert result["raw"] == 'still not json'


def test_transport_failure_is_not_retried():
    # A dead network / HTTP error will not fix itself in 50ms; retrying only doubles the wait.
    svc = _Svc([{"success": False, "error": "HTTP 502"}])

    result = svc.vision_json_completion("sys", "user", "shot.jpg")

    assert svc.calls == 1
    assert result["success"] is False
    assert result["error"] == "HTTP 502"
