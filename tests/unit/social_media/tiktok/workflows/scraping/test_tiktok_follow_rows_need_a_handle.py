"""A TikTok follow-list row is saved under a handle, never under the display name it shows.

When the handle anchors of the list resolve nothing, the loop falls back on the display names.
Those rows used to be saved as they were, a nickname standing as the pseudo; and the profile
reader let a nickname read in place of the handle replace the known one. Every name here is
invented.
"""

from types import SimpleNamespace

import pytest

import taktik.core.social_media.tiktok.actions.business.workflows.scraping.workflow as workflow_module
from taktik.core.social_media.tiktok.actions.business.workflows._internal.profile_extractor import (
    extract_profile_from_screen,
)
from taktik.core.social_media.tiktok.actions.business.workflows.scraping.models import ScrapingConfig
from taktik.core.social_media.tiktok.actions.business.workflows.scraping.workflow import ScrapingWorkflow
from taktik.core.social_media.tiktok.ui.selectors.surfaces.followers import FOLLOWERS_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.surfaces.profile import PROFILE_SELECTORS

NICKNAME = "‍إستي ✰"


class _Element:
    def __init__(self, text):
        self.text = text


def _workflow(monkeypatch, handles, names, enrich=False, opened=None):
    """A follow list showing `handles` and `names`; opening a row shows `opened[name]` as handle."""
    monkeypatch.setattr(workflow_module.time, "sleep", lambda _s: None)

    def first_matching(_device, selectors):
        if selectors == FOLLOWERS_SELECTORS.follower_username:
            return [_Element(text) for text in handles]
        if selectors == FOLLOWERS_SELECTORS.follower_display_name:
            return [_Element(text) for text in names]
        return []

    monkeypatch.setattr(workflow_module, "first_matching", first_matching)
    config = ScrapingConfig(scrape_type="target", enrich_profiles=enrich, max_profiles=50)
    workflow = ScrapingWorkflow(object(), SimpleNamespace(navigate_to_user_profile=lambda _u: True), config)
    workflow._base = SimpleNamespace(_find_and_click=lambda *_a, **_k: True)
    workflow._scroll = SimpleNamespace(scroll_search_results=lambda **_k: None)

    def enrich_in_place(profile, elem, _raw, username):
        profile["username"] = (opened or {}).get(elem.text, username)
        profile["is_enriched"] = True

    workflow._enrich_in_place = enrich_in_place
    workflow.saved = []
    workflow.set_on_save_profile_callback(workflow.saved.append)
    return workflow


def _saved(workflow):
    return [(profile["username"], profile["display_name"]) for profile in workflow.saved]


def test_rows_showing_handles_are_saved_under_them(monkeypatch):
    workflow = _workflow(monkeypatch, ["@lina.b", "@marc_studio"], ["Lina B", "Marc"])

    workflow._scrape_target_followers("source", "followers", 50)

    assert _saved(workflow) == [("lina.b", "Lina B"), ("marc_studio", "Marc")]


def test_display_names_alone_are_never_saved_as_pseudos(monkeypatch):
    workflow = _workflow(monkeypatch, [], ["Lina B", NICKNAME, "marc"])

    workflow._scrape_target_followers("source", "followers", 50)

    assert workflow.saved == []


def test_a_display_name_row_is_kept_when_its_profile_shows_the_handle(monkeypatch):
    workflow = _workflow(monkeypatch, [], ["Lina B", NICKNAME], enrich=True, opened={"Lina B": "lina.b"})

    workflow._scrape_target_followers("source", "followers", 50)

    assert _saved(workflow) == [("lina.b", "Lina B")]


def test_a_handle_row_that_holds_no_handle_is_skipped(monkeypatch):
    workflow = _workflow(monkeypatch, ["@lina.b", "Lina B"], ["Lina B", "Lina B"])

    workflow._scrape_target_followers("source", "followers", 50)

    assert _saved(workflow) == [("lina.b", "Lina B")]


class _Query:
    def __init__(self, elements):
        self._elements = elements

    def all(self):
        return list(self._elements)


class _Screen:
    def __init__(self, screen):
        self._screen = screen

    def xpath(self, selector):
        return _Query(self._screen.get(selector, []))

    def __call__(self, **_kwargs):
        return SimpleNamespace(exists=False, count=0)


@pytest.mark.parametrize("shown", [NICKNAME, "Lina B"])
def test_a_nickname_in_the_handle_slot_keeps_the_known_handle(shown):
    screen = _Screen({PROFILE_SELECTORS.username[0]: [_Element(shown)]})

    assert extract_profile_from_screen(screen, "lina.b")["username"] == "lina.b"


def test_the_handle_on_the_profile_still_wins():
    screen = _Screen({PROFILE_SELECTORS.username[0]: [_Element("@lina.b")]})

    assert extract_profile_from_screen(screen, "")["username"] == "lina.b"
