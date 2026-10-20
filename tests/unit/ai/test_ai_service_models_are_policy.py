"""The models of `AIService` come from the policy, and a model asked for outside the policy is said to be ignored.

`AIService(text_model=..., vision_model=...)` accepts two model names and has never used them: the
models are fixed by task in `openrouter_policy.py`. Taking a parameter and dropping it in silence
let a caller believe it had chosen a model while the bill said otherwise. The parameters stay (the
hosts still pass them through the factory), but a value that is none of the policy's models is now
reported.
"""

from loguru import logger

from taktik.core.ai.openrouter_policy import MODEL_ANALYSIS, MODEL_GENERATION
from taktik.core.ai.providers.openrouter import AIService


def _warnings_while(build):
    captured = []
    sink = logger.add(lambda message: captured.append(message.record["message"]), level="WARNING")
    try:
        service = build()
    finally:
        logger.remove(sink)
    return service, captured


def test_a_requested_model_is_not_used_and_the_caller_is_told():
    service, warnings = _warnings_while(
        lambda: AIService(api_key="x" * 10, text_model="other/text-model", vision_model="other/vision-model")
    )

    assert service.text_model == MODEL_ANALYSIS
    assert service.vision_model == MODEL_ANALYSIS
    joined = " ".join(warnings)
    assert "other/text-model" in joined
    assert "other/vision-model" in joined


def test_no_model_requested_or_the_policy_models_say_nothing():
    # What the desktop sends: the generation model as text, the analysis model as vision.
    _service, warnings = _warnings_while(
        lambda: AIService(api_key="x" * 10, text_model=MODEL_GENERATION, vision_model=MODEL_ANALYSIS)
    )
    _service, none_asked = _warnings_while(lambda: AIService(api_key="x" * 10))
    warnings = warnings + none_asked

    assert warnings == []
