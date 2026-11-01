"""Likes not seen in a row stop the run; a like seen starts the count again. Logic only: what a real
screen makes of it is in `tests/unit/social_media/instagram/services/test_like_reads_its_hearts_label.py`.
"""

from taktik.core.shared.diagnostics import like_confirmation, run_halt
from taktik.core.shared.diagnostics.run_start import begin_run

JUST_UNDER = like_confirmation.UNCONFIRMED_LIKES_BEFORE_HALT - 1


def _not_seen(times):
    for _ in range(times):
        like_confirmation.like_not_seen()


def test_the_threshold_sets_the_latch_with_its_code():
    _not_seen(JUST_UNDER)
    assert run_halt.arret_demande() is None

    _not_seen(1)

    assert run_halt.arret_demande()["code"] == run_halt.LIKE_UNCONFIRMED


def test_a_like_seen_starts_the_count_again():
    _not_seen(JUST_UNDER)
    like_confirmation.like_seen()
    _not_seen(JUST_UNDER)

    assert run_halt.arret_demande() is None


def test_a_new_run_holds_nothing_against_the_phone():
    _not_seen(JUST_UNDER)

    begin_run()
    _not_seen(JUST_UNDER)

    assert run_halt.arret_demande() is None
