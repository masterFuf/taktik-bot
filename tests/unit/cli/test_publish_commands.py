"""Publishing from the CLI must use the same workflow as the desktop app.

The CLI had `management content post|post-bulk|story` and two menu entries built on
`ContentWorkflow`, a second, older implementation that had drifted from the one the publish bridge
runs (`post-bulk` published N separate posts, not a carousel; no reels; none of the fixes on slide
order and on reclaiming pushed media). That engine is gone: the commands and the menu call the
production workflow.

These tests pin that the commands call the production workflow with the right post type and the
media in the caller's order — the property a user notices immediately when it breaks.
"""
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from taktik.cli.commands import publish_cmds


class RecordingWorkflow:
    """Captures how the production workflow was constructed and called."""

    last = None

    def __init__(self, device, device_id, *, log=None, status=None, post_type="post",
                 story_via_feed=False, package_name=None):
        self.post_type = post_type
        self.story_via_feed = story_via_feed
        self.device_id = device_id
        self.call = None
        RecordingWorkflow.last = self

    def execute(self, caption="", hashtags=None, media_paths=None, stop_before_share=False):
        self.call = {
            "caption": caption,
            "hashtags": hashtags or [],
            "media_paths": list(media_paths or []),
            "stop_before_share": stop_before_share,
        }
        return {"success": True, "message": f"{self.post_type} published", "error_type": None}


@pytest.fixture
def wired(monkeypatch, tmp_path):
    """Stub the device and the workflow, and hand back a factory for real files."""
    monkeypatch.setattr(publish_cmds, "_resolve_device", lambda d: (object(), d or "dev-1"))

    import taktik.core.social_media.instagram.workflows.publish.post_workflow as prod
    monkeypatch.setattr(prod, "InstagramPostWorkflow", RecordingWorkflow)

    def make(name: str) -> str:
        path = tmp_path / name
        path.write_bytes(b"x")
        return str(path)

    RecordingWorkflow.last = None
    return make


def test_post_uses_the_production_workflow(wired):
    image = wired("a.png")
    result = CliRunner().invoke(publish_cmds.publish, ["post", image, "--caption", "hello"])
    assert result.exit_code == 0, result.output
    assert RecordingWorkflow.last.post_type == "post"
    assert RecordingWorkflow.last.call["caption"] == "hello"


def test_carousel_keeps_the_caller_order(wired):
    """Slide order is the property a user sees first; it must survive the CLI."""
    images = [wired("01.png"), wired("02.png"), wired("03.png")]
    result = CliRunner().invoke(publish_cmds.publish, ["carousel", *images])
    assert result.exit_code == 0, result.output
    assert RecordingWorkflow.last.post_type == "carousel"
    assert RecordingWorkflow.last.call["media_paths"] == images


def test_a_single_medium_is_refused_as_a_carousel(wired):
    result = CliRunner().invoke(publish_cmds.publish, ["carousel", wired("a.png")])
    assert result.exit_code == 1
    assert "at least two media" in result.output


def test_more_than_ten_media_is_refused(wired):
    images = [wired(f"{i}.png") for i in range(11)]
    result = CliRunner().invoke(publish_cmds.publish, ["carousel", *images])
    assert result.exit_code == 1
    assert "at most 10" in result.output


def test_reel_is_reachable(wired):
    result = CliRunner().invoke(publish_cmds.publish, ["reel", wired("clip.mp4")])
    assert result.exit_code == 0, result.output
    assert RecordingWorkflow.last.post_type == "reel"


def test_story_can_enter_through_the_feed_tray(wired):
    result = CliRunner().invoke(publish_cmds.publish, ["story", wired("s.png"), "--via-feed"])
    assert result.exit_code == 0, result.output
    assert RecordingWorkflow.last.post_type == "story"
    assert RecordingWorkflow.last.story_via_feed is True


def test_rehearse_never_shares(wired):
    """The flag exists so an operator can check navigation without posting publicly."""
    result = CliRunner().invoke(publish_cmds.publish, ["post", wired("a.png"), "--rehearse"])
    assert result.exit_code == 0, result.output
    assert RecordingWorkflow.last.call["stop_before_share"] is True


def test_hashtags_lose_their_hash_and_split_on_spaces(wired):
    CliRunner().invoke(publish_cmds.publish,
                       ["post", wired("a.png"), "--hashtags", "#travel #sunset nature"])
    assert RecordingWorkflow.last.call["hashtags"] == ["travel", "sunset", "nature"]


def test_a_failed_publish_exits_non_zero(wired, monkeypatch):
    import taktik.core.social_media.instagram.workflows.publish.post_workflow as prod

    class Failing(RecordingWorkflow):
        def execute(self, **kwargs):
            return {"success": False, "message": "no gallery", "error_type": "gallery_item_not_found"}

    monkeypatch.setattr(prod, "InstagramPostWorkflow", Failing)
    result = CliRunner().invoke(publish_cmds.publish, ["post", wired("a.png")])
    assert result.exit_code == 1
    assert "gallery_item_not_found" in result.output


def test_the_cli_has_no_second_publishing_engine():
    """`management content` ran `ContentWorkflow`; publishing goes through `taktik publish` only."""
    import importlib.util

    from taktik.cli.commands.management_cmds import management

    assert "content" not in management.commands
    assert importlib.util.find_spec(
        "taktik.core.social_media.instagram.workflows.management.content") is None


def test_the_menu_publishes_through_the_production_workflow(wired, monkeypatch):
    """The interactive menu's "Post Content" / "Post Story" run the same workflow as the commands,
    and a failure brings the operator back to the menu instead of closing the terminal."""
    import taktik.core.social_media.instagram.workflows.publish.post_workflow as prod

    assert publish_cmds.run_publish("story", "dev-1", (wired("s.png"),)) is True
    assert RecordingWorkflow.last.post_type == "story"

    class Failing(RecordingWorkflow):
        def execute(self, **kwargs):
            return {"success": False, "message": "no gallery", "error_type": "gallery_item_not_found"}

    monkeypatch.setattr(prod, "InstagramPostWorkflow", Failing)
    assert publish_cmds.run_publish("post", "dev-1", (wired("a.png"),), "hello", "#travel") is False
