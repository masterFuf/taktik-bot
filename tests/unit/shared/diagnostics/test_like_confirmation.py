"""Likes not seen in a row leave the posts, then stop the run; a like seen starts the count again.
Logic only: what a real screen makes of it is in
`tests/unit/social_media/instagram/services/test_like_reads_its_hearts_label.py`.
"""

from taktik.core.shared.diagnostics import like_confirmation, run_halt
from taktik.core.shared.diagnostics.run_start import begin_run

TO_LEAVE = like_confirmation.UNCONFIRMED_LIKES_BEFORE_LEAVING
JUST_UNDER = like_confirmation.UNCONFIRMED_LIKES_BEFORE_HALT - 1


def _not_seen(times):
    for _ in range(times):
        like_confirmation.like_not_seen()


def test_the_threshold_sets_the_latch_with_its_code():
    _not_seen(JUST_UNDER)
    assert run_halt.arret_demande() is None

    _not_seen(1)

    assert run_halt.arret_demande()["code"] == run_halt.LIKE_UNCONFIRMED


def test_a_few_in_a_row_ask_to_leave_the_posts_and_the_run_goes_on():
    _not_seen(TO_LEAVE - 1)
    assert not like_confirmation.leave_posts_asked()

    _not_seen(1)

    assert like_confirmation.leave_posts_asked()
    assert run_halt.arret_demande() is None


def test_the_posts_entered_next_are_walked_and_left_in_their_turn():
    _not_seen(TO_LEAVE)

    like_confirmation.posts_entered()
    assert not like_confirmation.leave_posts_asked(), "the next posts were left before one like"
    _not_seen(TO_LEAVE - 1)
    assert not like_confirmation.leave_posts_asked()
    _not_seen(1)

    assert like_confirmation.leave_posts_asked()
    assert run_halt.arret_demande() is None


def test_entering_posts_does_not_start_the_count_again():
    # Three lists of posts left one after the other, without one like seen: the run stops.
    for _ in range(like_confirmation.UNCONFIRMED_LIKES_BEFORE_HALT // TO_LEAVE):
        like_confirmation.posts_entered()
        _not_seen(TO_LEAVE)

    assert run_halt.arret_demande()["code"] == run_halt.LIKE_UNCONFIRMED


def test_a_like_seen_starts_the_count_again():
    _not_seen(JUST_UNDER)
    like_confirmation.like_seen()
    assert not like_confirmation.leave_posts_asked()
    _not_seen(JUST_UNDER)

    assert run_halt.arret_demande() is None


def test_a_new_run_holds_nothing_against_the_phone():
    _not_seen(JUST_UNDER)

    begin_run()
    assert not like_confirmation.leave_posts_asked()
    _not_seen(JUST_UNDER)

    assert run_halt.arret_demande() is None


def test_the_first_likes_not_seen_of_a_run_keep_their_screen():
    kept = [like_confirmation.screen_to_keep() for _ in range(like_confirmation.SCREENS_KEPT_PER_RUN + 2)]

    assert kept == [True] * like_confirmation.SCREENS_KEPT_PER_RUN + [False, False]

    begin_run()
    assert like_confirmation.screen_to_keep(), "a new run kept no screen"
