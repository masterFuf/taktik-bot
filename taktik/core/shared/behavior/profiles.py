"""Pacing profiles — the rhythm of a session comes from a PROFILE, not user-set seconds.

A human's pace (delay between actions, how fast fatigue builds, how often they take a break)
is a *style*, not a number the operator should tune in seconds. `PacingProfile` resolves a
profile id ('natural' / 'balanced' / 'careful' / 'fast' / … ) into the concrete pacing
numbers the engine uses.

DEFAULT is `natural` (since 2026-06-10): NO systematic inter-step pause — the bot is already
slow from real work (UI nav, AI analysis, scrolling), so the old 5-15s gap was superfluous
and read as robotic (confirmed by run cadence measurement). `balanced` reproduces the FORMER
default exactly (delay 5-15s, fatigue 1.0→×1.5/hour, breaks 5-15s/60-180s) and stays available
by explicit id. Variants are slower ('careful', 'slow_reader') or faster ('fast', 'fast_debug').

Wiring: `SessionManager.get_delay_between_actions` reads the profile's delay when no explicit
user delay is set (an explicit `delay_between_actions` still wins). The fatigue/breaks fields
are part of the model for completeness (the small `_human_like_delay` hesitations and the
`_maybe_take_break` occasional pauses are kept — they're human, not robotic);
wiring them is deferred because `HumanBehavior` is a shared singleton (per-session injection
would clobber across parallel devices — see the redesign spec).

See `internal docs` §8 (Lot 3) and the humanization
master plan §3.4.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PacingProfile:
    profile_id: str
    # Delay between high-level workflow actions (seconds).
    action_delay_min: float
    action_delay_max: float
    # Fatigue multiplier over time: mult = base + minutes/60 * per_minute, capped at cap.
    fatigue_base: float
    fatigue_per_minute: float
    fatigue_cap: float
    # Short break: every [min,max] interactions, for [s_min,s_max] seconds.
    short_break_every_min: int
    short_break_every_max: int
    short_break_min_s: float
    short_break_max_s: float
    # Long break: every [min,max] interactions, for [s_min,s_max] seconds.
    long_break_every_min: int
    long_break_every_max: int
    long_break_min_s: float
    long_break_max_s: float


# 'balanced' MUST equal today's hardcoded values (regression target).
_BALANCED = PacingProfile(
    profile_id="balanced",
    action_delay_min=5.0, action_delay_max=15.0,
    fatigue_base=1.0, fatigue_per_minute=0.6, fatigue_cap=1.5,
    short_break_every_min=8, short_break_every_max=15, short_break_min_s=5.0, short_break_max_s=15.0,
    long_break_every_min=30, long_break_every_max=50, long_break_min_s=60.0, long_break_max_s=180.0,
)

# 'natural' is the NEW DEFAULT (Kevin, 2026-06-10): the bot is already slow from real work
# (UI nav, AI analysis, scrolling), so the systematic 5-15s inter-step pause was superfluous
# and read as robotic. Near-zero inter-step delay (a tiny varied gap to avoid metronomic
# regularity) — the small contextual `_human_like_delay` hesitations and the occasional real
# breaks (kept identical to balanced below) provide the human texture instead.
_NATURAL = PacingProfile(
    profile_id="natural",
    action_delay_min=0.0, action_delay_max=1.0,
    fatigue_base=1.0, fatigue_per_minute=0.6, fatigue_cap=1.5,
    short_break_every_min=8, short_break_every_max=15, short_break_min_s=5.0, short_break_max_s=15.0,
    long_break_every_min=30, long_break_every_max=50, long_break_min_s=60.0, long_break_max_s=180.0,
)

PACING_PROFILES = {
    "natural": _NATURAL,
    "balanced": _BALANCED,
    # Slower, more cautious: longer gaps, fatigue builds faster, breaks more often + longer.
    "careful": PacingProfile(
        profile_id="careful",
        action_delay_min=8.0, action_delay_max=24.0,
        fatigue_base=1.0, fatigue_per_minute=0.8, fatigue_cap=1.7,
        short_break_every_min=6, short_break_every_max=12, short_break_min_s=10.0, short_break_max_s=25.0,
        long_break_every_min=22, long_break_every_max=38, long_break_min_s=90.0, long_break_max_s=240.0,
    ),
    # A reader: a touch slower than balanced (dwell-heavy elsewhere), breaks like balanced.
    "slow_reader": PacingProfile(
        profile_id="slow_reader",
        action_delay_min=7.0, action_delay_max=20.0,
        fatigue_base=1.0, fatigue_per_minute=0.6, fatigue_cap=1.6,
        short_break_every_min=8, short_break_every_max=15, short_break_min_s=8.0, short_break_max_s=18.0,
        long_break_every_min=28, long_break_every_max=46, long_break_min_s=70.0, long_break_max_s=200.0,
    ),
    # Faster real profile (user-facing 'Rapide'): tighter gaps, light fatigue, less frequent breaks.
    "fast": PacingProfile(
        profile_id="fast",
        action_delay_min=2.0, action_delay_max=6.0,
        fatigue_base=1.0, fatigue_per_minute=0.3, fatigue_cap=1.3,
        short_break_every_min=18, short_break_every_max=30, short_break_min_s=4.0, short_break_max_s=10.0,
        long_break_every_min=60, long_break_every_max=90, long_break_min_s=30.0, long_break_max_s=90.0,
    ),
    # Extreme/deterministic-ish for debugging: very tight gaps, almost no breaks.
    "fast_debug": PacingProfile(
        profile_id="fast_debug",
        action_delay_min=1.0, action_delay_max=4.0,
        fatigue_base=1.0, fatigue_per_minute=0.2, fatigue_cap=1.2,
        short_break_every_min=25, short_break_every_max=40, short_break_min_s=2.0, short_break_max_s=6.0,
        long_break_every_min=90, long_break_every_max=140, long_break_min_s=15.0, long_break_max_s=40.0,
    ),
    # Deterministic-friendly for regression: near-zero delays, flat fatigue, breaks effectively off.
    "strict_test": PacingProfile(
        profile_id="strict_test",
        action_delay_min=0.0, action_delay_max=0.0,
        fatigue_base=1.0, fatigue_per_minute=0.0, fatigue_cap=1.0,
        short_break_every_min=10_000, short_break_every_max=10_000, short_break_min_s=0.0, short_break_max_s=0.0,
        long_break_every_min=10_000, long_break_every_max=10_000, long_break_min_s=0.0, long_break_max_s=0.0,
    ),
}


def resolve_pacing_profile(profile_id) -> PacingProfile:
    """Return the PacingProfile for an id, defaulting to 'natural' for unknown/None.

    'natural' (no systematic inter-step pause) is the default since 2026-06-10 — the old
    5-15s 'balanced' pacing is still available by explicit id for callers that want it."""
    return PACING_PROFILES.get(profile_id or "natural", _NATURAL)


__all__ = ["PacingProfile", "PACING_PROFILES", "resolve_pacing_profile"]
