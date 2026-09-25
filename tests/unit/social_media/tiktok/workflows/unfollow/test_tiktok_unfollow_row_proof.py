"""An unfollow on TikTok counts only when the row proves it, and nothing waits for a sheet that is not there.

Two defects of the TikTok unfollow, reachable in French since T4 (report of the night of
2026-09-23, question 14): every tap was counted, whatever the row showed afterwards, and each tap
was followed by a 1 s sleep plus a 2 s wait for a confirmation sheet the following list never
shows (the row turns « Suivre » in place). And nothing was written to the base (T2).

The screen is uiautomator2's own engine on a list shaped like the French 46.6.3 captures
(conftest.py). The words are read through the catalogue with the French locale active.
"""


def test_a_row_that_turns_into_suivre_is_one_unfollow_recorded(screen, make_workflow, base_db):
    workflow = make_workflow([screen.Row("Alpha", "alpha_one")], max_unfollows=5)

    stats = workflow.run()

    assert stats.unfollowed == 1 and stats.unconfirmed == 0
    assert workflow.events == [("unfollowed", "alpha_one")]
    assert base_db.recorded == [("alpha_one", 7)]
    assert stats.recorded == 1


def test_a_row_that_still_says_suivis_is_not_counted(screen, make_workflow, base_db):
    workflow = make_workflow([screen.Row("Alpha", "alpha_one", on_tap=screen.STAY)], max_unfollows=5)

    stats = workflow.run()

    assert stats.unfollowed == 0
    assert stats.unconfirmed == 1
    assert workflow.events == [("not_confirmed", "alpha_one", "following")]
    assert base_db.recorded == []


def test_no_fixed_wait_for_a_sheet_the_list_does_not_show(screen, make_workflow, clock):
    """The row flips at once: no sleep at all between the tap and the count (delays set to 0)."""
    workflow = make_workflow([screen.Row("Alpha", "alpha_one")], max_unfollows=1)

    workflow.run()

    tap_to_count = [s for s in clock.slept if s not in (0, 2)]  # 2 s = the two navigation settles
    assert tap_to_count == []
    assert workflow.phone.sheet_shown == 0


def test_a_confirmation_sheet_is_tapped_only_when_it_shows(screen, make_workflow, base_db):
    workflow = make_workflow([screen.Row("Alpha", "alpha_one", on_tap=screen.SHEET)], max_unfollows=1)

    stats = workflow.run()

    assert workflow.phone.sheet_shown == 1
    assert workflow.phone.sheet_for is None  # the sheet was confirmed
    assert stats.unfollowed == 1
    assert base_db.recorded == [("alpha_one", 7)]


def test_the_wait_for_the_row_is_bounded(screen, make_workflow, clock):
    workflow = make_workflow([screen.Row("Alpha", "alpha_one", on_tap=screen.STAY)], max_unfollows=1, confirm_timeout=2.0)

    workflow.run()

    waited = sum(s for s in clock.slept if s < 1)
    assert 1.9 <= waited <= 2.4


def test_three_unconfirmed_taps_in_a_row_stop_the_run(screen, make_workflow):
    rows = [screen.Row(f"R{i}", f"handle_{i}", on_tap=screen.STAY) for i in range(5)]
    workflow = make_workflow(rows, max_unfollows=10)

    stats = workflow.run()

    assert stats.unconfirmed == 3
    assert stats.stop_reason == "unfollow_unconfirmed"
    assert [row.taps for row in rows] == [1, 1, 1, 0, 0]


def test_friends_are_kept_and_counted_once(screen, make_workflow):
    rows = [screen.Row("Beta", "beta_two", label="Ami(e)s"), screen.Row("Alpha", "alpha_one")]
    workflow = make_workflow(rows, max_unfollows=5)

    stats = workflow.run()

    assert stats.unfollowed == 1
    assert stats.refusals == {"friends": 1}
    assert stats.to_dict()["skipped"] == 1
    assert rows[0].taps == 0


def test_the_handle_is_paired_on_4314_rows_too(screen, make_workflow, base_db):
    """On 43.1.4 the handle's top sits 58 px below the button's: the old 50 px test lost it,
    so the unfollow could neither date nor record the account."""
    workflow = make_workflow([screen.Row("Alpha", "alpha_one", handle_offset=58)], max_unfollows=1)

    workflow.run()

    assert base_db.recorded == [("alpha_one", 7)]


def test_a_confirmed_unfollow_of_a_row_without_a_handle_is_counted_but_not_filed(screen, make_workflow, base_db):
    workflow = make_workflow([screen.Row("Keo", None)], max_unfollows=1)

    stats = workflow.run()

    assert stats.unfollowed == 1
    assert stats.recorded == 0
    assert base_db.recorded == []
