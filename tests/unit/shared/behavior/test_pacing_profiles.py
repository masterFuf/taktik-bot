"""Pacing profiles — 'natural' (default) has no inter-step pause; 'balanced' keeps the former
5-15s; variants are slower/faster; safe resolve."""

from taktik.core.shared.behavior.profiles import (
    PacingProfile,
    PACING_PROFILES,
    resolve_pacing_profile,
)


def test_balanced_reproduces_current_values():
    p = PACING_PROFILES["balanced"]
    # The FORMER default's hardcoded numbers — still available by explicit id.
    assert (p.action_delay_min, p.action_delay_max) == (5.0, 15.0)
    assert (p.fatigue_base, p.fatigue_per_minute, p.fatigue_cap) == (1.0, 0.6, 1.5)
    assert (p.short_break_every_min, p.short_break_every_max) == (8, 15)
    assert (p.short_break_min_s, p.short_break_max_s) == (5.0, 15.0)
    assert (p.long_break_every_min, p.long_break_every_max) == (30, 50)
    assert (p.long_break_min_s, p.long_break_max_s) == (60.0, 180.0)


def test_natural_is_default_with_no_inter_step_pause():
    p = PACING_PROFILES["natural"]
    # The new default: essentially no systematic inter-step delay (a tiny varied gap)…
    assert p.action_delay_min == 0.0 and p.action_delay_max <= 1.0
    # …but the occasional real breaks are KEPT (same as balanced) — those are human.
    b = PACING_PROFILES["balanced"]
    assert (p.short_break_min_s, p.short_break_max_s) == (b.short_break_min_s, b.short_break_max_s)
    assert (p.long_break_every_min, p.long_break_every_max) == (b.long_break_every_min, b.long_break_every_max)


def test_resolve_defaults_to_natural():
    assert resolve_pacing_profile(None).profile_id == "natural"
    assert resolve_pacing_profile("does_not_exist").profile_id == "natural"
    assert resolve_pacing_profile("careful").profile_id == "careful"
    assert resolve_pacing_profile("balanced").profile_id == "balanced"


def test_careful_is_slower_than_balanced():
    b, c = PACING_PROFILES["balanced"], PACING_PROFILES["careful"]
    assert c.action_delay_min > b.action_delay_min
    assert c.action_delay_max > b.action_delay_max
    assert c.short_break_every_max < b.short_break_every_max   # breaks more often
    assert c.long_break_max_s > b.long_break_max_s             # longer long breaks


def test_fast_debug_is_faster_than_balanced():
    b, f = PACING_PROFILES["balanced"], PACING_PROFILES["fast_debug"]
    assert f.action_delay_max < b.action_delay_max
    assert f.long_break_every_min > b.long_break_every_min     # breaks far rarer


def test_strict_test_is_deterministic_friendly():
    s = PACING_PROFILES["strict_test"]
    assert s.action_delay_min == 0.0 and s.action_delay_max == 0.0
    assert s.fatigue_per_minute == 0.0 and s.fatigue_cap == 1.0
    assert s.short_break_every_min >= 10_000   # breaks effectively off


def test_every_profile_id_is_a_PacingProfile():
    for pid, prof in PACING_PROFILES.items():
        assert isinstance(prof, PacingProfile)
        assert prof.profile_id == pid
        assert prof.action_delay_max >= prof.action_delay_min >= 0
