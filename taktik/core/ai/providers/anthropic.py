"""The Anthropic implementation of `ModelTransport`: the Messages API, Claude models only.

The engine writes its prompts in OpenAI's chat format (what OpenRouter takes as is); this transport
translates them:
  - the system messages become the top-level `system`, a list of text blocks; the blocks of
    `cacheable_system()` already carry Anthropic's `cache_control`, so they pass unchanged;
  - an `image_url` part (a `data:` URL) becomes an `image` block with its base64 and media type;
  - text parts pass unchanged, strings too.

What OpenRouter is asked differently here, from the policy (`openrouter_policy.py`):
  - thinking off, by the first form the model accepts (`ANTHROPIC_THINKING_OFF_FORMS`);
  - no temperature: the current Claude models refuse any value but their default;
  - the retried statuses (`ANTHROPIC_RETRYABLE_HTTP_STATUSES`, 529 "overloaded" among them);
  - the cost: Anthropic answers with tokens only, so the cost is computed from them at the public
    prices (`ANTHROPIC_PRICES_USD_PER_MTOK`) and said to be (`cost_basis` "public_price"). A model
    without a price is refused before the request: its spend could not be counted.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from taktik.core.ai.openrouter_policy import (
    ANTHROPIC_API_VERSION,
    ANTHROPIC_LONG_PROMPT_PRICES_USD_PER_MTOK,
    ANTHROPIC_PRICES_USD_PER_MTOK,
    ANTHROPIC_RETRYABLE_HTTP_STATUSES,
    ANTHROPIC_THINKING_OFF_FORMS,
    PROVIDER_ANTHROPIC,
    RATE_LIMIT_BACKOFF_SECONDS,
)

from .transport import COST_PUBLIC_PRICE, ModelCall, post_json, refusal_answer

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"


# ------------------------------------------------------------------------------- the messages


def _image_block(url: str) -> Dict[str, Any]:
    """An `image_url` of the engine as Anthropic's image block: a data URL, or a web address."""
    if url.startswith("data:") and ";base64," in url:
        header, data = url.split(",", 1)
        media_type = header[len("data:"):].split(";", 1)[0] or "image/jpeg"
        return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}
    return {"type": "image", "source": {"type": "url", "url": url}}


def _content(content: Any) -> Any:
    """A message's content in Anthropic's blocks; a string stays a string."""
    if not isinstance(content, list):
        return content
    blocks: List[Dict[str, Any]] = []
    for part in content:
        if isinstance(part, dict) and part.get("type") == "image_url":
            url = (part.get("image_url") or {}).get("url") or ""
            blocks.append(_image_block(url))
        else:
            blocks.append(part)
    return blocks


def anthropic_messages(messages: list) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """(system blocks, messages) of a chat in OpenAI's format, in the Messages API's."""
    system: List[Dict[str, Any]] = []
    turns: List[Dict[str, Any]] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role == "system":
            if isinstance(content, list):
                system.extend(block for block in content if isinstance(block, dict))
            elif content:
                system.append({"type": "text", "text": str(content)})
            continue
        turns.append({"role": role, "content": _content(content)})
    return system, turns


# ------------------------------------------------------------------------------- the cost


def public_price_cost(model: str, usage: Dict[str, Any]) -> Optional[float]:
    """What a call cost at Anthropic's public prices, from the tokens it answered with; None for a
    model the policy has no price for.

    Uncached input, cache writes, cache reads and output each have their price. Haiku 5.5 prices a
    prompt over its threshold (all of its input tokens, cache reads and writes counted) at its long
    prices, for the whole request.
    """
    prices = ANTHROPIC_PRICES_USD_PER_MTOK.get(model)
    if prices is None:
        return None
    uncached = usage.get("input_tokens") or 0
    cache_write = usage.get("cache_creation_input_tokens") or 0
    cache_read = usage.get("cache_read_input_tokens") or 0
    output = usage.get("output_tokens") or 0
    long_prices = ANTHROPIC_LONG_PROMPT_PRICES_USD_PER_MTOK.get(model)
    if long_prices and uncached + cache_write + cache_read > long_prices["above_prompt_tokens"]:
        prices = long_prices
    return (
        uncached * prices["input"]
        + cache_write * prices["cache_write"]
        + cache_read * prices["cache_read"]
        + output * prices["output"]
    ) / 1_000_000


# ------------------------------------------------------------------------------- the transport


class AnthropicTransport:
    """`ModelTransport` over the Messages API."""

    provider = PROVIDER_ANTHROPIC
    label = "Anthropic"

    def __init__(self, api_key: str):
        self.api_key = api_key
        # The thinking-off form each model accepted, learned from its first refusals and kept, so
        # a refusal is provoked once per model rather than once per call.
        self._thinking_form: Dict[str, int] = {}

    def complete(self, call: ModelCall) -> Dict[str, Any]:
        if call.model not in ANTHROPIC_PRICES_USD_PER_MTOK:
            message = (
                f"{call.model} has no public price in the policy (ANTHROPIC_PRICES_USD_PER_MTOK): "
                f"its spend could not be counted, nothing was sent"
            )
            logger.error(f"[AIService] {message}")
            return {"success": False, "error": message}

        system, turns = anthropic_messages(call.messages)
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_API_VERSION,
            "Content-Type": "application/json",
        }

        def body(form: dict) -> bytes:
            request: Dict[str, Any] = {
                "model": call.model,
                "max_tokens": call.max_tokens,
                "messages": turns,
                **form,
            }
            if system:
                request["system"] = system
            return json.dumps(request).encode("utf-8")

        outcome = post_json(
            ANTHROPIC_API_URL,
            headers,
            tuple(body(form) for form in ANTHROPIC_THINKING_OFF_FORMS),
            first_form=self._thinking_form.get(call.model, 0),
            form_refused=lambda status, text: status == 400 and "thinking" in text.lower(),
            retryable_statuses=ANTHROPIC_RETRYABLE_HTTP_STATUSES,
            backoff_seconds=RATE_LIMIT_BACKOFF_SECONDS,
            model=call.model,
            label=self.label,
        )
        if outcome.form:
            self._thinking_form[call.model] = outcome.form
        if outcome.data is None:
            return refusal_answer(outcome)
        return self._answer(call, outcome.data)

    @staticmethod
    def _answer(call: ModelCall, data: dict) -> Dict[str, Any]:
        served = data.get("model") or call.model
        usage = data.get("usage") or {}
        # Thinking blocks, when a model cannot turn thinking off, are not the answer.
        text = "".join(
            block.get("text") or ""
            for block in data.get("content") or []
            if isinstance(block, dict) and block.get("type") == "text"
        )
        stop_reason = data.get("stop_reason")
        priced = served if served in ANTHROPIC_PRICES_USD_PER_MTOK else call.model
        cost = public_price_cost(priced, usage)
        tokens = {
            "prompt": (usage.get("input_tokens") or 0)
            + (usage.get("cache_creation_input_tokens") or 0)
            + (usage.get("cache_read_input_tokens") or 0),
            "completion": usage.get("output_tokens"),
            "cached": usage.get("cache_read_input_tokens") or 0,
        }
        billed = {
            "model": served,
            "provider": PROVIDER_ANTHROPIC,
            "usage": usage,
            "tokens": tokens,
            "cost_usd": cost,
            "cost_basis": COST_PUBLIC_PRICE,
            "finish_reason": stop_reason,
        }
        if stop_reason == "max_tokens":
            logger.warning(
                f"[AIService] {call.model} hit the {call.max_tokens}-token ceiling "
                f"(output={usage.get('output_tokens')}); response is truncated"
            )
        # A refusal is paid for and answers nothing usable; said apart from an empty answer.
        if stop_reason == "refusal":
            category = (data.get("stop_details") or {}).get("category")
            logger.error(f"[AIService] {call.model} refused the request (category={category})")
            return {"success": False, "error": f"{call.model} refused the request (category={category})", **billed}
        if not text.strip():
            logger.error(f"[AIService] {call.model} returned an empty answer (stop_reason={stop_reason})")
            return {"success": False, "error": f"empty answer from {call.model} (stop_reason={stop_reason})", **billed}
        return {"success": True, "text": text.strip(), **billed}


__all__ = ["ANTHROPIC_API_URL", "AnthropicTransport", "anthropic_messages", "public_price_cost"]
