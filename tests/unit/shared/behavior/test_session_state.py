from taktik.core.shared.behavior.session_state import BehaviorSessionState
from taktik.core.shared.telemetry import clear_telemetry_sink, configure_telemetry_sink


def test_seeded_session_choices_are_reproducible():
    left = BehaviorSessionState(seed=73)
    right = BehaviorSessionState(seed=73)

    left_choices = [left.choose_scroll_mode(context="post") for _ in range(30)]
    right_choices = [right.choose_scroll_mode(context="post") for _ in range(30)]

    assert left_choices == right_choices
    assert left.snapshot() == right.snapshot()


def test_style_is_kept_until_the_reported_burst_is_consumed():
    state = BehaviorSessionState(seed=12)
    first = state.choose_scroll_mode(context="post")
    style = first["style"]

    for _ in range(first["burst_remaining"]):
        choice = state.choose_scroll_mode(context="post")
        assert choice["style"] == style
        assert choice["style_changed"] is False


def test_motor_parameters_move_together_with_the_session_style():
    state = BehaviorSessionState(seed=19)
    state._style = "brisk"
    state._burst_remaining = 3
    brisk = state.motor_modulation(context="post", emit=False, jitter=False)

    state._style = "deliberate"
    deliberate = state.motor_modulation(context="post", emit=False, jitter=False)

    assert brisk["velocity_scale"] > deliberate["velocity_scale"]
    assert brisk["distance_scale"] < deliberate["distance_scale"]
    assert brisk["settle_scale"] < deliberate["settle_scale"]
    assert brisk["dwell_scale"] < deliberate["dwell_scale"]


def test_reading_keeps_the_style_of_the_gesture_that_finished_a_burst():
    state = BehaviorSessionState(seed=21)
    state._style = "brisk"
    state._burst_remaining = 1

    choice = state.choose_scroll_mode(context="post")
    dwell_scale = state.reading_scale(context="post_reading")

    assert choice["style"] == "brisk"
    assert choice["burst_remaining"] == 0
    assert state.snapshot()["style"] == "brisk"
    assert dwell_scale < 1.0


def test_style_transitions_favour_continuity_over_extreme_jumps():
    state = BehaviorSessionState(seed=8, profile_id="natural")

    after_brisk = state._transition_weights("brisk")
    after_deliberate = state._transition_weights("deliberate")

    # Tuple order follows brisk, steady, deliberate.
    assert after_brisk[2] < after_brisk[0]
    assert after_brisk[2] < after_brisk[1]
    assert after_deliberate[0] < after_deliberate[1]
    assert after_deliberate[0] < after_deliberate[2]


def test_energy_drifts_smoothly_toward_the_current_style():
    state = BehaviorSessionState(seed=31)
    state._style = "brisk"
    state._burst_remaining = 8
    state._energy = 0.30

    energies = [state.choose_scroll_mode(context="post")["energy"] for _ in range(6)]

    assert energies[-1] > energies[0]
    assert all(0.20 <= value <= 0.82 for value in energies)
    assert max(abs(right - left) for left, right in zip(energies, energies[1:])) < 0.08


def test_new_burst_reports_its_transition_context():
    state = BehaviorSessionState(seed=17)
    first = state.choose_scroll_mode(context="post")
    state._burst_remaining = 0

    next_burst = state.choose_scroll_mode(context="post")

    assert first["burst_started"] is True
    assert first["previous_style"] is None
    assert next_burst["burst_started"] is True
    assert next_burst["previous_style"] == first["style"]
    assert state.snapshot()["energy"] == next_burst["energy"]


def test_directional_gesture_consumes_the_same_session_burst():
    state = BehaviorSessionState(seed=27)
    vertical = state.choose_scroll_mode(context="feed_post")

    horizontal = state.plan_directional_gesture(
        context="carousel_slide", gesture="hswipe"
    )

    assert horizontal["index"] == vertical["index"] + 1
    assert horizontal["style"] == vertical["style"]
    assert horizontal["burst_remaining"] == max(0, vertical["burst_remaining"] - 1)
    assert horizontal["gesture"] == "hswipe"
    assert horizontal["drag_probability"] is None
    assert state.snapshot()["gesture_count"] == 2


def test_directional_gesture_is_seeded_and_strict_neutral():
    left = BehaviorSessionState(seed=45)
    right = BehaviorSessionState(seed=45)
    assert left.plan_directional_gesture(context="story_advance", gesture="tap") == (
        right.plan_directional_gesture(context="story_advance", gesture="tap")
    )

    strict = BehaviorSessionState(strict_regression=True)
    decision = strict.plan_directional_gesture(context="carousel_slide", gesture="hswipe")
    assert decision["energy"] == 0.52
    assert decision["distance_scale"] == 1.0
    assert decision["velocity_scale"] == 1.0
    assert decision["settle_scale"] == 1.0
    assert decision["dwell_scale"] == 1.0


def test_natural_bursts_keep_the_long_run_drag_baseline():
    state = BehaviorSessionState(seed=88, profile_id="natural")
    choices = [state.choose_scroll_mode(context="post") for _ in range(5000)]
    drag_ratio = sum(choice["mode"] == "drag" for choice in choices) / len(choices)

    assert 0.12 <= drag_ratio <= 0.18


def test_histories_are_bounded_in_ram():
    state = BehaviorSessionState(seed=3, history_limit=6)
    for _ in range(40):
        state.choose_scroll_mode(context="post")
        state.decide_post_framing(
            land_ratio=0.30,
            confidence=0.9,
            context="post",
            good_threshold=0.12,
        )

    assert len(state.gesture_history) == 6
    assert len(state.framing_history) == 6
    assert state.snapshot()["gesture_count"] == 40
    assert state.snapshot()["framing_count"] == 40


def test_higher_perception_confidence_increases_correction_probability():
    uncertain = BehaviorSessionState(seed=41)
    confident = BehaviorSessionState(seed=41)

    low = uncertain.decide_post_framing(
        land_ratio=0.34,
        confidence=0.2,
        context="post",
        good_threshold=0.12,
    )
    high = confident.decide_post_framing(
        land_ratio=0.34,
        confidence=0.95,
        context="post",
        good_threshold=0.12,
    )

    assert high["style"] == low["style"]
    assert high["probability"] > low["probability"]


def test_critical_misalignment_is_always_repaired():
    state = BehaviorSessionState(seed=9)
    decision = state.decide_post_framing(
        land_ratio=0.70,
        confidence=0.1,
        context="post",
        good_threshold=0.12,
    )

    assert decision["correct"] is True
    assert decision["probability"] == 1.0
    assert decision["reason"] == "critical_misalignment"
    assert 0.18 <= decision["reaction_delay_s"] <= 1.20
    assert 0.03 <= decision["target_ratio"] < 0.09


def test_profile_post_interaction_context_repairs_a_low_incoming_header():
    state = BehaviorSessionState(seed=19)

    decision = state.decide_post_framing(
        land_ratio=0.40,
        confidence=0.95,
        context="profile_post_header",
        good_threshold=0.12,
    )

    assert decision["correct"] is True
    assert decision["probability"] == 1.0
    assert decision["reason"] == "critical_misalignment"


def test_grid_entry_memory_avoids_the_last_successful_cell_on_same_profile():
    state = BehaviorSessionState(seed=5)
    keys = ["kevin:position:1", "kevin:position:2"]

    first = state.choose_grid_entry_index(context="kevin", candidate_keys=keys)
    state.remember_grid_entry(context="kevin", key=keys[first], index=first)
    second = state.choose_grid_entry_index(context="kevin", candidate_keys=keys)

    assert second != first
    assert state.snapshot()["recent_grid_entries"] == [
        {"context": "kevin", "key": keys[first], "index": first}
    ]


def test_grid_entry_memory_can_require_an_unseen_cell_for_reel_reentry():
    state = BehaviorSessionState(seed=5)
    keys = [f"kevin:position:{position}" for position in range(1, 5)]
    chosen = []

    for _ in keys:
        index = state.choose_grid_entry_index(
            context="kevin",
            candidate_keys=keys,
            avoid_recent=None,
            require_unseen=True,
        )
        assert index is not None
        assert index not in chosen
        chosen.append(index)
        state.remember_grid_entry(context="kevin", key=keys[index], index=index)

    assert state.choose_grid_entry_index(
        context="kevin",
        candidate_keys=keys,
        avoid_recent=None,
        require_unseen=True,
    ) is None


def test_strict_regression_keeps_framing_deterministic_and_immediate():
    state = BehaviorSessionState(strict_regression=True)
    decision = state.decide_post_framing(
        land_ratio=0.30,
        confidence=0.8,
        context="post",
        good_threshold=0.12,
    )

    assert decision["reason"] == "strict_regression"
    assert decision["correct"] is True
    assert decision["reaction_delay_s"] == 0.0
    assert decision["target_ratio"] == 0.05


def test_strict_regression_disables_motor_modulation():
    state = BehaviorSessionState(strict_regression=True)

    decision = state.choose_scroll_mode(context="post")

    assert decision["distance_scale"] == 1.0
    assert decision["velocity_scale"] == 1.0
    assert decision["settle_scale"] == 1.0
    assert decision["dwell_scale"] == 1.0
    assert state.snapshot()["motor_signature"] == {
        "reach": 1.0,
        "tempo": 1.0,
        "attention": 1.0,
    }
    assert decision["energy"] == 0.52


def test_reconfigure_keeps_an_active_sessions_history():
    state = BehaviorSessionState(seed=4, profile_id="natural")
    state.choose_scroll_mode(context="post")

    state.reconfigure(seed=999, strict_regression=False, profile_id="careful")

    snapshot = state.snapshot()
    assert snapshot["profile_id"] == "careful"
    assert snapshot["gesture_count"] == 1
    assert len(snapshot["recent_gestures"]) == 1


def test_reconfigure_to_strict_keeps_history_but_neutralizes_motor_scales():
    state = BehaviorSessionState(seed=4, profile_id="natural")
    state.choose_scroll_mode(context="post")

    state.reconfigure(seed=4, strict_regression=True, profile_id="strict_test")
    decision = state.choose_scroll_mode(context="post")

    assert state.snapshot()["gesture_count"] == 2
    assert decision["style"] == "steady"
    assert decision["distance_scale"] == 1.0
    assert decision["velocity_scale"] == 1.0
    assert decision["settle_scale"] == 1.0
    assert decision["dwell_scale"] == 1.0


def test_two_sessions_never_share_mutable_history():
    left = BehaviorSessionState(seed=1)
    right = BehaviorSessionState(seed=1)

    left.choose_scroll_mode(context="post")

    assert left.snapshot()["gesture_count"] == 1
    assert right.snapshot()["gesture_count"] == 0


def test_decisions_are_visible_on_existing_step_telemetry():
    metrics = []
    configure_telemetry_sink(metrics.append)
    try:
        state = BehaviorSessionState(seed=7)
        state.choose_scroll_mode(context="feed_post")
        state.decide_post_framing(
            land_ratio=0.25,
            confidence=0.8,
            context="feed_post",
            good_threshold=0.12,
        )
    finally:
        clear_telemetry_sink()

    assert [(metric.category, metric.action) for metric in metrics] == [
        ("behavior", "gesture_choice"),
        ("behavior", "framing_decision"),
    ]
