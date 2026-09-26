"""What every OpenRouter call of the product sends, declared once.

The bot's transport (`providers/openrouter.py`) reads these values; the desktop app's copy is
GENERATED from this file (`npm run ai:policy -- --write` in the app), and the same command fails
as soon as the two differ. The gate runs this file on its own, so it stays free of imports.
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
