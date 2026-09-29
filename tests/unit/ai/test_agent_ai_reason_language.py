"""The Taktik Agent autonomous engine writes its operator-facing `reason` in the APP language.

The `reason` is shown in the Taktik Agent panel, so it must follow the desktop app language (fr/en/
es/...). The `comment` field stays audience-language (the post's language) — not covered here.
"""

from taktik.core.ai.agent_decisions import AgentAI, _reason_language_rule


def test_reason_rule_maps_code_to_full_language_name():
    assert 'French' in _reason_language_rule('fr')
    assert 'Spanish' in _reason_language_rule('es')
    assert 'Portuguese' in _reason_language_rule('pt')
    assert 'English' in _reason_language_rule('en')
    # Always targets the reason field.
    assert '"reason"' in _reason_language_rule('fr')


def test_reason_rule_defaults_to_english_for_unknown_or_empty():
    assert 'English' in _reason_language_rule('')
    assert 'English' in _reason_language_rule(None)
    assert 'English' in _reason_language_rule('xx')


def test_agent_ai_stores_language():
    ai = AgentAI(ai_service=object(), ipc=None, language='fr')
    assert ai.language == 'fr'
    # Backward-compatible default.
    assert AgentAI(ai_service=object()).language == 'en'
