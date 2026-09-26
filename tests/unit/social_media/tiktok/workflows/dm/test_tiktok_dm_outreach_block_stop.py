"""A TikTok DM that TikTok refuses is not a sent DM, and the run stops before the next recipient."""

from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.tiktok.actions.business.workflows.dm import TikTokDMOutreachWorkflow

from test_tiktok_dm_outreach_workflow import (  # noqa: E402 - sibling test module
    FakeBaseAction,
    FakeDMActions,
    FakeManager,
    FakeNavigation,
    FakeNotifier,
    FakeRng,
)


class _Refusing:
    def is_action_blocked(self):
        run_halt.demander_arret(run_halt.ACTION_BLOCKED, "tiktok (Too many requests)")
        return True


def test_the_first_refused_dm_ends_the_run_unrecorded():
    FakeManager.instances = []
    notifier = FakeNotifier()
    records = []
    workflow = TikTokDMOutreachWorkflow(
        "device-1",
        notifier=notifier,
        duplicate_checker=lambda *args: False,
        sent_dm_recorder=lambda *args: records.append(args),
        manager_factory=FakeManager,
        navigation_factory=FakeNavigation,
        dm_actions_factory=FakeDMActions,
        base_action_factory=FakeBaseAction,
        rng=FakeRng(),
        sleeper=lambda duration: None,
    )
    assert workflow.connect() is True
    workflow._block_detector = lambda: _Refusing()

    result = workflow.run(["first", "second"], ["hello"], delay_min=0, delay_max=0, max_dms=5,
                          account_id=7, session_id="session-1")

    assert result["stop_reason"] == "action_blocked"
    assert result["dms_success"] == 0 and result["dms_failed"] == 1
    assert records == [], "a refused DM written as sent"
    assert workflow.dm_actions.sent_messages == ["hello"], "the second recipient was written to"
    assert workflow.navigation.home_count == 0, "the way home closes the refusal"
