"""The bounds of the settings: declared once, refused by the reader before the phone is touched.

A setting's bounds (`Field.bounds`) are the ones the app's pages write for it. Each reader of a
declared workflow refuses a value outside them first (`contract/bounds.py`, its checker held in
`test_workflow_contract_bounds_checker.py`), so a launcher never reaches the phone with a value no
page could have sent. These tests hold:
- every declared bound: it fits its setting, its default lies inside it, its condition names
  declared settings;
- the Instagram bounds against the record of what the pages wrote (TikTok declares none: 2.x);
- every declared bound through its launcher: a value past either end refused before the phone, the
  ends themselves accepted by the reader;
- every declared bound through `taktik workflows run`: refused with nothing connected.
"""

from __future__ import annotations

import json

import pytest

from contract_probe import DEVICE, conditions, launch, merge, nest, payload_for, read
from taktik.core.contract import WORKFLOW_CONTRACTS
from taktik.core.contract.bounds import describe, out_of_bounds
from taktik.core.contract.instagram_agent import INSTAGRAM_TAKTIK_AGENT
from taktik.core.contract.instagram_automation import INSTAGRAM_AUTOMATION
from taktik.core.contract.instagram_scraping import INSTAGRAM_SCRAPING
from taktik.core.contract.schema import (
    HOST,
    Bounds,
    Field,
    ListOf,
    OneOf,
    Shape,
    WorkflowContract,
    has_default,
    nested_fields,
    scalar_default,
)

# ------------------------------------------------------------------------------------ the declarations


def _bounded_settings(contract: WorkflowContract):
    for path, item, when, _ in nested_fields(contract.settings):
        if item.bounds is not None:
            yield ".".join(path), item, when


BOUNDED = [
    pytest.param(contract, path, item, when, id=f"{contract.workflow_id}:{path}")
    for contract in WORKFLOW_CONTRACTS
    for path, item, when in _bounded_settings(contract)
]


def _numeric(item: Field) -> bool:
    return item.type in ("int", "number")


@pytest.mark.parametrize("contract, path, item, when", BOUNDED)
def test_a_bound_fits_its_setting(contract, path, item, when):
    bounds = item.bounds
    numbers = (bounds.minimum, bounds.maximum, bounds.unbounded_at)
    items = (bounds.min_items, bounds.max_items)
    texts = item.type == "string" or item.type == ListOf("string")
    assert any(value is not None for value in (*numbers, *items, bounds.max_length)), "empty bounds"
    if any(value is not None for value in numbers):
        assert _numeric(item), "a number's bounds on a setting that is no number"
    if any(value is not None for value in items):
        assert isinstance(item.type, ListOf), "a list's bounds on a setting that is no list"
    if bounds.max_length is not None:
        assert texts, "a text's bound on a setting that holds no text"
    if bounds.minimum is not None and bounds.maximum is not None:
        assert bounds.minimum <= bounds.maximum
    if bounds.min_items is not None and bounds.max_items is not None:
        assert bounds.min_items <= bounds.max_items
    assert item.by != HOST, "the host fills it: no page bounds it"


@pytest.mark.parametrize("contract, path, item, when", BOUNDED)
def test_the_bots_default_lies_inside_its_bounds(contract, path, item, when):
    if not has_default(item):
        pytest.skip("no default")
    if scalar_default(item):
        assert out_of_bounds(contract, _payload(contract, item, path, when, item.default)) == []


@pytest.mark.parametrize("contract, path, item, when", BOUNDED)
def test_the_condition_of_a_bound_names_declared_settings(contract, path, item, when):
    for dotted, wanted in item.bounds.when.items():
        fields, setting = contract.settings, None
        for part in dotted.split("."):
            setting = next((sub for sub in fields if sub.key == part), None)
            assert setting is not None, f"{dotted} is not a declared setting"
            fields = setting.type.fields if isinstance(setting.type, Shape) else ()
        if isinstance(setting.type, OneOf):
            for value in wanted if isinstance(wanted, tuple) else (wanted,):
                assert setting.type.allows(value), f"{dotted} never takes {value!r}"


# ------------------------------------------------------------------------------------ what the pages wrote

#: The profile and feed runs, whose pages set `limits.maxProfiles` (the Unfollow page sets the same value
#: through `unfollow.maxUnfollows`, bounded there; the list syncs send 0 and set nothing).
_PROFILE_PAGES = ("target_followers", "target_following", "target_profiles", "hashtags", "post_url", "feed")
_PERCENT = Bounds(minimum=0, maximum=100)
_AT_LEAST_0 = Bounds(minimum=0)

#: The bounds the app's Instagram pages wrote on 2026-10-18, setting by setting; the Taktik Agent has
#: no page, the form of its scheduler node stands for it. A bound changes with its page, here first.
INSTAGRAM_PAGE_BOUNDS = {
    "instagram.automation.target_followers": {
        # Target, Hashtag, Post likers: profiles to interact with; Feed: posts to see.
        "limits.maxProfiles": Bounds(minimum=1, maximum=500, when={"workflowType": _PROFILE_PAGES}),
        "limits.minLikesPerProfile": Bounds(minimum=0, maximum=20),
        "limits.maxLikesPerProfile": Bounds(minimum=0, maximum=20),
        # The raw percentages under the intentions.
        "probabilities.like": _PERCENT,
        "probabilities.follow": _PERCENT,
        "probabilities.comment": _PERCENT,
        "probabilities.watchStories": _PERCENT,
        "probabilities.likeStories": _PERCENT,
        "probabilities.feedStoryReaction": _PERCENT,
        "filters.minFollowers": _AT_LEAST_0,
        "filters.maxFollowers": _AT_LEAST_0,
        "filters.minPosts": _AT_LEAST_0,
        "filters.maxFollowing": _AT_LEAST_0,
        "filters.maxConsecutivePrivateProfiles": Bounds(minimum=0, maximum=50),
        # The likes rail of a feed post: a threshold typed past its end is kept.
        "filters.minPostLikes": _AT_LEAST_0,
        "filters.maxPostLikes": _AT_LEAST_0,
        "session.durationMinutes": Bounds(minimum=5, maximum=600),
        "session.maxConsecutiveKnownUsernames": Bounds(minimum=1, maximum=1000),
        "feedStories.maxProfiles": Bounds(minimum=1, maximum=20),
        "feed.maxLikersPerPost": Bounds(minimum=1),
        "feed.maxSuggestionFollows": Bounds(minimum=0, maximum=100),
        "unfollow.maxUnfollows": Bounds(minimum=1, maximum=200),
        "unfollow.minDelay": Bounds(minimum=1, maximum=120),
        "unfollow.maxDelay": Bounds(minimum=1, maximum=120),
        "unfollow.minDaysSinceFollow": Bounds(minimum=0, maximum=30),
        "postCriteria.minLikes": _AT_LEAST_0,
        "postCriteria.maxLikes": _AT_LEAST_0,
        "maxPosts": Bounds(minimum=1, maximum=100),
        "maxLikersPerPost": Bounds(minimum=1, maximum=200),
        "maxCommentersPerPost": Bounds(minimum=1, maximum=200),
        "max_comment_likes": Bounds(minimum=1, maximum=50),
        "max_comment_replies": Bounds(minimum=1, maximum=20),
        "ai.relevanceGating.minScore": Bounds(minimum=0, maximum=1),
    },
    "instagram.scraping.target": {
        "sessionDurationMinutes": Bounds(minimum=5, maximum=600),
        # The page's ceiling, which its follower estimate and its cell hold.
        "maxProfiles": Bounds(minimum=1, maximum=10000),
        "minFollowers": _AT_LEAST_0,
        "minFollowing": _AT_LEAST_0,
        "minPosts": _AT_LEAST_0,
        "maxFollowers": _AT_LEAST_0,
        "maxFollowing": _AT_LEAST_0,
        "deepQualifyMaxFollowing": Bounds(minimum=10, maximum=500),
        "maxPosts": Bounds(minimum=1, maximum=200),
        "maxPostsPerTarget": Bounds(minimum=1, maximum=200),
    },
    "instagram.engagement.coldDm": {
        "delayMin": Bounds(minimum=5, maximum=600),
        "delayMax": Bounds(minimum=5, maximum=600),
        "maxDmsPerSession": Bounds(minimum=1, maximum=100),
    },
    "instagram.engagement.dm_read": {
        # 1 to 50 conversations, or 0 when every conversation is read.
        "limit": Bounds(minimum=1, maximum=50, unbounded_at=0),
    },
    "instagram.engagement.notifications": {
        "followSuggestions": Bounds(minimum=0, maximum=50),
        "followBackDailyCap": Bounds(minimum=1, maximum=30),
        "welcomeDmDailyCap": Bounds(minimum=1, maximum=30),
        "followActorDailyCap": Bounds(minimum=1, maximum=30),
    },
    "instagram.engagement.taktik_agent": {
        "max_likes": _AT_LEAST_0,
        "max_comments": _AT_LEAST_0,
        "max_follows": _AT_LEAST_0,
        "max_profile_visits": _AT_LEAST_0,
        "max_posts_seen": _AT_LEAST_0,
        "session_duration_min": Bounds(minimum=1),
    },
}


@pytest.mark.parametrize("contract", [pytest.param(c, id=c.workflow_id) for c in WORKFLOW_CONTRACTS])
def test_the_declared_bounds_are_the_ones_the_pages_wrote(contract):
    declared = {path: item.bounds for path, item, _ in _bounded_settings(contract)}
    # TikTok, Threads, the accounts, the publications: no bound yet (TikTok's in 2.x).
    assert declared == INSTAGRAM_PAGE_BOUNDS.get(contract.workflow_id, {})


# ------------------------------------------------------------------------------------ through the launcher


def _step(item: Field) -> float:
    return 1 if item.type == "int" else 0.5


def _past(item: Field, end: float, direction: int) -> float:
    """A value one step past `end`, never the one that says no limit."""
    value = end + direction * _step(item)
    if item.bounds.unbounded_at is not None and value == item.bounds.unbounded_at:
        value += direction * _step(item)
    return int(value) if item.type == "int" else value


def _payload(contract: WorkflowContract, item: Field, path: str, when, value):
    at = merge(conditions(when), conditions(item.bounds.when))
    return payload_for(contract, merge(at, nest(tuple(path.split(".")), value)))


def _ends(item: Field):
    bounds = item.bounds
    return [(end, direction) for end, direction in ((bounds.minimum, -1), (bounds.maximum, 1)) if end is not None]


NUMBER_BOUNDS = [param for param in BOUNDED if _numeric(param.values[2])]


@pytest.mark.parametrize("contract, path, item, when", NUMBER_BOUNDS)
def test_the_launcher_refuses_a_value_past_either_end_before_the_phone(contract, path, item, when):
    for end, direction in _ends(item):
        value = _past(item, end, direction)
        # Without a device nor a connection: a launcher that reached for the phone would fail
        # otherwise than with the reader's refusal.
        with pytest.raises(ValueError) as refused:
            launch(contract, _payload(contract, item, path, when, value))
        message = str(refused.value)
        assert message.startswith("Refused before the phone is touched: "), message
        assert f"{path} = " in message and describe(item.bounds) in message, message


def _cli_run(contract: WorkflowContract, payload: dict) -> tuple[str, dict]:
    """The id and the parameters of `taktik workflows run` for this payload: the id its selector names
    (the CLI's handler sets the selector from the id), and a target for a run that requires one."""
    workflow_id = contract.workflow_id
    if contract.selector and payload.get(contract.selector) is not None:
        named = f"{workflow_id.rsplit('.', 1)[0]}.{payload[contract.selector]}"
        workflow_id = named if named in contract.serves else workflow_id
    return workflow_id, {"target": "someone", **payload}


@pytest.mark.parametrize("contract, path, item, when", NUMBER_BOUNDS)
def test_the_cli_refuses_a_value_past_either_end_before_it_connects(contract, path, item, when, monkeypatch):
    """`taktik workflows run` chooses its phone without connecting it; the launcher reads, validates,
    then asks for it. A value no page could send ends with exit 1, and the CLI connected nothing."""
    from click.testing import CliRunner

    from taktik.cli.commands import workflows as workflow_cmds
    from taktik.cli.hosts.phone import CliPhone
    from unit.cli_phone import recording_device_manager

    connections = []
    monkeypatch.setattr(workflow_cmds, "_choose_phone",
                        lambda _device_id: CliPhone(recording_device_manager(connections, DEVICE)(), DEVICE))
    for end, direction in _ends(item):
        workflow_id, params = _cli_run(contract, _payload(contract, item, path, when, _past(item, end, direction)))
        result = CliRunner().invoke(workflow_cmds.workflows, ["run", workflow_id, "--json", json.dumps(params)],
                                    env={"OPENROUTER_API_KEY": "sk-or-v1-" + "0" * 48})

        assert result.exit_code == 1, result.output
        assert "Refused before the phone is touched" in " ".join(result.output.split()), result.output
    assert connections == []


@pytest.mark.parametrize("contract, path, item, when", NUMBER_BOUNDS)
def test_the_reader_accepts_the_ends_themselves(contract, path, item, when):
    bounds = item.bounds
    for value in (bounds.minimum, bounds.maximum, bounds.unbounded_at):
        if value is not None:
            read(contract, _payload(contract, item, path, when, int(value) if item.type == "int" else value))


def test_a_list_sync_sends_no_profile_budget_and_is_not_held_to_one():
    # The Unfollow and account pages send `maxProfiles: 0` with a sync: no page bounds it there.
    sync = {"workflowType": "sync_following", "target": "auto", "limits": {"maxProfiles": 0}}
    assert out_of_bounds(INSTAGRAM_AUTOMATION, sync) == []
    target = {**sync, "workflowType": "target_followers", "target": "someone"}
    assert out_of_bounds(INSTAGRAM_AUTOMATION, target) == [
        "limits.maxProfiles = 0, outside its bounds (1 to 500)"]


def test_an_automation_out_of_bounds_is_refused_before_the_host_connects():
    connected = []
    payload = {"workflowType": "target_followers", "target": "someone", "limits": {"maxProfiles": 501}}

    with pytest.raises(ValueError, match="limits.maxProfiles = 501"):
        launch(INSTAGRAM_AUTOMATION, payload, connect=lambda package: connected.append(package))
    assert connected == []


def test_a_scraping_out_of_bounds_or_with_no_source_is_refused_before_the_host_connects():
    connected = []
    out_of_bounds_run = {"type": "usernames", "usernames": ["alpha"], "maxProfiles": 10001}
    no_source = {"type": "hashtag", "hashtags": []}

    with pytest.raises(ValueError, match="maxProfiles = 10001"):
        launch(INSTAGRAM_SCRAPING, out_of_bounds_run, connect=lambda package: connected.append(package))
    with pytest.raises(ValueError, match="requires hashtags"):
        launch(INSTAGRAM_SCRAPING, no_source, connect=lambda package: connected.append(package))
    assert connected == []


def test_a_taktik_agent_out_of_bounds_says_why_on_stdout_before_connecting():
    class Ipc:
        def __init__(self):
            self.errors = []

        def error(self, message, error_code=None):
            self.errors.append(message)

    ipc = Ipc()
    connected = []
    payload = {"max_likes": -1, "openrouter_api_key": "sk-probe"}

    with pytest.raises(ValueError):
        launch(INSTAGRAM_TAKTIK_AGENT, payload, ipc=ipc, connect=lambda package: connected.append(package))
    assert connected == []
    assert ipc.errors == ["Refused before the phone is touched: max_likes = -1, outside its bounds (at least 0)"]
