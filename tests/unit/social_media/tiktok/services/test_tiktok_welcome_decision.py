from taktik.core.social_media.tiktok.services.welcome.decision import (
    REASON_AI_DECLINED_FOLLOW,
    REASON_AI_OFF,
    REASON_BELOW_THRESHOLD,
    REASON_NOT_RELEVANT,
    REASON_NO_MESSAGE,
    REASON_NO_VERDICT,
    REASON_PROFILE_UNREACHABLE,
    REASON_RELEVANT,
    REASON_UNSCORED,
    WelcomeDecision,
    WelcomePolicy,
    decide_for_new_follower,
    follow_back_targets,
    parse_welcome_policy,
    summarize,
    welcome_dm_targets,
)


def _policy(**overrides) -> WelcomePolicy:
    base = {
        "enabled": True,
        "follow_back": True,
        "welcome_dm": True,
        "min_score": 0.6,
        "dm_requires_follow_back": True,
        "messages": ("Bienvenue !",),
    }
    base.update(overrides)
    return WelcomePolicy(**base)


def _verdict(**overrides) -> dict:
    base = {"relevant": True, "score": 0.9, "follow": True, "reason": "same niche"}
    base.update(overrides)
    return base


def test_a_run_that_says_nothing_about_ai_decides_nothing():
    """Would have caught the welcome pass switching itself on for every existing scrape run."""
    policy = parse_welcome_policy(None)

    assert policy.enabled is False
    decision = decide_for_new_follower("creator", _verdict(), policy)
    assert (decision.follow_back, decision.welcome_dm, decision.reason) == (False, False, REASON_AI_OFF)


def test_ai_enabled_alone_does_not_turn_a_scrape_into_an_outreach():
    """`ai.enabled` is already sent by every AI-capable TikTok run for the relevance verdict.

    Would have caught a profile-qualification run starting to send private messages the day the
    front began forwarding its usual AI block to this bridge.
    """
    policy = parse_welcome_policy({"enabled": True, "profileAnalysis": True})

    assert policy.enabled is False


def test_the_welcome_dm_stays_off_unless_it_is_asked_for_by_name():
    """Would have caught `welcomeDm` defaulting to true and writing to strangers on a follow-back run."""
    policy = parse_welcome_policy({"enabled": True, "newFollowers": {"enabled": True}})

    assert policy.enabled is True
    assert policy.follow_back is True
    assert policy.welcome_dm is False


def test_a_missing_verdict_is_neither_a_yes_nor_a_no():
    """Would have caught a provider error being read as approval — the AI never answered."""
    decision = decide_for_new_follower("creator", None, _policy())

    assert (decision.follow_back, decision.welcome_dm) == (False, False)
    assert decision.reason == REASON_NO_VERDICT
    assert decision.relevant is None


def test_a_relevant_profile_with_no_score_cannot_clear_a_threshold():
    """Would have caught `minScore` becoming decorative: a verdict with no score sliding through."""
    decision = decide_for_new_follower("creator", _verdict(score=None), _policy())

    assert decision.reason == REASON_UNSCORED
    assert (decision.follow_back, decision.welcome_dm) == (False, False)


def test_a_boolean_score_is_not_a_score_of_one():
    """`True` is a valid float in Python: `float(True) == 1.0`.

    Would have caught a model answering `score: true` scoring a perfect 1.0 that nobody measured.
    """
    decision = decide_for_new_follower("creator", _verdict(score=True), _policy())

    assert decision.reason == REASON_UNSCORED
    assert decision.score is None


def test_a_verdict_below_the_operator_threshold_is_refused():
    decision = decide_for_new_follower("creator", _verdict(score=0.4), _policy(min_score=0.6))

    assert decision.reason == REASON_BELOW_THRESHOLD
    assert (decision.follow_back, decision.welcome_dm) == (False, False)
    assert decision.score == 0.4


def test_an_irrelevant_profile_is_refused_before_the_score_is_even_read():
    decision = decide_for_new_follower("creator", _verdict(relevant=False, score=0.95), _policy())

    assert decision.reason == REASON_NOT_RELEVANT
    assert decision.relevant is False


def test_the_ai_declining_the_follow_also_cancels_the_welcome_message():
    """Default policy: no DM to someone we did not even judge worth following back.

    Would have caught a run that skipped the follow and still wrote privately to the person.
    """
    decision = decide_for_new_follower("creator", _verdict(follow=False), _policy())

    assert (decision.follow_back, decision.welcome_dm) == (False, False)
    assert decision.reason == REASON_AI_DECLINED_FOLLOW


def test_a_welcome_message_can_go_out_without_a_follow_back_when_the_policy_allows_it():
    decision = decide_for_new_follower(
        "creator", _verdict(follow=False), _policy(dm_requires_follow_back=False)
    )

    assert (decision.follow_back, decision.welcome_dm) == (False, True)
    assert decision.reason == REASON_RELEVANT


def test_a_welcome_dm_with_no_message_text_is_not_sent():
    """The bot never composes: the texts come from the app. No text means no message.

    Would have caught a run reporting welcomes it had nothing to type.
    """
    policy = _policy(messages=())
    decision = decide_for_new_follower("creator", _verdict(), policy)

    assert decision.welcome_dm is False
    assert decision.follow_back is True
    assert policy.dm_requested_without_message is True


def test_a_message_requested_without_text_and_without_a_follow_says_so():
    decision = decide_for_new_follower("creator", _verdict(follow=False), _policy(messages=()))

    assert decision.reason == REASON_AI_DECLINED_FOLLOW


def test_a_relevant_follower_is_followed_back_and_welcomed():
    decision = decide_for_new_follower("@Creator", _verdict(), _policy())

    assert decision.username == "Creator"
    assert (decision.follow_back, decision.welcome_dm) == (True, True)
    assert decision.reason == REASON_RELEVANT
    assert decision.score == 0.9


def test_targets_keep_the_order_the_followers_were_met_in():
    decisions = [
        WelcomeDecision("first", follow_back=True, welcome_dm=True, reason=REASON_RELEVANT),
        WelcomeDecision("second", reason=REASON_NOT_RELEVANT),
        WelcomeDecision("third", follow_back=True, reason=REASON_RELEVANT),
    ]

    assert follow_back_targets(decisions) == ["first", "third"]
    assert welcome_dm_targets(decisions) == ["first"]


def test_the_summary_separates_a_rejected_run_from_an_unreachable_one():
    """Both end at "0 welcomed"; only the reason breakdown says which one happened.

    Would have caught a workflow that navigated nowhere reporting the same success line as one
    where the AI simply said no to everybody.
    """
    unreachable = [WelcomeDecision("a", reason=REASON_PROFILE_UNREACHABLE)] * 3
    rejected = [WelcomeDecision("b", reason=REASON_NOT_RELEVANT)] * 3

    assert summarize(unreachable)["reasons"] == {REASON_PROFILE_UNREACHABLE: 3}
    assert summarize(rejected)["reasons"] == {REASON_NOT_RELEVANT: 3}
    assert summarize(unreachable)["welcome_dm"] == 0


def test_the_policy_reads_both_camel_case_and_snake_case_config_keys():
    """The bridge payload is camelCase, a standalone CLI config is snake_case; both are real."""
    camel = parse_welcome_policy(
        {
            "enabled": True,
            "newFollowers": {
                "enabled": True,
                "followBack": False,
                "welcomeDm": True,
                "minScore": 0.8,
                "maxDms": 3,
                "messages": ["  Salut  ", "", "Bienvenue"],
            },
        }
    )
    snake = parse_welcome_policy(
        {
            "enabled": True,
            "new_followers": {
                "enabled": True,
                "follow_back": False,
                "welcome_dm": True,
                "min_score": 0.8,
                "max_dms": 3,
                "messages": ["  Salut  ", "", "Bienvenue"],
            },
        }
    )

    assert camel == snake
    assert camel.messages == ("Salut", "Bienvenue")
    assert camel.min_score == 0.8
    assert camel.max_dms == 3


def test_an_unusable_threshold_falls_back_instead_of_disabling_the_check():
    """Would have caught `minScore: "high"` crashing the run, or worse, becoming 0."""
    policy = parse_welcome_policy(
        {"enabled": True, "newFollowers": {"enabled": True, "minScore": "high"}}
    )

    assert policy.min_score == 0.6
