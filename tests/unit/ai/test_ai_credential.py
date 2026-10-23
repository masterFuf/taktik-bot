"""The key a run calls the AI with travels with its provider (`AICredential`).

`openrouterApiKey` was the only key a payload could carry. A payload now says the provider and the
key (`provider` + `apiKey` in an `ai` block); the old name is still read, and only as what it always
was, an OpenRouter key: paired with another provider it would send an OpenRouter key to Anthropic.
"""

import pytest

from taktik.core.ai.credential import AICredential, credential_from_env, read_credential
from taktik.core.ai.factory import create_ai_service
from taktik.core.ai.openrouter_policy import ANTHROPIC_MODEL, MODEL_GENERATION

ANTHROPIC_KEY = "sk-ant-api03-" + "a" * 40
OPENROUTER_KEY = "sk-or-v1-" + "o" * 40


def _block(**fields):
    return read_credential(fields, provider_names=("provider",), key_names=("apiKey",),
                           openrouter_key_names=("openrouterApiKey",))


def test_the_provider_and_the_key_are_read_together():
    assert _block(provider="anthropic", apiKey=ANTHROPIC_KEY) == AICredential("anthropic", ANTHROPIC_KEY)


def test_the_old_name_is_an_openrouter_key_and_nothing_else():
    assert _block(openrouterApiKey=OPENROUTER_KEY) == AICredential("openrouter", OPENROUTER_KEY)
    # Anthropic asked, only the old OpenRouter name filled: no key, never the OpenRouter one.
    assert _block(provider="anthropic", openrouterApiKey=OPENROUTER_KEY) == AICredential("anthropic", "")
    # The new name comes first.
    assert _block(apiKey="new-key-123", openrouterApiKey=OPENROUTER_KEY).api_key == "new-key-123"


def test_an_unknown_provider_is_refused():
    with pytest.raises(ValueError):
        _block(provider="mistral", apiKey="k" * 10)


def test_the_environment_serves_openrouter_first():
    assert credential_from_env({"ANTHROPIC_API_KEY": ANTHROPIC_KEY}) == AICredential("anthropic", ANTHROPIC_KEY)
    assert credential_from_env({"ANTHROPIC_API_KEY": ANTHROPIC_KEY,
                                "OPENROUTER_API_KEY": OPENROUTER_KEY}) == AICredential("openrouter", OPENROUTER_KEY)
    assert credential_from_env({}) is None


def test_a_credential_never_prints_its_key():
    credential = AICredential("anthropic", ANTHROPIC_KEY)

    assert ANTHROPIC_KEY not in repr(credential)
    assert ANTHROPIC_KEY not in str(credential)
    assert str(credential).endswith(ANTHROPIC_KEY[-4:])


def test_the_factory_builds_the_service_of_the_block_s_provider():
    enabled, service = create_ai_service(ai_config={"enabled": True, "provider": "anthropic", "apiKey": ANTHROPIC_KEY})
    assert enabled and service.provider == "anthropic" and service.model_generation == ANTHROPIC_MODEL

    enabled, service = create_ai_service(ai_config={"enabled": True, "openrouterApiKey": OPENROUTER_KEY})
    assert enabled and service.provider == "openrouter" and service.model_generation == MODEL_GENERATION


def test_the_factory_says_which_provider_has_no_key():
    said = []
    enabled, service = create_ai_service(
        ai_config={"enabled": True, "provider": "anthropic", "openrouterApiKey": OPENROUTER_KEY},
        log=lambda level, message: said.append((level, message)),
    )

    assert (enabled, service) == (False, None)
    assert said == [("warning", "AI mode requested but no anthropic API key provided")]
