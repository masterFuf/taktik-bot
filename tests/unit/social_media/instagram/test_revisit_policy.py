"""Revisit delays are the operator's call, and they are scoped to the account automated.

Two independent settings (see RevisitPolicy):
  - how long an interaction keeps a profile off-limits for THIS account;
  - how long a stored filter decision stays valid before the profile is re-evaluated.

The second one did not exist: a profile filtered once ("0 posts", "private account") was
banned from that account forever, even though those reasons describe a moment and not a
profile. On the real DB that was 2424 profiles filtered more than 60 days ago, still
excluded — the oldest since December.
"""

import pytest

from taktik.core.social_media.instagram.actions.business.workflows.common.revisit_policy import (
    DEFAULT_REFILTER_DAYS,
    DEFAULT_REINTERACTION_DAYS,
    RevisitPolicy,
)


# ── Reading the operator's settings ────────────────────────────────────────────

def test_absent_filters_fall_back_to_defaults():
    # Standalone bot / older desktop build: behaviour must not change.
    policy = RevisitPolicy.from_filters(None)

    assert policy.reinteraction_days == DEFAULT_REINTERACTION_DAYS
    assert policy.refilter_days == DEFAULT_REFILTER_DAYS
    assert policy.reinteraction_hours == 60 * 24


@pytest.mark.parametrize("payload", [
    {"reinteractionDays": 30, "refilterDays": 45},   # desktop camelCase
    {"reinteraction_days": 30, "refilter_days": 45},  # bot snake_case
])
def test_both_key_styles_are_accepted(payload):
    policy = RevisitPolicy.from_filters(payload)

    assert policy.reinteraction_days == 30
    assert policy.refilter_days == 45
    assert policy.reinteraction_hours == 30 * 24
    assert policy.filtered_max_age_days == 45


def test_invalid_values_fall_back_instead_of_crashing_a_run():
    policy = RevisitPolicy.from_filters({"reinteractionDays": "soixante", "refilterDays": None})

    assert policy.reinteraction_days == DEFAULT_REINTERACTION_DAYS
    assert policy.refilter_days == DEFAULT_REFILTER_DAYS


def test_negative_values_are_read_as_never():
    policy = RevisitPolicy.from_filters({"reinteractionDays": -5, "refilterDays": -1})

    assert policy.reinteraction_days == 0
    assert policy.refilter_days == 0


# ── "Never come back" ──────────────────────────────────────────────────────────

def test_zero_reinteraction_days_never_re_engages():
    # The processed lookup is a time window, so "never" must be a window wide enough to
    # cover any real history — not 0, which would mean "no cooldown at all".
    policy = RevisitPolicy.from_filters({"reinteractionDays": 0})

    assert policy.reinteraction_hours > 50 * 365 * 24


def test_zero_refilter_days_keeps_filters_permanent():
    # None is what the DB layer reads as "no date bound" -> the pre-existing behaviour.
    policy = RevisitPolicy.from_filters({"refilterDays": 0})

    assert policy.filtered_max_age_days is None


def test_a_positive_refilter_delay_expires_stored_filters():
    policy = RevisitPolicy.from_filters({"refilterDays": 90})

    assert policy.filtered_max_age_days == 90
