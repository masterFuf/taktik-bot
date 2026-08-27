"""The `follow_actor` verb: follow whoever engaged with one of our comments.

The verb exists because the signal is the strongest the activity feed carries — we wrote the
comment, they reacted to it. What has to hold is the opposite of enthusiasm: this is a REAL
follow, aimed at someone we have never checked, from a row that offers no inline button.

- the relationship is read on the profile BEFORE anything is tapped, and every state that
  means "already related" steps back;
- an UNREADABLE state steps back too. `follow_user` is not guarded internally, so tapping
  blind on a profile we already follow would UNFOLLOW it -- the cost of being wrong is not
  symmetrical here, unlike the read-only skip paths that fail open;
- a step-back is a SKIP, never a success: counting it as done would inflate the run, and
  recording it would spend a slot of the daily cap on an action that never happened.
"""

import pytest

import bridges.instagram.engagement.runtime.notifications.commands as commands
import bridges.instagram.engagement.runtime.notifications.follow_actor as follow_actor


class _Clicks:
    """Stands in for the production ClickActions facade."""

    def __init__(self, state, follow_ok=True):
        self.state = state
        self.follow_ok = follow_ok
        self.followed = []

    def get_follow_button_state(self):
        return self.state

    def follow_user(self, username):
        self.followed.append(username)
        return self.follow_ok


class _Nav:
    def __init__(self, can_open=True):
        self.can_open = can_open
        self.opened = []
        self.went_home = 0

    def navigate_to_profile(self, username):
        self.opened.append(username)
        return self.can_open

    def navigate_to_home(self):
        self.went_home += 1
        return True


@pytest.fixture
def screen(monkeypatch):
    """Intercept the two production facades the verb composes."""
    state = {"clicks": _Clicks('follow'), "nav": _Nav()}

    import taktik.core.social_media.instagram.actions.atomic.interaction as interaction
    import taktik.core.social_media.instagram.actions.atomic.navigation as navigation

    monkeypatch.setattr(interaction, "ClickActions", lambda device: state["clicks"])
    monkeypatch.setattr(navigation, "NavigationActions", lambda device: state["nav"])
    return state


# ---------------------------------------------------------------------------
# The relationship read is the guard
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("state", ["following", "requested", "message"])
def test_an_existing_relationship_is_left_alone(screen, state):
    screen["clicks"] = _Clicks(state)

    result = follow_actor.follow_actor(object(), "someone")

    assert result["skipped"] is True
    assert result["reason"] == state
    assert screen["clicks"].followed == []


def test_an_unreadable_relationship_is_left_alone(screen):
    # Fail-CLOSED, on purpose: follow_user is unguarded, so a blind tap on a profile we
    # already follow would unfollow it.
    screen["clicks"] = _Clicks('unknown')

    result = follow_actor.follow_actor(object(), "someone")

    assert result["skipped"] is True
    assert result["reason"] == "unknown_state"
    assert screen["clicks"].followed == []


@pytest.mark.parametrize("state", ["follow", "follow_back"])
def test_no_relationship_or_they_follow_us_gets_followed(screen, state):
    screen["clicks"] = _Clicks(state)

    result = follow_actor.follow_actor(object(), "someone")

    assert result["success"] is True
    assert result.get("skipped") is not True
    assert screen["clicks"].followed == ["someone"]


def test_a_profile_that_will_not_open_is_a_failure_not_a_skip(screen):
    screen["nav"] = _Nav(can_open=False)

    result = follow_actor.follow_actor(object(), "someone")

    assert result["success"] is False
    assert screen["clicks"].followed == []


def test_the_feed_is_always_walked_back_to(screen):
    screen["clicks"] = _Clicks('following')

    follow_actor.follow_actor(object(), "someone")

    # Even on a skip: the next entry reaches its profile through the search tab, which does
    # not exist on someone else's profile page.
    assert screen["nav"].went_home == 1


def test_an_empty_username_never_opens_anything(screen):
    result = follow_actor.follow_actor(object(), "   ")

    assert result["success"] is False
    assert screen["nav"].opened == []


# ---------------------------------------------------------------------------
# What the batch does with a step-back
# ---------------------------------------------------------------------------

class _Bridge:
    def __init__(self):
        self.device = object()

    def connect(self):
        return True

    def restart_instagram(self):
        pass

    def build_workflow(self):
        return object()


@pytest.fixture
def batch(monkeypatch):
    audit = []
    monkeypatch.setattr(commands, "NotificationsBridge", lambda *a, **k: _Bridge())
    monkeypatch.setattr(commands, "emit_notif_json", lambda *a, **k: None)
    monkeypatch.setattr(commands, "load_actioned_hashes", lambda *a, **k: set())
    monkeypatch.setattr(commands, "batch_identity_hash", lambda *a, **k: None)
    monkeypatch.setattr(commands, "count_actions_today", lambda *a, **k: 0)
    monkeypatch.setattr(commands, "resolve_account_id", lambda *a, **k: 7)
    monkeypatch.setattr(commands, "wait_before_next_off_screen_action", lambda **k: None)
    monkeypatch.setattr(
        commands, "record_notification_action",
        lambda account, **kwargs: audit.append((kwargs.get("action"), kwargs.get("actor_username"))))
    return {"audit": audit}


def test_a_step_back_is_not_recorded_and_does_not_spend_the_cap(batch, monkeypatch):
    # Two entries, a cap of one: if the first one's step-back counted, the second would
    # never be attempted.
    seen = []

    def _follow(device, username):
        seen.append(username)
        if username == "related":
            return {"success": True, "skipped": True, "reason": "following"}
        return {"success": True}

    monkeypatch.setattr(commands, "follow_actor", _follow)

    commands.cmd_batch("device-1", [
        {"action": "follow_actor", "username": "related"},
        {"action": "follow_actor", "username": "fresh"},
    ], account_username="me", follow_actor_daily_cap=1)

    assert seen == ["related", "fresh"]
    # Only the follow that happened is on the trail — and so in the follow budget.
    assert batch["audit"] == [("follow_actor", "fresh")]


def test_the_daily_cap_bites_on_the_follows_that_land(batch, monkeypatch):
    monkeypatch.setattr(commands, "follow_actor", lambda device, username: {"success": True})

    commands.cmd_batch("device-1", [
        {"action": "follow_actor", "username": "a"},
        {"action": "follow_actor", "username": "b"},
        {"action": "follow_actor", "username": "c"},
    ], account_username="me", follow_actor_daily_cap=2)

    assert [u for _, u in batch["audit"]] == ["a", "b"]
