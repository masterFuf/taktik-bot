"""Lab action engagement.comment_feed_post: the two calls the Feed loop makes, nothing else."""

from types import SimpleNamespace

from bridges.compat.diagnostics.actions.instagram.engagement import comment_feed_post


class _Feed:
    def __init__(self, author="bob", result=None):
        self.author = author
        self.result = result or {"commented": True, "success": True}
        self.calls = []

    def _get_current_post_author(self):
        return self.author

    def _comment_feed_post(self, author, config, comment_text=None):
        self.calls.append((author, config))
        return self.result


def test_it_comments_through_the_feed_comment_under_the_author():
    feed = _Feed()

    result = comment_feed_post(SimpleNamespace(feed=feed), {"text": "Superbe"})

    assert feed.calls == [("bob", {"custom_comments": ["Superbe"]})]
    assert result["success"] is True


def test_without_a_text_it_shows_the_feed_rule():
    feed = _Feed(result={"commented": False, "skipped": True, "skip_reason": "no_comment_text"})

    result = comment_feed_post(SimpleNamespace(feed=feed), {})

    assert feed.calls == [("bob", {"custom_comments": []})]
    assert result["success"] is False
    assert "no_comment_text" in result["message"]


def test_an_unreadable_author_means_no_comment():
    feed = _Feed(author=None)

    result = comment_feed_post(SimpleNamespace(feed=feed), {"text": "Superbe"})

    assert feed.calls == []
    assert result["success"] is False
