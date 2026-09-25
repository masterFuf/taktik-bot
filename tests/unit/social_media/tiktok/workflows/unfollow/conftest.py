"""A TikTok following list on a fake phone, read by uiautomator2's own xpath engine.

The rows follow the French captures of 46.6.3 (own following list, 2026-08-30): a clickable row
holding the display name (`txt_user_name`), the handle when the list shows one (`txt_desc`) and a
Button whose text IS the relationship (« Suivis », « Ami(e)s », « Suivre »). Tapping « Suivis »
turns it into « Suivre » in place, and the row stays: that is what the capture after an unfollow
shows. The handles are invented; the dumps stay out of this public repository.

What happens on a tap is set per row (`on_tap`): the row flips (the normal case), stays as it was
(a tap that did not take), or a confirmation sheet covers the list first.
"""

import types

import pytest
from uiautomator2.xpath import XPathEntry

import taktik.core.social_media.tiktok.actions.business.workflows.unfollow.workflow as workflow_module
from taktik.core.social_media.tiktok.actions.business.workflows.unfollow.models import (
    UnfollowConfig,
    UnfollowStats,
)
from taktik.core.social_media.tiktok.actions.business.workflows.unfollow.workflow import UnfollowWorkflow
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.surfaces.followers import FOLLOWERS_SELECTORS

PKG = "com.zhiliaoapp.musically"
FLIP, STAY, SHEET = "flip", "stay", "sheet"


def _node(cls, text="", rid="", clickable="false", bounds=(0, 0, 10, 10), children=""):
    l, t, r, b = bounds
    rid_attr = f"{PKG}:id/{rid}" if rid else ""
    return (f'<node class="{cls}" text="{text}" resource-id="{rid_attr}" content-desc="" '
            f'clickable="{clickable}" bounds="[{l},{t}][{r},{b}]">{children}</node>')


class Row:
    def __init__(self, name, handle, label="Suivis", on_tap=FLIP, handle_offset=44):
        self.name = name
        self.handle = handle
        self.label = label
        self.on_tap = on_tap
        # 46.6.3: the handle's top is 44 px below the button's; 43.1.4: 58 px.
        self.handle_offset = handle_offset
        self.taps = 0


class FollowingList:
    """The phone: its screen is rebuilt from the rows at every dump."""

    wait_timeout = 1.0

    def __init__(self, rows):
        self.rows = list(rows)
        self.sheet_for = None
        self.sheet_shown = 0
        self.xpath = XPathEntry(self)

    # uiautomator2's engine reads the screen through this
    def dump_hierarchy(self, *args, **kwargs):
        if self.sheet_for is not None:
            body = _node("android.widget.FrameLayout", clickable="true", bounds=(0, 2065, 1080, 2245),
                         children=_node("android.widget.TextView", "Arrêter de suivre",
                                        bounds=(40, 2120, 600, 2180)))
        else:
            body = ""
            for index, row in enumerate(self.rows):
                top = 600 + index * 190
                names = _node("android.widget.TextView", row.name, rid="txt_user_name",
                              bounds=(221, top, 540, top + 50))
                if row.handle:
                    handle_top = top + 11 + row.handle_offset
                    names += _node("android.widget.TextView", row.handle, rid="txt_desc",
                                   bounds=(221, handle_top, 684, handle_top + 42))
                body += _node("android.widget.LinearLayout", clickable="true", bounds=(0, top, 1080, top + 189),
                              children=_node("android.widget.FrameLayout", bounds=(30, top, 200, top + 170))
                              + _node("android.widget.LinearLayout", bounds=(221, top, 700, top + 150),
                                      children=names)
                              + _node("android.widget.Button", row.label, clickable="true",
                                      bounds=(723, top + 11, 954, top + 85)))
            body = _node("androidx.recyclerview.widget.RecyclerView", bounds=(0, 580, 1080, 2300), children=body)
        return f'<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">{body}</hierarchy>'

    def row_at(self, top):
        index = round((top - 611) / 190)
        return self.rows[index] if 0 <= index < len(self.rows) else None

    def tap(self, element):
        """What the workflow's humanized tap does on this phone."""
        text = getattr(element, "text", "")
        if text == "Arrêter de suivre" or self.sheet_for is not None:
            self.sheet_for.label = "Suivre"
            self.sheet_for = None
            return True
        row = self.row_at(element.bounds[1])
        row.taps += 1
        if row.on_tap == FLIP:
            row.label = "Suivre"
        elif row.on_tap == SHEET:
            self.sheet_for = row
            self.sheet_shown += 1
        return True


class Clock:
    """Time as the workflow sees it: sleeping advances it, nothing else does."""

    def __init__(self):
        self.now = 0.0
        self.slept = []

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds

    def monotonic(self):
        return self.now


@pytest.fixture(autouse=True)
def french():
    set_active_locale("fr")
    yield
    set_active_locale(None)


@pytest.fixture
def clock(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(workflow_module, "time", types.SimpleNamespace(sleep=clock.sleep, monotonic=clock.monotonic))
    return clock


@pytest.fixture
def base_db(monkeypatch):
    """The base as the workflow reaches it: ages by handle, the account id, what gets recorded."""
    from taktik.core.database.tiktok_follow_graph import TikTokFollowGraphService
    import taktik.core.database.local.service as db_service

    state = types.SimpleNamespace(ages={}, recorded=[], looked_up=[], account_id=7)

    def _age(username, account_id):
        state.looked_up.append((username, account_id))
        return state.ages.get(username)

    def _record(username, account_id, session_id=None):
        state.recorded.append((username, account_id))
        return True

    monkeypatch.setattr(TikTokFollowGraphService, "get_follow_age_days", staticmethod(_age))
    monkeypatch.setattr(TikTokFollowGraphService, "record_unfollow", staticmethod(_record))
    monkeypatch.setattr(db_service, "get_local_database", lambda: types.SimpleNamespace(
        get_or_create_tiktok_account=lambda username: (state.account_id, False)))
    return state


@pytest.fixture
def make_workflow(clock, base_db):
    """A workflow on the fake list; `.events` collects what the bridge would send."""

    def _make(rows, **config):
        phone = FollowingList(rows)
        workflow = UnfollowWorkflow.__new__(UnfollowWorkflow)
        workflow.device = phone
        config.setdefault("min_delay", 0)
        config.setdefault("max_delay", 0)
        config.setdefault("max_scroll_attempts", 1)
        config.setdefault("bot_username", "moncompte")
        workflow.config = UnfollowConfig(**config)
        workflow.stats = UnfollowStats()
        workflow.stopped = False
        workflow._account_id = None
        workflow._account_resolved = False
        workflow._unconfirmed_in_a_row = 0
        workflow._kept = set()
        workflow._selectors = FOLLOWERS_SELECTORS
        workflow._nav = types.SimpleNamespace(navigate_to_profile=lambda: True)
        workflow._scroll = types.SimpleNamespace(scroll_profile_videos=lambda direction: None)
        workflow._base = types.SimpleNamespace(
            _find_and_click=lambda *a, **k: True,
            _human_tap_bounds=phone.tap,
        )
        workflow.events = []
        workflow._on_unfollow = lambda username, count: workflow.events.append(("unfollowed", username))
        workflow._on_skip = lambda username, reason: workflow.events.append(("skipped", username, reason))
        workflow._on_unconfirmed = lambda username, state: workflow.events.append(("not_confirmed", username, state))
        workflow._on_stats = None
        workflow.phone = phone
        return workflow

    return _make


@pytest.fixture
def screen():
    """The row builder and the tap outcomes, for the tests of this folder."""
    return types.SimpleNamespace(Row=Row, FollowingList=FollowingList, FLIP=FLIP, STAY=STAY, SHEET=SHEET)
