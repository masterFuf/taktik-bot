"""A process that meets a second phone starts again from the baseline.

The catalogues are process-globals. Applying 447 then 410 in the same process (the CLI loop, a
clone after the official app) used to leave the 447 entries in place, and the 442 DM row
selector, which only knows the Compose inbox, found no row on the 410.
"""

import pytest

from taktik.core.compat.selectors.setup import INSTAGRAM_TARGET_VERSION, apply_version_overrides
from taktik.core.social_media.instagram.ui.selectors import DETECTION_SELECTORS, DM_SELECTORS, PROFILE_SELECTORS


@pytest.fixture(autouse=True)
def back_to_baseline():
    yield
    apply_version_overrides("instagram", INSTAGRAM_TARGET_VERSION)


def _snapshot():
    return (list(PROFILE_SELECTORS.bio), list(PROFILE_SELECTORS.enrichment_category_selectors),
            list(DETECTION_SELECTORS._business_account_indicators_base), DM_SELECTORS.thread_container)


def test_the_baseline_comes_back_after_a_newer_phone():
    baseline = _snapshot()
    assert apply_version_overrides("instagram", "447.0.0.55.81") > 0
    assert _snapshot() != baseline
    apply_version_overrides("instagram", INSTAGRAM_TARGET_VERSION)
    assert _snapshot() == baseline


def test_an_older_override_set_drops_the_newer_entries():
    baseline = _snapshot()
    apply_version_overrides("instagram", "447.0.0.55.81")
    apply_version_overrides("instagram", "442.0.0.46.79")
    bio, category, business, thread = _snapshot()
    assert (bio, category, business) == baseline[:3]
    assert thread != baseline[3]


def test_applying_twice_is_the_same_as_once():
    apply_version_overrides("instagram", "447.0.0.55.81")
    once = _snapshot()
    apply_version_overrides("instagram", "447.0.0.55.81")
    assert _snapshot() == once


def test_a_refused_field_does_not_break_the_next_apply():
    """A read-only property in an override is skipped; it must not be \"restored\" later."""
    from taktik.core.compat.selectors.setup import _patch_singleton

    baseline = _snapshot()
    assert _patch_singleton("detection", DETECTION_SELECTORS,
                            {"detection.business_account_indicators": ["//refused"]}) == 0
    assert apply_version_overrides("instagram", "447.0.0.55.81") > 0
    apply_version_overrides("instagram", INSTAGRAM_TARGET_VERSION)
    assert _snapshot() == baseline
