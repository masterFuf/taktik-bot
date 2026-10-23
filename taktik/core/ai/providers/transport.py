"""How `AIService` reaches a model: one interface, one implementation per provider.

In Symfony terms, `ModelTransport` is the interface a service type-hints (as it would
`HttpClientInterface`), and `OpenRouterTransport` (`providers/openrouter.py`) and
`AnthropicTransport` (`providers/anthropic.py`) are its two implementations. `AIService` keeps what
is the same whoever answers: the total deadline, the one run-log line per call and the cost ledger
(`ai_spend`). A transport does the rest: the request in its provider's format, the retries, and an
answer in the shape below.

The answer of `complete`, a dict, the same for both providers:
  success        the model answered something;
  text           the answer (on success);
  error          why not (on failure);
  model          the model that served the call, as the provider names it;
  provider       who answered (`AI_PROVIDERS`);
  usage          the provider's own usage block, untouched;
  tokens         {"prompt", "completion", "cached"}: the same counts in one shape, for the log;
  cost_usd       what the call cost, None when nothing says (a failure before any answer);
  cost_basis     "billed" (the provider said what it charged) or "public_price" (computed from
                 the tokens at the public prices of the policy);
  finish_reason  why the model stopped, in the provider's words;
  upstream       the backend a gateway routed to (OpenRouter only), else None;
  rate_limited   the failure is the provider's rate limit (429).

A billed call that answered nothing is a failure that still carries its `cost_usd`: the ledger
reports on "were we charged", not on "did it work".
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Protocol, Sequence

from loguru import logger

# urllib's timeout is a socket-inactivity timeout, not a total request deadline: a provider can
# drip bytes and hold a profile for ever. The total deadline is `AIService`'s.
MODEL_SOCKET_TIMEOUT_SECONDS = 30.0

COST_BILLED = "billed"
COST_PUBLIC_PRICE = "public_price"


@dataclass(frozen=True)
class ModelCall:
    """One call, as the engine writes it: chat messages in OpenAI's format (the prompts are
    written in it, images as `image_url` data URLs), whoever answers."""

    model: str
    messages: list
    temperature: float
    max_tokens: int


class ModelTransport(Protocol):
    """What `AIService` asks of a provider."""

    provider: str
    label: str  # the provider's name, for a person ("OpenRouter")

    def complete(self, call: ModelCall) -> Dict[str, Any]:
        ...


@dataclass
class HttpOutcome:
    """What one POST ended on, after its retries: an answer, a refusal or no answer at all."""

    data: Optional[dict] = None  # the parsed JSON of a 2xx
    status: Optional[int] = None  # the HTTP status of a refusal
    body: str = ""  # the body of that refusal
    error: Optional[str] = None  # no answer: network, unreadable JSON
    form: int = 0  # the request form the outcome came from


def _refusal_body(exc: urllib.error.HTTPError, label: str) -> str:
    try:
        return exc.read().decode("utf-8")
    except Exception as read_error:  # noqa: BLE001 - the status is still known, the body is not
        logger.warning(f"[AIService] {label} HTTP {exc.code}: the body could not be read ({read_error})")
        return ""


def post_json(
    url: str,
    headers: Dict[str, str],
    forms: Sequence[bytes],
    *,
    first_form: int,
    form_refused: Callable[[int, str], bool],
    retryable_statuses: Sequence[int],
    backoff_seconds: Sequence[float],
    model: str,
    label: str,
) -> HttpOutcome:
    """POST one call, with the policy both providers share.

    `forms` are the same request in its successive shapes (OpenRouter: reasoning off, then the
    minimal effort; Anthropic: the thinking-off forms). A 400 that `form_refused` recognises moves
    to the next shape, once each: a blanket retry on 400 would re-send every malformed or
    quota-refused request. A status of `retryable_statuses` waits `backoff_seconds` (the policy's
    `RATE_LIMIT_BACKOFF_SECONDS`, two growing waits), then gives up: a third would hold a run on an upstream saturated for longer than
    a burst. Anything else stays one call.
    """
    form = first_form
    waits: list = []
    while True:
        request = urllib.request.Request(url, data=forms[form], headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=MODEL_SOCKET_TIMEOUT_SECONDS) as response:
                return HttpOutcome(data=json.loads(response.read().decode("utf-8")), form=form)
        except urllib.error.HTTPError as exc:
            body = _refusal_body(exc, label)
            if form + 1 < len(forms) and form_refused(exc.code, body):
                form += 1
                logger.info(
                    f"[AIService] {model} refused that request form — retrying with the next one, "
                    f"and remembering it for this model"
                )
                continue
            if exc.code in retryable_statuses and len(waits) < len(backoff_seconds):
                wait = backoff_seconds[len(waits)]
                waits.append(wait)
                reason = "rate-limited upstream" if exc.code == 429 else f"HTTP {exc.code} upstream"
                logger.warning(
                    f"[AIService] {model} {reason} — waiting {wait:.0f}s "
                    f"before retry {len(waits)}/{len(backoff_seconds)}"
                )
                time.sleep(wait)
                continue
            logger.error(f"[AIService] {label} HTTP {exc.code}: {body[:300]}")
            return HttpOutcome(status=exc.code, body=body, form=form)
        except Exception as exc:  # noqa: BLE001 - said, and returned as the call's failure
            logger.error(f"[AIService] {label} error: {exc}")
            return HttpOutcome(error=str(exc), form=form)


def refusal_answer(outcome: HttpOutcome) -> Dict[str, Any]:
    """The failure of a call that got no answer: a refusal (its status and body) or none at all."""
    if outcome.status is None:
        return {"success": False, "error": outcome.error or "no answer"}
    return {
        "success": False,
        "error": f"HTTP {outcome.status}: {outcome.body[:200]}",
        # Distinguishable from a real failure, so a caller can fall back rather than drop the work.
        "rate_limited": outcome.status == 429,
    }


__all__ = [
    "COST_BILLED",
    "COST_PUBLIC_PRICE",
    "HttpOutcome",
    "MODEL_SOCKET_TIMEOUT_SECONDS",
    "ModelCall",
    "ModelTransport",
    "post_json",
    "refusal_answer",
]
