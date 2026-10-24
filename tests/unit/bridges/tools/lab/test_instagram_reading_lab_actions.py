"""Three Instagram reads of production that the Lab could not run one by one.

The likers of a post as the scraping and the post URL workflows read them
(`LikerExtractionMixin._extract_likers_after_click`), the message requests folder of the DM inbox
(`DMInboxNavigationMixin.open_requests_folder`), and the thread a comment of a workflow reads
before writing (`ThreadContextMixin.read_thread_context`). Each action must call that function,
never a reading of its own.
"""

from types import SimpleNamespace

import bridges.tools.lab.actions.instagram.dm as dm
from bridges.tools.lab.actions.instagram.comment import read_thread_context
from bridges.tools.lab.actions.instagram.post import read_likers
from taktik.core.social_media.instagram.workflows.common.comment_context import ThreadSelection


def test_the_likers_are_read_by_the_reader_of_the_workflows():
    calls = []

    def extract(max_interactions=None, multiply_by=2):
        calls.append((max_interactions, multiply_by))
        return ["ana", "bob"]

    result = read_likers(SimpleNamespace(popup=SimpleNamespace(_extract_likers_after_click=extract)),
                         {"max_likers": "7"})

    # One liker asked for is one read: the workflows double their budget, the Lab reads what it asks.
    assert calls == [(7, 1)]
    assert result["success"] is True
    assert result["details"] == {"count": 2, "usernames": ["ana", "bob"]}


def test_no_liker_read_is_a_failure():
    popup = SimpleNamespace(_extract_likers_after_click=lambda **_k: [])

    assert read_likers(SimpleNamespace(popup=popup), {})["success"] is False


def test_the_requests_folder_is_opened_by_the_production_runtime(monkeypatch):
    opened = []

    class _Runtime:
        def open_requests_folder(self):
            opened.append(True)
            return True

    monkeypatch.setattr(dm, "_dm_runtime", lambda _a: _Runtime())

    result = dm.open_requests(SimpleNamespace(), {})

    assert opened == [True]
    assert result["success"] is True


def test_the_thread_is_read_as_a_comment_of_a_workflow_reads_it():
    calls = []
    selection = ThreadSelection(items=[{"username": "x", "text": "nice light"}], seen=3, kept=1,
                                praise_count=2, dropped={"praise": 2})

    def read(**kwargs):
        calls.append(kwargs)
        return selection

    result = read_thread_context(SimpleNamespace(comment=SimpleNamespace(read_thread_context=read)),
                                 {"post_author": "@author"})

    assert calls == [{"post_author": "author"}]
    assert result["success"] is True
    assert result["details"]["items"] == [{"username": "x", "text": "nice light"}]
    assert result["details"]["praise_count"] == 2
    assert result["details"]["dropped"] == {"praise": 2}


def test_a_thread_without_material_is_not_a_success():
    comment = SimpleNamespace(read_thread_context=lambda **_k: ThreadSelection())

    assert read_thread_context(SimpleNamespace(comment=comment), {})["success"] is False
