"""The glossary informs the writing. It is the one mechanism of the four that does not judge.

Three others were built and measured against the same problem on 2026-09-09 and all three were
net-negative: an LLM proofreader rewrote correct text, a lower temperature kept the mistakes and
tripled repeated openings, and a determiner corrector broke five correct comments out of six.
Their shared flaw was judging output after the fact, when the model's generation IN CONTEXT is
more reliable than any out-of-context judgement it makes about it.

This one adds a line to the prompt and gets out of the way. Measured: +4 % cost (it rides in the
cached prefix), no loss of variety, and on a forced probe 1 mistake in 30 uses became 0 in 40.
"""

from taktik.core.app.ai import glossary
from taktik.core.app.ai.providers.openrouter import AIService


def system_prompt(language, reply=False):
    seen = {}
    service = AIService(api_key="x" * 10)

    def capture(model, messages, *a, **k):
        blocks = messages[0]["content"]
        seen["stable"] = "".join(
            b["text"] for b in blocks if b.get("cache_control")) if not isinstance(
            blocks, str) else blocks
        return {"success": True, "model": model, "cost_usd": 0.0,
                "text": '{"anchor": "a", "comment": "c", "safe_comment": "s", '
                        '"reasoning": "r", "should_reply": true}'}

    service._call_openrouter = capture
    if reply:
        service.generate_comment_reply(comment_text="joli", username="x", language=language)
    else:
        service.generate_smart_comment(post_description="d", username="x", language=language)
    return seen["stable"]


def test_only_correct_forms_are_ever_shown():
    """A model reads an example as something to use.

    Measured the same day: given "ça m'intrigue" as an example way out of a rule, mistral-nemo
    published that exact phrase in 5 of 18 comments. Showing "le vibe" here to warn against it
    would be offering it.
    """
    text = glossary.block("fr")
    assert "la vibe" in text and "cet angle" in text
    for wrong in ("le vibe", "ce angle", "la néon", "cette oxymore", "de la live"):
        assert wrong not in text, wrong


def test_a_language_with_nothing_to_say_contributes_nothing():
    """Not an empty header, not an empty list — nothing at all for a model to interpret.

    English, Chinese, Japanese and Turkish have no grammatical gender, so their emptiness is a
    fact about the language rather than a gap waiting to be filled.
    """
    for language in ("en", "zh", "ja", "tr", "sw", "", None):
        assert glossary.block(language) == ""


def test_the_line_reaches_the_cached_prefix_of_both_generators():
    """It belongs with the rules, not with the per-post data: it does not change between two
    French comments, so it is billed at a tenth like the rest of the prefix."""
    for reply in (False, True):
        assert "la vibe" in system_prompt("fr", reply=reply)
        assert "la vibe" not in system_prompt("en", reply=reply)


def test_the_same_language_yields_the_same_prefix():
    """The cache pays only for a byte-identical prefix. One account writes in one or two
    languages, so this costs one or two warm entries — never one per post."""
    assert system_prompt("fr") == system_prompt("fr")
    assert system_prompt("fr") != system_prompt("en")


def test_a_repeated_entry_is_listed_once():
    """The list grows by hand from mistakes seen in published output, so it will collect
    duplicates; a model reading the same form twice learns nothing extra and pays for it."""
    text = glossary.block("fr")
    assert text.count("cet oxymore") == 1
