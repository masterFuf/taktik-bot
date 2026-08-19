"""The one way to build an AIService from a run's `ai` config.

Four bridges used to build it themselves — Instagram automation, Instagram scraping,
Instagram agent, TikTok automation — and they did NOT agree. Only the scraping one passed
`niche_taxonomy`, so the premium taxonomy reached the classifier during scraping and was
absent everywhere else. Same call, same model, same prompt builder, two different behaviours
depending on which bridge happened to construct the service.

What that cost, measured over 99 August automation runs (3 713 classifications):

  - the model never saw the 20 valid category keys, so it invented its own slugs
    (`health_wellness`, `health_and_wellness`, `media_production`, `film_and_media`…) and
    `_canonicalize_niche_category` clamped **486 of them (13.1 %)** to `other` — a
    classification paid for and then thrown away;
  - it never saw the 251 sub-niche labels either, so **every single call** proposed a
    free-form sub-niche that the desktop then had to fuzzy-match back onto the taxonomy.

The taxonomy is front-owned premium data: the open-source bot must keep working without it,
so an absent taxonomy still yields a usable free-form classification. What must never happen
again is one bridge getting it and another not.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple

LogCallback = Callable[[str, str], None]

_MIN_API_KEY_LENGTH = 5


def _noop_log(_level: str, _message: str) -> None:
    return None


def build_ai_service(
    *,
    api_key: str,
    ipc: Any = None,
    vision_model: Optional[str] = None,
    text_model: Optional[str] = None,
    niche_taxonomy: Optional[Dict[str, list]] = None,
) -> Any:
    """Construct the service. Every AIService in the product goes through here.

    `niche_taxonomy` (slug -> [sub-niche labels]) is the premium classification taxonomy
    injected by the desktop app through the session config. The open-source bot does not own
    it; when it is absent the classifier stays free-form rather than failing.
    """
    from taktik.core.app.ai.providers.openrouter import AIService

    return AIService(
        api_key=api_key,
        ipc=ipc,
        vision_model=vision_model,
        text_model=text_model,
        niche_taxonomy=niche_taxonomy,
    )


def create_ai_service(
    *,
    ai_config: Dict[str, Any],
    ipc: Any = None,
    log: LogCallback = _noop_log,
    ready_message: str = "AI mode enabled",
) -> Tuple[bool, Any]:
    """Build the optional AI service from a run's `ai` config block.

    Returns `(enabled, service)`; `(False, None)` when AI is off or no usable key was
    injected, so a caller can keep running without AI exactly as before.

    The taxonomy is read here, from the config, for EVERY caller — that is the whole point of
    this function. A bridge that wants an AI service asks for one; it does not get to decide
    which parts of the config the classifier is allowed to see.
    """
    if not ai_config.get("enabled", False):
        return False, None

    api_key = ai_config.get("openrouterApiKey", "")
    if not (api_key and len(api_key) > _MIN_API_KEY_LENGTH):
        log("warning", "AI mode requested but no OpenRouter API key provided")
        return False, None

    taxonomy = ai_config.get("nicheTaxonomy") or ai_config.get("niche_taxonomy") or None
    service = build_ai_service(
        api_key=api_key,
        ipc=ipc,
        vision_model=ai_config.get("visionModel") or None,
        text_model=ai_config.get("textModel") or None,
        niche_taxonomy=taxonomy,
    )

    # Say whether the taxonomy arrived. A run classifying against a free-form taxonomy is a
    # legitimate standalone setup and a silent regression on the desktop — the log is what
    # tells the two apart without re-reading the payload.
    if taxonomy:
        log("info", f"{ready_message} (taxonomy: {len(taxonomy)} categories)")
    else:
        log("info", f"{ready_message} (no taxonomy injected - free-form classification)")
    return True, service


__all__ = ["build_ai_service", "create_ai_service", "LogCallback"]
