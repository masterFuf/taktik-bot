"""What the TikTok contracts declare beyond one bridge: the lines of the session start and of the
AI (provider verdict, its copy for the base, the engagement verdict), the keys of the `ai` block,
the rows the inbox screen readers build.

Each is held to the code that produces or reads it, on its real path: the session start with its
phone replaced, the AI provider with its network replaced, the bridge's AI hooks and the welcome
pass's qualifier with only the network and the screenshot replaced, the readers of the `ai` block,
and the dict literals the screen readers and the inbox workflow write.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from contract_probe import Recording
from taktik.core.contract import WORKFLOW_CONTRACTS
from taktik.core.contract.schema import Field, Shape
from taktik.core.contract.shared import AI_SPEND_EVENT
from taktik.core.contract.tiktok_automation import AI_BLOCK
from taktik.core.contract.tiktok_lines import AI_PROFILE_DONE_EVENT, AI_RELEVANCE_EVENT, BOT_PROFILE_EVENT
from unit.paths import CORE

_TIKTOK = CORE / "taktik/core/social_media/tiktok"


@pytest.fixture
def lines(monkeypatch):
    from bridges.common.ipc import IPC

    printed: List[Dict[str, Any]] = []
    monkeypatch.setattr(IPC, "send", lambda self, msg_type, **kwargs: printed.append({"type": msg_type, **kwargs}))
    return printed


def _problems(fields, data):
    from test_workflow_contract_bridges import problems_of

    return problems_of(fields, data)


def _conforms(event, printed):
    matching = [line for line in printed if line["type"] == event.type]
    assert matching, f"no `{event.type}` printed"
    for line in matching:
        json.dumps(line)
        assert not _problems(event.fields, line), (line, _problems(event.fields, line))


# ------------------------------------------------------------------------ session start


def test_bot_profile_is_what_the_session_start_prints(monkeypatch, lines):
    import taktik.core.social_media.tiktok.actions.business.actions.profile_actions as profile_actions
    from bridges.tiktok.common.ipc import _ipc
    from taktik.core.social_media.tiktok.workflows.runtime import startup

    own = profile_actions.TikTokProfileInfo(username="acting", display_name="Acting", following_count=3,
                                            followers_count=12, likes_count=40, bio=None,
                                            profile_pic_base64="data:image/jpeg;base64,AAAA")
    monkeypatch.setattr(profile_actions.ProfileActions, "__init__", lambda self, device: None)
    monkeypatch.setattr(profile_actions.ProfileActions, "fetch_own_profile", lambda self: own)
    screen = SimpleNamespace(xpath=lambda selector: SimpleNamespace(exists=True))
    manager = SimpleNamespace(restart=lambda: True, device_id="emulator-5554",
                              device_manager=SimpleNamespace(device=screen))

    assert startup.start_tiktok_session(manager, notifier=_ipc, fetch_profile=True) == "acting"

    _conforms(BOT_PROFILE_EVENT, lines)


def test_every_tiktok_app_reader_of_bot_profile_has_it_declared():
    declared = {c.workflow_id for c in WORKFLOW_CONTRACTS if any(e is BOT_PROFILE_EVENT for e in c.events)}
    # The dispatcher's workflows whose stdout readers read `bot_profile`.
    assert {
        "tiktok.automation.for_you", "tiktok.automation.hashtag", "tiktok.automation.followers",
        "tiktok.automation.target_profiles", "tiktok.automation.post_url", "tiktok.automation.sync_lists",
        "tiktok.automation.dm_read", "tiktok.automation.dm_send", "tiktok.automation.new_followers",
        "tiktok.automation.dm_unreplied", "tiktok.automation.dm_requests", "tiktok.automation.dm_activity",
        "tiktok.automation.notifications",
    } <= declared


# ---------------------------------------------------------------------------- AI provider


class _Answer:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


_KEY = "sk-or-" + "x" * 48


def _scripted_provider(monkeypatch, tmp_path) -> None:
    """The profile's screenshot and the model's answer: all the AI path touches outside the bot."""
    from PIL import Image

    from taktik.core.social_media.tiktok.workflows.core import ai_hooks

    shot = tmp_path / "profile.png"
    Image.new("RGB", (40, 80), (30, 30, 30)).save(shot)
    monkeypatch.setattr(ai_hooks, "_screenshot_for_ai", lambda device, name, log=None: str(shot))
    verdict = {"niche": "Cooking", "niche_category": "food_drink", "summary": "Recipes.", "language": "en",
               "engagement": {"relevant": True, "score": 72, "reason": "Close niche", "follow": True,
                              "comment": False, "like": True}}

    def answer(request, *_args, **_kwargs):
        body = json.loads(request.data.decode("utf-8"))
        return _Answer({"choices": [{"message": {"content": json.dumps(verdict)}, "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.0002},
                        "model": body["model"]})

    monkeypatch.setattr("urllib.request.urlopen", answer)


def test_ai_profile_done_is_what_the_provider_prints(monkeypatch, lines, tmp_path):
    from bridges.tiktok.common.ipc import _ipc
    from taktik.core.ai.factory import create_ai_service
    from taktik.core.social_media.tiktok.workflows.core import ai_hooks

    _scripted_provider(monkeypatch, tmp_path)
    enabled, service = create_ai_service(ai_config={"enabled": True, "openrouterApiKey": "sk-or-" + "x" * 48},
                                         ipc=_ipc)
    assert enabled

    assert ai_hooks.qualify_tiktok_profile(service, object(), "alice") is not None

    _conforms(AI_PROFILE_DONE_EVENT, lines)
    _conforms(AI_SPEND_EVENT, lines)


def test_ai_relevance_is_what_the_bridge_ai_hooks_print(monkeypatch, lines, tmp_path):
    """A run that qualifies the profiles it visits: the bridge's hooks (`install_run_ai_hooks`) on
    the shared mixin, the real AI service, the verdict, its copy for the base, the relevance."""
    from bridges.tiktok.automation.ai import install_run_ai_hooks
    from taktik.core.social_media.tiktok.actions.business.workflows._internal.video_comment import VideoCommentMixin
    from taktik.core.social_media.tiktok.actions.business.workflows.followers.interaction import (
        VideoInteractionMixin,
    )

    # The hooks patch two mixins for the process: the visit itself answers from a script, and
    # both are put back after the test.
    monkeypatch.setattr(VideoInteractionMixin, "_interact_with_profile_posts", lambda self_wf: "interacted")
    monkeypatch.setattr(VideoCommentMixin, "_try_comment_video", VideoCommentMixin._try_comment_video)
    _scripted_provider(monkeypatch, tmp_path)

    install_run_ai_hooks({"enabled": True, "openrouterApiKey": _KEY, "profileAnalysis": True}, "fr")
    visit = SimpleNamespace(device=object(), _current_profile_username="alice")
    assert VideoInteractionMixin._interact_with_profile_posts(visit) == "interacted"

    _conforms(AI_RELEVANCE_EVENT, lines)
    _conforms(AI_PROFILE_DONE_EVENT, lines)
    assert any(line.get("persist_only") for line in lines if line["type"] == "ai_profile_done")


def test_ai_relevance_is_what_the_welcome_pass_prints(monkeypatch, lines, tmp_path):
    from bridges.tiktok.automation.ai import build_welcome_qualifier

    _scripted_provider(monkeypatch, tmp_path)
    qualify = build_welcome_qualifier({"enabled": True, "openrouterApiKey": _KEY}, "fr")
    assert qualify is not None

    assert qualify(object(), "bob") is not None
    _conforms(AI_RELEVANCE_EVENT, lines)
    _conforms(AI_PROFILE_DONE_EVENT, lines)
    # The welcome pass's session does not read `ai_spend`.
    assert "ai_spend" not in {line["type"] for line in lines}


#: The dispatcher's workflows that qualify profiles: those that visit them, and the welcome pass.
_QUALIFYING = {
    "tiktok.automation.followers", "tiktok.automation.target_profiles", "tiktok.automation.post_url",
    "tiktok.automation.new_followers",
}


def test_every_tiktok_app_reader_of_ai_profile_done_has_it_declared():
    declared = {c.workflow_id for c in WORKFLOW_CONTRACTS if any(e is AI_PROFILE_DONE_EVENT for e in c.events)}
    assert {"tiktok.automation.for_you", "tiktok.automation.hashtag", *_QUALIFYING} <= declared


def test_every_tiktok_workflow_that_qualifies_profiles_declares_ai_relevance():
    declared = {c.workflow_id for c in WORKFLOW_CONTRACTS if any(e is AI_RELEVANCE_EVENT for e in c.events)}
    assert declared == _QUALIFYING


# ---------------------------------------------------------------------------- the ai block


def _paths(shape: Shape, prefix=()) -> set:
    out = set()
    for item in shape.fields:
        for name in item.names:
            out.add((*prefix, name))
            if isinstance(item.type, Shape):
                out |= _paths(item.type, (*prefix, name))
    return out


def _wire_block(shape: Shape) -> Dict[str, Any]:
    values = {"bool": True, "int": 3, "number": 0.5, "string": "probe", "json": {"probe": 1}}
    block = {}
    for item in shape.fields:
        if isinstance(item.type, Shape):
            block[item.key] = _wire_block(item.type)
        elif isinstance(item.type, str):
            block[item.key] = values[item.type]
        else:
            block[item.key] = ["Hello"]
    return block


def test_the_ai_block_readers_read_the_declared_keys_and_no_other(monkeypatch):
    from taktik.core.ai.factory import create_ai_service
    from taktik.core.social_media.tiktok.actions.business.workflows._internal.video_comment import VideoCommentMixin
    from taktik.core.social_media.tiktok.actions.business.workflows.followers.interaction import (
        VideoInteractionMixin,
    )
    from taktik.core.social_media.tiktok.services.welcome.decision import parse_welcome_policy
    from taktik.core.social_media.tiktok.workflows.core import ai_hooks

    # The hooks patch two mixins for the process: put them back after the test.
    monkeypatch.setattr(VideoInteractionMixin, "_interact_with_profile_posts",
                        VideoInteractionMixin._interact_with_profile_posts)
    monkeypatch.setattr(VideoCommentMixin, "_try_comment_video", VideoCommentMixin._try_comment_video)
    block = _wire_block(AI_BLOCK)
    block["openrouterApiKey"] = "sk-or-" + "x" * 48
    log: set = set()
    ai_config = Recording(block, log)

    enabled, service = create_ai_service(ai_config=ai_config)
    assert enabled
    ai_hooks.install_tiktok_ai_hooks(service, ai_config)
    parse_welcome_policy(ai_config)

    opaque = {(item.key,) for item in AI_BLOCK.fields if item.type == "json"}
    read = {path for path in log if not (path[:1] in opaque and len(path) > 1)}
    assert read <= _paths(AI_BLOCK), f"read and not declared: {sorted(read - _paths(AI_BLOCK))}"
    wire = {(item.key,) for item in AI_BLOCK.fields} | {
        (item.key, sub.key) for item in AI_BLOCK.fields if isinstance(item.type, Shape) for sub in item.type.fields}
    assert wire <= read, f"declared and not read: {sorted(wire - read)}"


# --------------------------------------------------------------- rows of the screen readers


def _literal_keys(path: Path, function: str) -> List[set]:
    """The key sets of the dict literals `function` appends to a list or assigns to `res`."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function:
            for inner in ast.walk(node):
                target = None
                if (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute)
                        and inner.func.attr == "append" and inner.args):
                    target = inner.args[0]
                elif isinstance(inner, ast.Assign) and any(
                        isinstance(t, ast.Name) and t.id == "res" for t in inner.targets):
                    target = inner.value
                if isinstance(target, ast.Dict) and all(isinstance(k, ast.Constant) for k in target.keys):
                    found.append({k.value for k in target.keys})
    return found


@pytest.mark.parametrize("module, function, shape_name", [
    ("actions/atomic/messaging/dm_actions.py", "get_new_followers", "TikTokNewFollowerRow"),
    ("actions/atomic/messaging/dm_actions.py", "get_inbox_conversations", "TikTokInboxConversationRow"),
    ("actions/atomic/messaging/dm_actions.py", "get_message_requests", "TikTokMessageRequestRow"),
    ("actions/atomic/messaging/dm_actions.py", "get_inbox_notifications", "TikTokActivityNotificationRow"),
    ("actions/atomic/messaging/dm_actions.py", "get_messages", "TikTokDmMessageRead"),
    ("actions/business/workflows/dm/workflow.py", "follow_back_users", "TikTokFollowBackResult"),
    ("actions/business/workflows/dm/workflow.py", "process_message_requests", "TikTokRequestResult"),
])
def test_the_screen_readers_build_the_declared_rows(module, function, shape_name):
    shapes = {}

    def collect(spec):
        if isinstance(spec, Shape):
            shapes[spec.name] = spec
            for sub in spec.fields:
                collect(sub.type)
        elif hasattr(spec, "item"):
            collect(spec.item)

    for contract in WORKFLOW_CONTRACTS:
        for item in (*contract.settings, *(f for e in contract.events for f in e.fields)):
            collect(item.type)
    declared = {item.key for item in shapes[shape_name].fields}
    always = {item.key for item in shapes[shape_name].fields if not item.optional}

    literals = _literal_keys(_TIKTOK / module, function)
    assert literals, f"no dict literal found in {function}"
    for keys in literals:
        assert always <= keys <= declared, (function, keys ^ declared)
