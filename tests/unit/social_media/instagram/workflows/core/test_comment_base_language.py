"""A French account must comment in French — never in the operator's app language.

Session 631 (2026-07-25, @institut.rentable, a French beauty-coaching account) posted two
comments IN ENGLISH on French posts, and skipped two other French posts entirely. Root
cause: `accounts.preferred_language` is NULL on 69 of 74 accounts, and the base language
then fell back to the APP UI language — which was English because the operator reads the
app in English. That fallback made the same run fail in both directions:

  - caption detected 'fr' -> 'fr' outside {en, english} -> comment SKIPPED
  - caption undetected    -> defaulted to 'en'          -> ENGLISH comment on a French post

The app UI language is the OPERATOR's reading preference, never the audience's language,
so it is gone. The account's own persona text is the anchor instead.
"""

from taktik.core.social_media.instagram.workflows.core.ai_hooks import (
    _resolve_base_language,
    _resolve_comment_language,
)

# The real persona stored for @institut.rentable (session 631).
FR_PERSONA = {
    "niche": "Business coaching pour instituts de beauté",
    "tonePersonality": "Professionnel mais accessible, motivant et inspirant",
}
EN_PERSONA = {
    "niche": "Entertainment fan community, Animation",
    "tonePersonality": "Playful, enthusiastic, family-friendly, and welcoming to all",
}


# ── The anchor ──────────────────────────────────────────────────────────────

def test_explicit_preferred_language_wins():
    assert _resolve_base_language({"language": "fr", "niche": "anything"}) == "fr"
    assert _resolve_base_language({"language": "en", "niche": "n'importe quoi en français"}) == "en"


def test_persona_text_is_the_anchor_when_no_explicit_language():
    # This is what rescues the 69 accounts whose preferred_language was never filled.
    assert _resolve_base_language(FR_PERSONA) == "fr"
    assert _resolve_base_language(EN_PERSONA) == "en"


def test_unknown_stays_unknown_and_is_never_invented():
    assert _resolve_base_language({}) is None
    assert _resolve_base_language(None) is None
    # An unreadable persona must NOT be resolved to some default language.
    assert _resolve_base_language({"niche": "???"}) is None


def test_the_resolver_cannot_be_handed_an_app_language():
    """Structural guard: the app UI language cannot come back in through this door."""
    import inspect

    params = list(inspect.signature(_resolve_base_language).parameters)
    assert params == ["account_persona"], f"unexpected parameters: {params}"


# ── The two production failures of session 631 ──────────────────────────────

def test_french_post_on_a_french_account_is_commented_in_french():
    base = _resolve_base_language(FR_PERSONA)
    assert _resolve_comment_language(base, "fr") == "fr"


def test_undetected_caption_falls_back_to_the_account_language_not_english():
    base = _resolve_base_language(FR_PERSONA)
    assert _resolve_comment_language(base, None) == "fr"


def test_the_old_fallback_would_have_produced_the_bug():
    """Locks the old behaviour as WRONG, so the fallback cannot silently come back."""
    # What used to happen when base fell back to the app language:
    assert _resolve_comment_language("en", "fr") is None   # French post -> skipped
    assert _resolve_comment_language("en", None) == "en"   # undetected  -> English comment


# ── The credibility whitelist still holds ───────────────────────────────────

def test_english_post_is_answered_in_english():
    assert _resolve_comment_language("fr", "en") == "en"


def test_a_third_language_is_skipped():
    assert _resolve_comment_language("fr", "other") is None


def test_unknown_account_language_follows_the_post():
    # No anchor: the post's own language is the only credible choice.
    assert _resolve_comment_language(None, "fr") == "fr"
    assert _resolve_comment_language(None, "en") == "en"


def test_unknown_account_language_and_unreadable_post_publishes_nothing():
    # No signal at all -> stay silent rather than guess.
    assert _resolve_comment_language(None, None) is None
    assert _resolve_comment_language(None, "other") is None
