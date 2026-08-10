"""Qualified visit of the suggestions of the notifications screen.

What these tests lock, and why it matters: a suggestion is an UNKNOWN profile. The
surface shows only its label, never its handle, so there is nothing to reconcile:
the record has to be produced. The previous mode tapped the row button and recorded
the follow under the displayed label; these tests forbid its return.


The device primitives are replaced; the sequencing under test — what to tap, what to
refuse, what to hand to the pipeline — is the production one.
"""

import pytest

from taktik.core.social_media.instagram.workflows.management.notifications.notifications_workflow import (
    NotificationsEngagementWorkflow,
)
from taktik.core.social_media.instagram.actions.core.base_business.profile_processing import (
    ProfileProcessingResult,
)


class _FakePipeline:
    """Injected per-profile pipeline: records what it is asked to handle."""

    def __init__(self, username="real_handle", opens=True, status=ProfileProcessingResult.SUCCESS):
        self.username = username
        self.opens = opens
        self._status = status
        self.processed = []

    def wait_for_profile(self, timeout=8.0):
        return self.opens

    def read_username(self):
        return self.username

    def process(self, username):
        self.processed.append(username)
        outcome = ProfileProcessingResult(self._status, username)
        outcome.interaction_result = {"follows": 1 if self._status == ProfileProcessingResult.SUCCESS else 0}
        return outcome


class _Workflow(NotificationsEngagementWorkflow):
    """Workflow reel, primitives device remplacees."""

    def __init__(self, rows, pipeline=None):
        self._rows = list(rows)
        self.profile_pipeline = pipeline
        self.taps = []
        self.returns = 0
        self.scrolls = 0
        self.zone_reached = True
        self.refreshes = 0
        import loguru
        self.logger = loguru.logger.bind(module="test")
        self._notify_cb = None

    # --- primitives remplacees ---
    def _optimize_locale(self):
        return None

    def scan_suggestions(self, root=None):
        return self._rows

    def reach_suggestions_zone(self, max_scrolls=8):
        return self.zone_reached

    def refresh_notifications_screen(self):
        self.refreshes += 1
        return True

    def _tap_point(self, point, name):
        self.taps.append((point, name))
        return True

    def _scroll_down(self, times=1):
        self.scrolls += times

    def _return_to_notifications(self, attempts=3):
        self.returns += 1
        return True

    def ensure_notifications_screen(self):  # pragma: no cover — never reached here
        return True


def _row(label, state, row_point, follow_point):
    return {"label": label, "state": state, "state_label": state,
            "social_context": "", "row_point": row_point,
            "follow_point": follow_point, "row_top": 0}


NO_DELAY = (0, 0)


def test_the_row_body_is_tapped_and_never_the_follow_button():
    """Tapping the button follows without ever knowing WHO: that is the removed mode."""
    pipeline = _FakePipeline(username="spa_echo")
    wf = _Workflow([_row("Spa Echo", "follow", (274, 1526), (838, 1557))], pipeline)

    result = wf.visit_suggestions(max_profiles=1, delay_range=NO_DELAY)

    assert [point for point, _name in wf.taps] == [(274, 1526)]
    assert result["visited"] == 1
    assert result["processed"] == 1


def test_the_handle_read_on_the_profile_is_what_gets_processed():
    """The displayed label is not a key: only the handle is."""
    pipeline = _FakePipeline(username="spa_echo")
    wf = _Workflow([_row("Spa Ec(h)o", "follow", (274, 1526), (838, 1557))], pipeline)

    wf.visit_suggestions(max_profiles=1, delay_range=NO_DELAY)

    assert pipeline.processed == ["spa_echo"]


def test_without_a_pipeline_nothing_is_tapped_at_all():
    """Without a pipeline only the blind follow would remain: refuse, plainly."""
    wf = _Workflow([_row("Spa Echo", "follow", (274, 1526), (838, 1557))], pipeline=None)

    result = wf.visit_suggestions(max_profiles=1, delay_range=NO_DELAY)

    assert result["stop_reason"] == "no_pipeline"
    assert wf.taps == []
    assert result["visited"] == 0


def test_a_profile_that_does_not_open_is_an_error_not_a_silent_skip():
    """The tap was sent but no profile appeared: handle nothing, and say so."""
    pipeline = _FakePipeline(opens=False)
    wf = _Workflow([_row("Spa Echo", "follow", (274, 1526), (838, 1557))], pipeline)

    result = wf.visit_suggestions(max_profiles=1, max_scrolls=0, delay_range=NO_DELAY)

    assert pipeline.processed == []
    assert result["errors"] == 1
    assert result["visited"] == 0
    assert result["profiles"] == [{"label": "Spa Echo", "username": None, "status": "not_opened"}]


def test_an_open_profile_with_no_readable_handle_is_never_processed():
    """Without a handle, writing would mean inventing a key."""
    pipeline = _FakePipeline(username=None)
    wf = _Workflow([_row("Spa Echo", "follow", (274, 1526), (838, 1557))], pipeline)

    result = wf.visit_suggestions(max_profiles=1, max_scrolls=0, delay_range=NO_DELAY)

    assert pipeline.processed == []
    assert result["errors"] == 1
    assert result["profiles"][0]["status"] == "no_username"


def test_only_plain_follow_rows_are_visited():
    """Same rule as everywhere else: no follow-back, no already-followed."""
    pipeline = _FakePipeline(username="inconnu")
    wf = _Workflow([
        _row("Me suit", "follow_back", (274, 1300), (838, 1330)),
        _row("Deja suivi", "following", (274, 1500), (838, 1530)),
        _row("Inconnu", "follow", (274, 1700), (838, 1730)),
    ], pipeline)

    result = wf.visit_suggestions(max_profiles=5, max_scrolls=0, delay_range=NO_DELAY)

    assert [point for point, _name in wf.taps] == [(274, 1700)]
    assert result["skipped_follow_back"] == 1


def test_each_visit_returns_to_the_notifications_screen():
    """Staying on the profile would make the current page read as the next list."""
    pipeline = _FakePipeline(username="inconnu")
    wf = _Workflow([_row("Inconnu", "follow", (274, 1700), (838, 1730))], pipeline)

    wf.visit_suggestions(max_profiles=1, delay_range=NO_DELAY)

    assert wf.returns == 1


def test_the_zone_must_be_reachable_before_anything_is_touched():
    """Without the zone nothing is touched, and the stop reason says WHICH of the three
    outcomes was met, because they do not call for the same reaction."""
    pipeline = _FakePipeline()
    wf = _Workflow([_row("Inconnu", "follow", (274, 1700), (838, 1730))], pipeline)
    wf.zone_reached = False
    wf.descent_outcome = "no_suggestions_offered"

    result = wf.visit_suggestions(max_profiles=1, delay_range=NO_DELAY)

    assert result["stop_reason"] == "no_suggestions_offered"
    assert wf.taps == []


def test_the_list_is_collapsed_before_the_first_descent():
    """The scan expanded the list with the load-more entry: each tap inserted a page of
    notifications between us and the section. Leaving and coming back collapses it."""
    pipeline = _FakePipeline(username="inconnu")
    wf = _Workflow([_row("Inconnu", "follow", (274, 1700), (838, 1730))], pipeline)

    wf.visit_suggestions(max_profiles=1, delay_range=NO_DELAY)

    assert wf.refreshes == 1


def test_the_collapse_can_be_skipped_for_an_isolated_probe():
    """A probe tests the zone on the screen the operator navigated to."""
    pipeline = _FakePipeline(username="inconnu")
    wf = _Workflow([_row("Inconnu", "follow", (274, 1700), (838, 1730))], pipeline)

    wf.visit_suggestions(max_profiles=1, refresh_first=False, delay_range=NO_DELAY)

    assert wf.refreshes == 0


def test_a_filtered_profile_counts_as_processed_not_as_a_follow():
    """A profile opened, qualified then rejected cost a full run: it must be visible."""
    pipeline = _FakePipeline(username="hors_cible",
                             status=ProfileProcessingResult.FILTERED_CRITERIA)
    wf = _Workflow([_row("Hors cible", "follow", (274, 1700), (838, 1730))], pipeline)

    result = wf.visit_suggestions(max_profiles=1, max_scrolls=0, delay_range=NO_DELAY)

    assert result["processed"] == 1
    assert result["filtered"] == 1
    assert result["follows"] == 0


def test_the_removed_blind_list_mode_cannot_come_back():
    """Following from the list no longer exists: it followed under a display label."""
    assert not hasattr(NotificationsEngagementWorkflow, "follow_suggestions")


@pytest.mark.parametrize("state", ["follow_back", "following", "requested", None])
def test_no_state_other_than_follow_is_ever_opened(state):
    pipeline = _FakePipeline()
    wf = _Workflow([_row("X", state, (274, 1700), (838, 1730))], pipeline)

    result = wf.visit_suggestions(max_profiles=1, max_scrolls=0, delay_range=NO_DELAY)

    assert wf.taps == []
    assert result["visited"] == 0


# ---------------------------------------------------------------------------
# The descent to the zone.
#
# The zone lives at the bottom of the activity screen, and its distance depends on
# the ACCOUNT: an active one stacks dozens of screens before it. A fixed scroll
# budget stopped halfway and the pass left without doing anything, while the zone
# existed further down.
# ---------------------------------------------------------------------------

from lxml import etree

from taktik.core.social_media.instagram.ui.selectors import NOTIFICATION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale


def _screen_xml(marker, with_header=False):
    """One notifications screen; ``marker`` makes it differ from the previous one."""
    header = ('<node class="android.widget.TextView" resource-id="activity_feed_header_row"'
              ' text="Suggestions" bounds="[44,1498][306,1551]"/>') if with_header else ""
    return etree.fromstring(
        ("<?xml version='1.0' encoding='UTF-8'?><hierarchy>"
         f'<node class="android.widget.TextView" text="notification {marker}"'
         f' bounds="[253,300][893,460]"/>' + header + "</hierarchy>").encode("utf-8")
    )


class _Descent(_Workflow):
    """The real workflow, with only the scrolling simulated."""

    def __init__(self, screens):
        super().__init__(rows=[], pipeline=None)
        self._screens = list(screens)
        self.selectors = NOTIFICATION_SELECTORS
        self.show_more_taps = 0

    def reach_suggestions_zone(self, max_scrolls=60):  # on teste la VRAIE methode
        return NotificationsEngagementWorkflow.reach_suggestions_zone(self, max_scrolls)

    def _dump_root(self):
        return self._screens[min(self.scrolls, len(self._screens) - 1)]

    def _tap_show_more(self):  # pragma: no cover — doit rester non appele
        self.show_more_taps += 1
        return True


@pytest.fixture(autouse=True)
def _french():
    set_active_locale("fr")
    yield
    set_active_locale(None)


def test_the_descent_goes_far_past_the_old_fixed_budget():
    """Thirty screens before the zone: a fixed small budget stopped halfway."""
    screens = [_screen_xml(i) for i in range(30)] + [_screen_xml(30, with_header=True)]
    wf = _Descent(screens)

    assert wf.reach_suggestions_zone() is True
    assert wf.scrolls == 30


def test_the_descent_stops_when_the_list_stops_moving():
    """Two identical screens mean the bottom. Insisting would change nothing."""
    screens = [_screen_xml(0), _screen_xml(1)] + [_screen_xml(1)] * 20
    wf = _Descent(screens)

    assert wf.reach_suggestions_zone() is False
    # One identical screen proves nothing, since a render in progress looks the same;
    # the stop comes on the second, not after exhausting the guard.
    assert wf.scrolls == 3


def test_the_descent_never_taps_show_more():
    """The load-more entry loads OLDER notifications: they insert themselves between
    us and the zone, so tapping it moves us away."""
    wf = _Descent([_screen_xml(0), _screen_xml(1), _screen_xml(1), _screen_xml(1)])

    wf.reach_suggestions_zone()

    assert wf.show_more_taps == 0


def test_the_safety_cap_is_a_guard_rail_not_a_stop_policy():
    """When the screen still changes at the cap, say so; do not claim to be at the bottom."""
    wf = _Descent([_screen_xml(i) for i in range(50)])

    assert wf.reach_suggestions_zone(max_scrolls=5) is False
    assert wf.scrolls == 6


def _people_section_xml(marker, header):
    """The bottom of the screen: a PEOPLE section that is not the suggestions one.

    Instagram sert a cet endroit une section dont l'identite VARIE — "Suggestions"
    one pass, another people section the next, nothing sometimes. Reading them as a
    navigation failure would send someone looking for a bug where
    il n'y en a pas.
    """
    return etree.fromstring(
        ("<?xml version='1.0' encoding='UTF-8'?><hierarchy>"
         f'<node class="android.widget.TextView" text="notification {marker}"'
         f' bounds="[253,300][893,460]"/>'
         f'<node class="android.widget.TextView" resource-id="activity_feed_header_row"'
         f' text="{header}" bounds="[44,949][737,1002]"/>'
         "</hierarchy>").encode("utf-8")
    )


def test_a_bottom_without_suggestions_is_reported_as_such_not_as_a_failure():
    other = "Followers que vous ne suivez pas"
    wf = _Descent([_people_section_xml(0, other)] + [_people_section_xml(1, other)] * 5)

    assert wf.reach_suggestions_zone() is False
    assert wf.descent_outcome == "no_suggestions_offered"


def test_hitting_the_guard_rail_is_not_reported_as_an_absent_section():
    """The list was still moving: we do NOT know whether the zone existed further down."""
    wf = _Descent([_screen_xml(i) for i in range(50)])

    assert wf.reach_suggestions_zone(max_scrolls=5) is False
    assert wf.descent_outcome == "cap_hit"


def test_reaching_the_zone_is_reported_as_reached():
    wf = _Descent([_screen_xml(0), _screen_xml(1, with_header=True)])

    assert wf.reach_suggestions_zone() is True
    assert wf.descent_outcome == "reached"
