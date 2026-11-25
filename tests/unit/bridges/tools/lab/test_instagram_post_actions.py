from types import SimpleNamespace

from bridges.tools.lab.actions.instagram.post import (
    navigate_next,
    read_stats,
    return_to_profile,
    return_to_grid_and_reopen,
)


def test_read_stats_uses_production_extractors():
    calls = []
    extractors = SimpleNamespace(
        extract_likes_count_from_ui=lambda **kwargs: (
            calls.append(("likes", kwargs)) or 123
        ),
        extract_comments_count_from_ui=lambda **kwargs: (
            calls.append(("comments", kwargs)) or 4
        ),
    )

    result = read_stats(
        SimpleNamespace(like=SimpleNamespace(ui_extractors=extractors)),
        {"is_reel": False},
    )

    assert result["details"] == {"likes": 123, "comments": 4, "is_reel": False}
    assert calls == [
        ("likes", {"is_reel": False}),
        ("comments", {"is_reel": False}),
    ]


def test_navigate_next_exposes_profile_viewer_session_memory():
    class _Scroll:
        _last_advance_behavior = {
            "mode": "drag",
            "style": "deliberate",
            "burst_remaining": 2,
            "energy": 0.37,
        }

        @staticmethod
        def _behavior_snapshot():
            return {"style": "deliberate", "gesture_count": 5}

    like = SimpleNamespace(
        scroll_actions=_Scroll(),
        _navigate_to_next_post_in_sequence=lambda: True,
    )

    result = navigate_next(SimpleNamespace(like=like), {})

    assert result["success"] is True
    assert "style=deliberate" in result["message"]
    assert "energy=0.37" in result["message"]
    assert result["details"]["advance_decision"]["mode"] == "drag"
    assert result["details"]["behavior_state"]["gesture_count"] == 5


def test_return_to_grid_and_reopen_uses_the_combined_production_sequence():
    calls = []
    scroll = SimpleNamespace(
        _last_behavior_gesture={"style": "steady", "energy": 0.51}
    )
    like = SimpleNamespace(
        scroll_actions=scroll,
        _return_to_grid_and_open_another_post=lambda count, username=None: (
            calls.append((count, username)) or True
        ),
        _behavior_state_snapshot=lambda: {"gesture_count": 7},
    )

    result = return_to_grid_and_reopen(
        SimpleNamespace(like=like), {"posts_count": "24", "username": "kevin"}
    )

    assert calls == [(24, "kevin")]
    assert result["success"] is True
    assert result["details"]["behavior_state"]["gesture_count"] == 7


def test_return_to_profile_propagates_observed_navigation_failure():
    like = SimpleNamespace(
        scroll_actions=SimpleNamespace(_last_behavior_gesture={"style": "steady"}),
        _return_to_profile_from_post=lambda: False,
        _behavior_state_snapshot=lambda: {"gesture_count": 2},
    )

    result = return_to_profile(SimpleNamespace(like=like), {})

    assert result["success"] is False
    assert "returned to profile=False" in result["message"]


def test_check_excluded_terms_runs_the_production_check_on_the_framed_post(monkeypatch):
    import pytest

    import taktik.core.social_media.instagram.actions.base.base_business.term_exclusion as term_exclusion
    from bridges.tools.lab.actions.instagram.post import check_excluded_terms

    monkeypatch.setattr(term_exclusion.IPCEmitter, "emit_term_exclusion", staticmethod(lambda *a: None))
    framed = {"author": "lea_photo", "header_desc": "lea_photo a publié une photo", "reframed": True,
              "caption_text": "lea_photo Atelier Zorvak ce matin", "post_ends_on_screen": True}
    like = SimpleNamespace(scroll_actions=SimpleNamespace(read_framed_caption=lambda: framed),
                           logger=SimpleNamespace(info=lambda *a: None, warning=lambda *a: None))

    found = check_excluded_terms(SimpleNamespace(like=like), {"post_terms": "brindille, zorvak"})
    clear = check_excluded_terms(SimpleNamespace(like=like), {"post_terms": "brindille"})

    assert found["details"]["reason"] == "post_excluded_term" and found["details"]["term"] == "zorvak"
    assert clear["details"]["allowed"] is True
    with pytest.raises(ValueError):
        check_excluded_terms(SimpleNamespace(like=like), {})
