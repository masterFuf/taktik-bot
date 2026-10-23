"""What every model call of the product sends, declared once: OpenRouter's, and Anthropic's.

The bot's transports (`providers/openrouter.py`, `providers/anthropic.py`) read these values; the
desktop app's copy is GENERATED from this file (`npm run ai:policy -- --write` in the app), and the
same command fails as soon as the two differ. The gate runs this file on its own, so it stays free
of imports.
"""

# Models by task. Each task keeps its own constant, so one can move on its own measurement.
MODEL_GENERATION = "qwen/qwen3.7-flash"      # comment / DM / persona / scheduler
MODEL_CLASSIFICATION = "qwen/qwen3.7-flash"  # classify a profile from its screenshot
# Post description. qwen was benched on 30 real posts and wrote the description in English
# on 20 of them, against 0 for this model: the switch was refused on that measurement.
MODEL_ANALYSIS = "google/gemini-3.1-flash-lite"

# Waits before retrying a transient failure: two, growing, then give up. A third would only
# hold a run on an upstream that is saturated for longer than a burst.
RATE_LIMIT_BACKOFF_SECONDS = (2.0, 6.0)

# Statuses retried with those waits: the upstream rate limit (429), and the gateway's
# "bad upstream answer" (502) and "no provider available" (503), which are not billed.
# Anything else (quota, bad request, auth) stays one call.
RETRYABLE_HTTP_STATUSES = (429, 502, 503)

# Every call asks for an answer, never for a train of thought. The strong form first; an
# endpoint that answers 400 "reasoning is mandatory" gets the minimal effort instead.
REASONING_OFF = {"enabled": False}
REASONING_MINIMAL = {"effort": "minimal"}

# Preferred upstream, for the prompt cache; fallbacks allowed so a renamed or saturated
# backend never fails a whole run.
PROVIDER_PREFERENCE = {
    "order": ["google-ai-studio", "google-vertex"],
    "allow_fallbacks": True,
}

# ------------------------------------------------------------------------------- providers

# Who a call goes to. OpenRouter serves every model, the ones TAKTIK measured among them;
# Anthropic serves the Claude models only, through its own API, with a key of its own.
PROVIDER_OPENROUTER = "openrouter"
PROVIDER_ANTHROPIC = "anthropic"
AI_PROVIDERS = (PROVIDER_OPENROUTER, PROVIDER_ANTHROPIC)

# The key a run takes when its host knows both: OpenRouter first, where the measured models are.
RUN_PROVIDER_ORDER = (PROVIDER_OPENROUTER, PROVIDER_ANTHROPIC)

# The engine's three model roles; the comments of the models above say which call takes which.
TASK_GENERATION = "generation"          # comment / DM / persona / scheduler
TASK_CLASSIFICATION = "classification"  # classify a profile from its screenshot
TASK_ANALYSIS = "analysis"              # describe a post
AI_TASKS = (TASK_GENERATION, TASK_CLASSIFICATION, TASK_ANALYSIS)

# How a model stands for a task: benched by TAKTIK on real profiles, posts or comments, or put
# there by TAKTIK without a bench yet (the desktop shows it as proposed, not yet measured).
MODEL_MEASURED = "measured"
MODEL_PROPOSED = "proposed"

# Every task at Anthropic: the cheapest Claude that reads images. Proposed, not measured: the
# bench (`scripts/eval/replay_models.py --provider anthropic`) has not run on it.
ANTHROPIC_MODEL = "claude-haiku-5-5"

MODELS_BY_TASK = {
    TASK_GENERATION: {PROVIDER_OPENROUTER: MODEL_GENERATION, PROVIDER_ANTHROPIC: ANTHROPIC_MODEL},
    TASK_CLASSIFICATION: {PROVIDER_OPENROUTER: MODEL_CLASSIFICATION, PROVIDER_ANTHROPIC: ANTHROPIC_MODEL},
    TASK_ANALYSIS: {PROVIDER_OPENROUTER: MODEL_ANALYSIS, PROVIDER_ANTHROPIC: ANTHROPIC_MODEL},
}
MODEL_STATUS_BY_TASK = {
    TASK_GENERATION: {PROVIDER_OPENROUTER: MODEL_MEASURED, PROVIDER_ANTHROPIC: MODEL_PROPOSED},
    TASK_CLASSIFICATION: {PROVIDER_OPENROUTER: MODEL_MEASURED, PROVIDER_ANTHROPIC: MODEL_PROPOSED},
    TASK_ANALYSIS: {PROVIDER_OPENROUTER: MODEL_MEASURED, PROVIDER_ANTHROPIC: MODEL_PROPOSED},
}

# ------------------------------------------------------------------------------- anthropic

ANTHROPIC_API_VERSION = "2023-06-01"

# Retried with the same waits as OpenRouter's: the rate limit (429), the API's own error (500)
# and "overloaded" (529), none of them billed. Anything else stays one call.
ANTHROPIC_RETRYABLE_HTTP_STATUSES = (429, 500, 529)

# An answer, never a train of thought, as `REASONING_OFF` asks OpenRouter. No form is accepted by
# every Claude model, so they are tried in this order, each once, on a 400 that names thinking,
# and the accepted one is remembered per model:
#   Haiku 5.5 turns thinking off (at its default effort, `medium`);
#   Sonnet 5.5 refuses "disabled" and thinks only between tool calls, and these calls have none;
#   Opus 5.5 cannot turn it off: the least of it.
# No temperature is ever sent: these models refuse any value but their default.
ANTHROPIC_THINKING_OFF_FORMS = (
    {"thinking": {"type": "disabled"}},
    {"thinking": {"type": "between_tools"}},
    {"output_config": {"effort": "low"}},
)

# Anthropic answers with tokens and no cost: a call's cost is computed from them at the public
# prices below, in dollars per million tokens, and reported as such (`cost_basis` "public_price"),
# never as a billed figure. Read on https://platform.claude.com/docs/en/about-claude/pricing on the
# date below; `cache_write` is the 5-minute write, the one `cache_control: ephemeral` asks for. A
# model missing here is never called: its spend could not be counted.
ANTHROPIC_PRICES_READ_ON = "2026-10-23"
ANTHROPIC_PRICES_USD_PER_MTOK = {
    "claude-haiku-5-5": {"input": 0.10, "cache_write": 0.125, "cache_read": 0.01, "output": 0.50},
    "claude-sonnet-5-5": {"input": 2.0, "cache_write": 2.5, "cache_read": 0.10, "output": 10.0},
    "claude-opus-5-5": {"input": 4.0, "cache_write": 5.0, "cache_read": 0.20, "output": 20.0},
}
# Haiku 5.5 bills a prompt longer than this (cache reads and writes counted) at its long prices.
ANTHROPIC_LONG_PROMPT_PRICES_USD_PER_MTOK = {
    "claude-haiku-5-5": {
        "above_prompt_tokens": 100000,
        "input": 0.50, "cache_write": 0.625, "cache_read": 0.05, "output": 2.50,
    },
}
