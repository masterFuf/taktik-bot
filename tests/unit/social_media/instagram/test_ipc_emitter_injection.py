"""Unit tests for injected Instagram IPC emitter adapters."""

from taktik.core.social_media.instagram.actions.core.ipc import IPCEmitter


class RecordingAdapter:
    def __init__(self):
        self.calls = []

    def send_follow_event(self, username, success=True, profile_data=None):
        self.calls.append(("follow", username, success, profile_data))

    def send_unfollow_event(self, username, success=True):
        self.calls.append(("unfollow", username, success))

    def send_stats(self, **stats):
        self.calls.append(("stats", stats))

    def send_current_post(self, **payload):
        self.calls.append(("current_post", payload))

    def send_post_skipped(self, **payload):
        self.calls.append(("post_skipped", payload))

    def send_feed_decision(self, author, action, reason=None, comment=None, visit_profile=False):
        self.calls.append(("feed_decision", author, action, reason, comment, visit_profile))


def teardown_function():
    IPCEmitter.clear_bridge_adapter()


def test_ipc_emitter_is_noop_without_bridge_adapter():
    IPCEmitter.clear_bridge_adapter()

    IPCEmitter.emit_follow("alice")
    IPCEmitter.emit_current_post(author="alice")


def test_ipc_emitter_uses_injected_bridge_adapter():
    adapter = RecordingAdapter()
    IPCEmitter.configure_bridge_adapter(adapter)

    IPCEmitter.emit_follow("alice", profile_data={"followers_count": 10})
    IPCEmitter.emit_unfollow("bob")
    IPCEmitter.emit_stats(unfollows=1)
    IPCEmitter.emit_current_post(author="author", hashtag="fitness")
    IPCEmitter.emit_post_skipped(author="author", reason="already_processed", hashtag="fitness")

    assert adapter.calls == [
        ("follow", "alice", True, {"followers_count": 10}),
        ("unfollow", "bob", True),
        ("stats", {"likes": 0, "follows": 0, "comments": 0, "profiles": 0, "unfollows": 1}),
        ("current_post", {"author": "author", "likes_count": None, "comments_count": None, "caption": None, "hashtag": "fitness"}),
        ("post_skipped", {"author": "author", "reason": "already_processed", "hashtag": "fitness"}),
    ]


def test_emit_feed_decision_forwards_to_adapter():
    adapter = RecordingAdapter()
    IPCEmitter.configure_bridge_adapter(adapter)

    IPCEmitter.emit_feed_decision("alice", "like", reason="Liké")
    IPCEmitter.emit_feed_decision("bob", "like_comment", reason="Commenté", comment="nice!")
    IPCEmitter.emit_feed_decision(None, "skip", reason="200 likes > max 150")

    assert adapter.calls == [
        ("feed_decision", "alice", "like", "Liké", None, False),
        ("feed_decision", "bob", "like_comment", "Commenté", "nice!", False),
        ("feed_decision", None, "skip", "200 likes > max 150", None, False),
    ]


def test_emit_feed_decision_is_noop_without_bridge_adapter():
    IPCEmitter.clear_bridge_adapter()
    # Must not raise when no bridge is injected (standalone/CLI runs).
    IPCEmitter.emit_feed_decision("alice", "like", reason="Liké")
