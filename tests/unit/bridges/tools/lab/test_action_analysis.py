from bridges.tools.lab.action_test.analysis import (
    build_action_analysis,
    expected_screen_after,
)


def test_profile_post_navigation_actions_declare_their_expected_screens():
    assert expected_screen_after("post.navigate_next") == "instagram.post"
    assert expected_screen_after("post.return_to_profile") == "instagram.profile"
    assert expected_screen_after("post.return_to_grid_and_reopen") == "instagram.post"


def test_home_profile_surface_misses_are_screen_disambiguation_not_context_gate():
    report = {
        "runId": "detection.get_current_screen_20260602T153659000Z",
        "action": {"id": "detection.get_current_screen"},
        "result": {"success": True},
        "screens": {"before": "instagram.home", "after": "instagram.home"},
        "selectorTraces": [
            {
                "xpath": '//*[@resource-id="com.instagram.android:id/feed_tab" and @selected="true"]',
                "found": True,
                "screen": "instagram.home",
                "family": "detection",
                "elapsedMs": 300,
            },
            {
                "xpath": '//*[@resource-id="com.instagram.android:id/row_profile_header"]',
                "found": False,
                "screen": "instagram.home",
                "family": "detection",
                "elapsedMs": 600,
            },
            {
                "xpath": '//*[@resource-id="com.instagram.android:id/row_profile_header"]',
                "found": False,
                "screen": "instagram.home",
                "family": "detection",
                "elapsedMs": 550,
            },
        ],
    }

    analysis = build_action_analysis(report)
    row_profile_header = next(
        item for item in analysis["recommendations"]
        if item["xpath"] == '//*[@resource-id="com.instagram.android:id/row_profile_header"]'
    )

    assert analysis["verdict"] == "pass"
    assert row_profile_header["recommendation"] == "watch"
    assert row_profile_header["severity"] == "info"
    assert row_profile_header["reason"] == "screen_disambiguation_negative_probe"


def test_a_detection_answering_no_is_not_a_screen_it_failed_to_reach():
    # A detection moves nothing: its "no" (a success since a no is an answer) on the feed is not
    # "succeeded but ended on the feed instead of a post".
    report = {
        "runId": "detection.is_post_open_20260928T000000000Z",
        "action": {"id": "detection.is_post_open"},
        "result": {"success": True},
        "screens": {"before": "instagram.home", "after": "instagram.home"},
        "selectorTraces": [],
    }

    analysis = build_action_analysis(report)

    assert expected_screen_after("detection.is_post_open") is None
    assert analysis["transition"]["ok"] is None
    assert analysis["verdict"] == "pass"
    assert analysis["notes"] == []
