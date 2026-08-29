from taktik.core.social_media.tiktok.services.welcome.duplicate_guard import (
    CLEAR,
    CONTACTED,
    SKIP_ALREADY_DMED,
    SKIP_CONVERSATION_EXISTS,
    SKIP_GUARD_UNAVAILABLE,
    SKIP_NO_ACCOUNT,
    SKIP_NO_RECIPIENT,
    UNKNOWN,
    WelcomeDmGuard,
)


def _raising(_account_id, _handle):
    raise RuntimeError("no such column: platform")


def test_a_never_contacted_recipient_is_cleared():
    guard = WelcomeDmGuard(
        sent_dm_probe=lambda account_id, handle: False,
        thread_probe=lambda account_id, handle: False,
    )

    assert guard.contact_state(7, "creator") == CLEAR
    assert guard.skip_reason(7, "creator") is None


def test_a_recipient_already_in_sent_dms_is_skipped():
    guard = WelcomeDmGuard(sent_dm_probe=lambda account_id, handle: handle == "creator")

    assert guard.contact_state(7, "creator") == CONTACTED
    assert guard.skip_reason(7, "creator") == SKIP_ALREADY_DMED


def test_a_recipient_we_already_have_a_thread_with_is_skipped():
    """`sent_dms` never sees a conversation started from the inbox — a manual answer, an
    auto-reply, the DM read workflow.

    Would have caught the bot greeting someone it was already mid-conversation with.
    """
    guard = WelcomeDmGuard(
        sent_dm_probe=lambda account_id, handle: False,
        thread_probe=lambda account_id, handle: True,
    )

    assert guard.contact_state(7, "creator") == CONTACTED
    assert guard.skip_reason(7, "creator") == SKIP_CONVERSATION_EXISTS


def test_a_guard_that_cannot_read_the_database_refuses_instead_of_answering_never_contacted():
    """The whole reason this class exists.

    `SentDMService.check_already_sent` catches Exception and returns False, so a query that
    raises reads as "never messaged". Instagram cold DM ran on that False for months with no
    duplicate protection at all. Would have caught the same swallow reaching TikTok.
    """
    guard = WelcomeDmGuard(sent_dm_probe=_raising)

    assert guard.contact_state(7, "creator") == UNKNOWN
    assert guard.skip_reason(7, "creator") == SKIP_GUARD_UNAVAILABLE


def test_a_failing_thread_probe_also_refuses_the_send():
    """A first probe answering "clear" is not enough when the second one could not answer."""
    guard = WelcomeDmGuard(
        sent_dm_probe=lambda account_id, handle: False,
        thread_probe=_raising,
    )

    assert guard.contact_state(7, "creator") == UNKNOWN
    assert guard.skip_reason(7, "creator") == SKIP_GUARD_UNAVAILABLE


def test_a_missing_account_is_unknown_not_clear():
    """Without an account nothing can be RECORDED either, so the same welcome would be re-sent
    at every run. Would have caught a standalone run DMing the same people once a day."""
    guard = WelcomeDmGuard(sent_dm_probe=lambda account_id, handle: False)

    assert guard.contact_state(None, "creator") == UNKNOWN
    assert guard.skip_reason(None, "creator") == SKIP_NO_ACCOUNT
    assert guard.skip_reason(0, "creator") == SKIP_NO_ACCOUNT


def test_an_empty_recipient_is_refused_before_any_probe_runs():
    probed = []

    guard = WelcomeDmGuard(sent_dm_probe=lambda account_id, handle: probed.append(handle) or False)

    assert guard.skip_reason(7, "   ") == SKIP_NO_RECIPIENT
    assert probed == []


def test_handles_reach_the_probes_lowercased_and_without_the_at_sign():
    """`sent_dms.recipient_username` is written lowercased by the repository.

    Would have caught "@Creator" missing the row recorded for "creator" and being welcomed twice.
    """
    seen = []

    guard = WelcomeDmGuard(
        sent_dm_probe=lambda account_id, handle: seen.append(handle) or False,
    )
    guard.skip_reason(7, "@Creator")

    assert seen == ["creator"]


def test_filter_recipients_reports_every_skip_with_its_reason():
    def sent_dm_probe(account_id, handle):
        if handle == "boom":
            raise RuntimeError("database is locked")
        return handle == "known"

    guard = WelcomeDmGuard(sent_dm_probe=sent_dm_probe)
    allowed, skipped = guard.filter_recipients(7, ["@Fresh", "known", "boom"])

    assert allowed == ["fresh"]
    assert skipped == {"known": SKIP_ALREADY_DMED, "boom": SKIP_GUARD_UNAVAILABLE}


def test_the_duplicate_checker_handed_to_the_outreach_workflow_skips_on_unknown():
    """The workflow's contract is "True means skip". An unanswerable guard must return True.

    Would have caught the outreach reading the guard's failure as a green light at the exact
    point where the message leaves.
    """
    checker = WelcomeDmGuard(sent_dm_probe=_raising).as_duplicate_checker()

    assert checker(7, "creator", "tiktok") is True


def test_the_duplicate_checker_lets_a_clear_recipient_through():
    checker = WelcomeDmGuard(
        sent_dm_probe=lambda account_id, handle: False,
        thread_probe=lambda account_id, handle: False,
    ).as_duplicate_checker()

    assert checker(7, "creator", "tiktok") is False
