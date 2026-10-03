from types import SimpleNamespace

from bridges.tools.lab.actions.instagram.profile import scroll_grid


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
    from bridges.tools.lab.actions.instagram.profile import get_account_flags

    calls = []
    detection = SimpleNamespace(
        get_profile_flags_batch=lambda: calls.append("production")
        or {"is_private": False, "is_verified": True, "is_business": True},
    )

    result = get_account_flags(SimpleNamespace(detection=detection), {})

    assert calls == ["production"]
    assert result["success"] is True
    assert result["details"] == {"is_private": False, "is_verified": True, "is_business": True}


def _grid_key(position):
    return f"current-profile:position:{position}"


def _lab_like_with_grid_memory(opened_before, entry_position):
    """The Lab's like orchestration on a session grid memory where the earlier tests of the run
    opened `opened_before`; its production entry (stubbed: no phone) records the memory it starts
    from, then opens `entry_position` as the real one remembers a cell that opened."""
    from taktik.core.shared.behavior.session_state import BehaviorSessionState

    state = BehaviorSessionState(seed=7)
    for position in opened_before:
        state.remember_grid_entry(context="current-profile", key=_grid_key(position), index=position - 1)
    memory_at_entry = []

    def production_entry(posts_count, posts_to_inspect=0):
        memory_at_entry.append([item["key"] for item in state.grid_entry_history])
        state.remember_grid_entry(
            context="current-profile", key=_grid_key(entry_position), index=entry_position - 1
        )
        return True

    like = SimpleNamespace(behavior_state=state, _open_entry_post_of_profile=production_entry)
    return like, state, memory_at_entry


def test_the_reopen_preparation_opens_the_entry_on_a_forgotten_grid_memory():
    """`post.return_to_grid_and_reopen` resumes past the furthest post, among the cells the session
    never opened. On the 3a (2026-09-30, `verif4`), the earlier profile tests had opened #2, #1, #5
    and #6, its preparation opened #4, and only #5 and #6 were on screen past it: no cell left, the
    test red by the draws of the tests before it. Its preparation now forgets the grid memory first."""
    from bridges.tools.lab.actions.instagram.profile import open_entry_post

    like, state, memory_at_entry = _lab_like_with_grid_memory([2, 1, 5, 6], entry_position=4)

    result = open_entry_post(SimpleNamespace(like=like), {"forget_grid_memory": True})

    assert result["success"] is True
    assert memory_at_entry == [[]]
    reopen = state.choose_grid_entry_index(
        context="current-profile",
        candidate_keys=[_grid_key(5), _grid_key(6)],
        avoid_recent=None,
        require_unseen=True,
    )
    assert reopen is not None


def test_the_entry_keeps_the_session_grid_memory_unless_asked():
    """The production entry avoids the cells the session already opened: a run of the Lab action
    without the preparation's value keeps that memory, as the production does."""
    from bridges.tools.lab.actions.instagram.profile import open_entry_post

    like, _state, memory_at_entry = _lab_like_with_grid_memory([2, 1], entry_position=3)

    open_entry_post(SimpleNamespace(like=like), {})

    assert memory_at_entry == [[_grid_key(2), _grid_key(1)]]
