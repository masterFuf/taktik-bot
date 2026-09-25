"""Lab action post_url.read_post_author: the production read of the post URL workflow."""

from types import SimpleNamespace

import taktik.core.social_media.instagram.actions.business.workflows.post_url.workflow as post_url_module
from bridges.compat.diagnostics.actions.instagram.scraping import read_post_author


class _PostUrl:
    author = "abelstudios.au"

    def __init__(self, device):
        self.device = device

    def _extract_author_username(self):
        return self.author


def test_it_reads_the_author_through_the_post_url_workflow(monkeypatch):
    monkeypatch.setattr(post_url_module, "PostUrlBusiness", _PostUrl)

    result = read_post_author(SimpleNamespace(device="warm"), {})

    assert result["success"] is True
    assert result["details"]["author"] == "abelstudios.au"


def test_an_unreadable_author_is_a_failed_read(monkeypatch):
    monkeypatch.setattr(post_url_module, "PostUrlBusiness", type("P", (_PostUrl,), {"author": None}))

    assert read_post_author(SimpleNamespace(device="warm"), {})["success"] is False
