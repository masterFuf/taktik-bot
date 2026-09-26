"""A TikTok unfollow that TikTok refuses stops the run at once, uncounted and unwritten.

Before, only three unconfirmed rows in a row stopped it (`unfollow_unconfirmed`): a refusal whose
row still flipped was counted, and the run tapped on. The look after the tap is the same one every
TikTok writing path makes (`look_for_action_block`).
"""

from taktik.core.shared.diagnostics import run_halt


class _Refusing:
    def __init__(self, refuse_after):
        self.looks = 0
        self.refuse_after = refuse_after

    def is_action_blocked(self):
        self.looks += 1
        if self.looks >= self.refuse_after:
            run_halt.demander_arret(run_halt.ACTION_BLOCKED, "tiktok (Too many requests)")
            return True
        return False


def test_the_first_refused_unfollow_stops_the_run(screen, make_workflow, base_db):
    rows = [screen.Row("Alpha", "alpha_one"), screen.Row("Beta", "beta_two"),
            screen.Row("Gamma", "gamma_three")]
    workflow = make_workflow(rows, max_unfollows=5)
    workflow._detection = _Refusing(refuse_after=2)

    stats = workflow.run()

    assert stats.stop_reason == "action_blocked"
    assert stats.unfollowed == 1
    assert base_db.recorded == [("alpha_one", 7)], "a refused unfollow was written"
    assert [row.taps for row in rows] == [1, 1, 0], "a row tapped after the refusal"


def test_a_block_seen_elsewhere_in_the_run_stops_the_list_before_its_first_tap(screen, make_workflow):
    rows = [screen.Row("Alpha", "alpha_one")]
    workflow = make_workflow(rows, max_unfollows=5)
    run_halt.demander_arret(run_halt.ACTION_BLOCKED, "seen by the popup handler")

    stats = workflow.run()

    assert stats.stop_reason == "action_blocked"
    assert rows[0].taps == 0
