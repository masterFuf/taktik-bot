from taktik.core.shared.behavior import BehaviorPolicy, parse_behavior_policy


def test_parse_behavior_policy_absent_returns_none():
    assert parse_behavior_policy({}) is None
    assert parse_behavior_policy(None) is None


def test_parse_behavior_policy_non_object_returns_none():
    assert parse_behavior_policy({"behaviorPolicy": "balanced"}) is None


def test_parse_behavior_policy_complete_payload():
    policy = parse_behavior_policy(
        {
            "behaviorPolicy": {
                "profileId": "careful",
                "seed": 123,
                "strictRegression": True,
                "pausePolicy": {
                    "enabled": True,
                    "afterActions": 12,
                    "durationMinSeconds": 30,
                    "durationMaxSeconds": 180,
                    "strategy": "close_app",
                    "interruptible": True,
                    "resume": {"reentry": "from_home", "rotateContext": False},
                },
                "typingPolicy": {},
                "tapPolicy": {"foo": "bar"},
                "scrollPolicy": {},
                "futureField": "ignored",
            }
        }
    )

    assert isinstance(policy, BehaviorPolicy)
    assert policy.profile_id == "careful"
    assert policy.seed == 123
    assert policy.strict_regression is True
    assert policy.pause is not None
    assert policy.pause.enabled is True
    assert policy.pause.after_actions == 12
    assert policy.pause.duration_min_seconds == 30.0
    assert policy.pause.duration_max_seconds == 180.0
    assert policy.pause.strategy == "close_app"
    assert policy.pause.interruptible is True
    assert policy.pause.resume is not None
    assert policy.pause.resume.reentry == "from_home"
    assert policy.pause.resume.rotate_context is False
    assert policy.typing_raw == {}
    assert policy.tap_raw == {"foo": "bar"}
    assert policy.scroll_raw == {}


def test_parse_behavior_policy_partial_payload_uses_defaults():
    policy = parse_behavior_policy({"behaviorPolicy": {"pausePolicy": {"enabled": True}}})

    assert policy is not None
    assert policy.profile_id == "balanced"
    assert policy.seed is None
    assert policy.strict_regression is False
    assert policy.pause is not None
    assert policy.pause.enabled is True
    assert policy.pause.after_actions is None
    assert policy.pause.strategy == "idle_in_app"
    assert policy.pause.interruptible is True
    assert policy.pause.resume is None


def test_parse_behavior_policy_invalid_values_fallback_safely():
    policy = parse_behavior_policy(
        {
            "behaviorPolicy": {
                "profileId": "rocket",
                "seed": "bad",
                "strictRegression": "yes",
                "pausePolicy": {
                    "enabled": "yes",
                    "afterActions": "12",
                    "durationMinSeconds": "30",
                    "strategy": "teleport",
                    "interruptible": "yes",
                    "resume": {"reentry": "last_screen", "rotateContext": "yes"},
                },
            }
        }
    )

    assert policy is not None
    assert policy.profile_id == "balanced"
    assert policy.seed is None
    assert policy.strict_regression is False
    assert policy.pause is not None
    assert policy.pause.enabled is False
    assert policy.pause.after_actions is None
    assert policy.pause.duration_min_seconds is None
    assert policy.pause.strategy == "idle_in_app"
    assert policy.pause.interruptible is True
    assert policy.pause.resume is not None
    assert policy.pause.resume.reentry == "from_home"
    assert policy.pause.resume.rotate_context is True
