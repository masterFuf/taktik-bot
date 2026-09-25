from types import SimpleNamespace

from bridges.compat.diagnostics.actions.instagram.profile import scroll_grid


def test_scroll_grid_uses_production_action_and_exposes_session_state():
    calls = []
    scroll = SimpleNamespace(
        scroll_post_grid_down=lambda: calls.append("production") or True,
        _last_behavior_gesture={"style": "brisk", "energy": 0.68},
        _behavior_snapshot=lambda: {"gesture_count": 6},
    )

    result = scroll_grid(SimpleNamespace(scroll=scroll), {})

    assert calls == ["production"]
    assert result["success"] is True
    assert result["details"]["gesture_decision"]["style"] == "brisk"
    assert result["details"]["behavior_state"]["gesture_count"] == 6


def test_account_flags_come_from_the_production_batch_read():
    from bridges.compat.diagnostics.actions.instagram.profile import get_account_flags

    calls = []
    detection = SimpleNamespace(
        get_profile_flags_batch=lambda: calls.append("production")
        or {"is_private": False, "is_verified": True, "is_business": True},
    )

    result = get_account_flags(SimpleNamespace(detection=detection), {})

    assert calls == ["production"]
    assert result["success"] is True
    assert result["details"] == {"is_private": False, "is_verified": True, "is_business": True}
