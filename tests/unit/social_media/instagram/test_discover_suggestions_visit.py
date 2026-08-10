"""Qualified visit of the people discovery screen.

Why this screen is in the flow: the zone at the bottom of the notifications screen is
served by the algorithm and changes identity from one pass to the next on the same
account within the hour. An acquisition cannot
reposer dessus seule.

What these tests lock: the PROFILE is opened and never the button, the visit is spared
when the row designates an already-handled account, and the sequencing shared with the
notifications zone stays identical.
"""

import pytest

from taktik.core.social_media.instagram.actions.business.workflows.common.suggestion_visit import (
    SuggestionSurface,
    visit_suggestions,
)
from taktik.core.social_media.instagram.actions.business.workflows.feed.suggestions_visit import (
    _DiscoverSuggestionSurface,
)
from taktik.core.social_media.instagram.actions.core.base_business.profile_processing import (
    ProfileProcessingResult,
)


class _Surface(SuggestionSurface):
    """Test surface: records what the shared service asks of it."""

    def __init__(self, rows, username="real_handle", opens=True,
                 status=ProfileProcessingResult.SUCCESS, known=()):
        self._rows = list(rows)
        self._username = username
        self._opens = opens
        self._status = status
        self._known = set(known)
        self.opened = []
        self.processed = []
        self.left = 0
        self.scrolls = 0
        self.messages = []

    def reach(self):
        return True

    def scan(self):
        return self._rows

    def followable(self, rows):
        return [r for r in rows if r.get("state") == "follow"]

    def row_key(self, row):
        return (row.get("label") or "").lower()

    def already_known(self, row):
        return (row.get("label") or "") in self._known

    def open_profile(self, row):
        self.opened.append(row.get("label"))
        return self._opens

    def read_username(self):
        return self._username

    def process(self, username):
        self.processed.append(username)
        outcome = ProfileProcessingResult(self._status, username)
        outcome.interaction_result = {
            "follows": 1 if self._status == ProfileProcessingResult.SUCCESS else 0
        }
        return outcome

    def leave(self):
        self.left += 1
        return True

    def scroll(self):
        self.scrolls += 1

    def log_info(self, message):
        self.messages.append(("info", message))

    def log_warning(self, message):
        self.messages.append(("warning", message))


def _row(label, state="follow"):
    return {"label": label, "state": state}


NO_DELAY = (0, 0)


# ---------------------------------------------------------------------------
# The shared sequencing
# ---------------------------------------------------------------------------

def test_the_shared_runner_visits_qualifies_and_returns():
    surface = _Surface([_row("Inconnu")], username="inconnu")

    result = visit_suggestions(surface, max_profiles=1, delay_range=NO_DELAY)

    assert surface.opened == ["Inconnu"]
    assert surface.processed == ["inconnu"]
    assert surface.left == 1
    assert result["visited"] == 1 and result["follows"] == 1


def test_a_known_profile_costs_neither_a_visit_nor_an_ai_call():
    """The surface knows, WITHOUT opening, that the account is handled: spend nothing."""
    surface = _Surface([_row("deja_vu"), _row("inconnu")], known={"deja_vu"})

    result = visit_suggestions(surface, max_profiles=2, max_scrolls=0, delay_range=NO_DELAY)

    assert surface.opened == ["inconnu"]
    assert result["skipped_known"] == 1
    assert result["profiles"][0]["status"] == "already_known"


def test_only_plain_follow_rows_are_visited():
    surface = _Surface([_row("Me suit", "follow_back"), _row("Inconnu")])

    result = visit_suggestions(surface, max_profiles=5, max_scrolls=0, delay_range=NO_DELAY)

    assert surface.opened == ["Inconnu"]
    assert result["skipped_follow_back"] == 1


def test_a_profile_that_does_not_open_is_never_processed():
    surface = _Surface([_row("Inconnu")], opens=False)

    result = visit_suggestions(surface, max_profiles=1, max_scrolls=0, delay_range=NO_DELAY)

    assert surface.processed == []
    assert result["errors"] == 1
    assert result["profiles"][0]["status"] == "not_opened"
    assert surface.left == 1  # we come back to the list anyway


def test_an_unreadable_handle_is_never_processed():
    surface = _Surface([_row("Inconnu")], username=None)

    result = visit_suggestions(surface, max_profiles=1, max_scrolls=0, delay_range=NO_DELAY)

    assert surface.processed == []
    assert result["profiles"][0]["status"] == "no_username"


def test_a_row_is_never_tried_twice():
    """The same screen is re-read between two profiles: without identity, it loops."""
    surface = _Surface([_row("Inconnu")])

    visit_suggestions(surface, max_profiles=3, max_scrolls=2, delay_range=NO_DELAY)

    assert surface.opened == ["Inconnu"]


# ---------------------------------------------------------------------------
# The discovery-screen adapter
# ---------------------------------------------------------------------------

class _Business:
    def __init__(self, account_id=7):
        self._account_id = account_id
        self.taps = []
        self.logger = _Logger()

    def human_tap_record(self, bounds):
        self.taps.append(tuple(bounds))
        return True

    def _get_account_id(self):
        return self._account_id


class _Logger:
    def debug(self, *_a, **_k):
        pass

    def info(self, *_a, **_k):
        pass

    def warning(self, *_a, **_k):
        pass


@pytest.mark.parametrize("label,queried", [
    ("marie.dupont", True),        # forme d'un @handle -> interrogeable
    ("marie_dupont2", True),
    ("Marie Dupont", False),       # nom affiche -> aucune clef, on visite
    ("Spa Ec(h)o", False),
    ("", False),
])
def test_only_handle_shaped_labels_are_looked_up(monkeypatch, label, queried):
    """The FULL NAME is often put in that field. Querying the database with a display
    name would answer nothing useful, and a false positive would cost a target,
    which is worse than paying for a visit twice."""
    asked = []

    def _fake_skippable(username, account_id, **_kw):
        asked.append(username)
        return True, "already_processed"

    monkeypatch.setattr(
        "taktik.core.social_media.instagram.actions.business.workflows.feed."
        "suggestions_visit.InstagramWorkflowStateService.is_profile_skippable",
        staticmethod(_fake_skippable),
    )
    surface = _DiscoverSuggestionSurface(_Business(), {})

    known = surface.already_known({"label": label})

    assert bool(asked) is queried
    assert known is queried


def test_a_database_error_makes_us_visit_rather_than_skip(monkeypatch):
    """Fail-open: a failed read must never lose a target."""
    def _boom(*_a, **_k):
        raise RuntimeError("db down")

    monkeypatch.setattr(
        "taktik.core.social_media.instagram.actions.business.workflows.feed."
        "suggestions_visit.InstagramWorkflowStateService.is_profile_skippable",
        staticmethod(_boom),
    )
    surface = _DiscoverSuggestionSurface(_Business(), {})

    assert surface.already_known({"label": "marie.dupont"}) is False


def test_the_recorded_provenance_names_the_surface():
    """An acquisition coming from the discovery screen must be recognisable in the
    database: that is what will allow comparing the two sources later."""
    assert _DiscoverSuggestionSurface.SOURCE_TYPE == "SUGGESTIONS"
    assert _DiscoverSuggestionSurface.SOURCE_NAME == "discover_people"
