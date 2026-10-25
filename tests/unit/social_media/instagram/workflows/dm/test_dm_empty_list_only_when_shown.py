"""« 0 conversation » only when the screen shows an empty list (rule of 2026-10-25).

The reader concluded « no conversation » as soon as it found no row (« No threads found »), and a
reading of the requests folder that did not open answered 0 as well: a list that had not loaded, or
that Instagram could not load, was read as an empty one, and the « Réponses DM » node succeeded on it.

Captured on a C57S (Android 14, Instagram 410 in English, a test account, 2026-10-25), anonymized:
- the requests folder right after the tap that opens it: its action bar « Message requests » and its
  thread list are up, nothing in it yet (`ig410_en_dm_requests_loading.xml`);
- the same folder a moment later, empty: its page « No message requests » (`ig410_en_dm_requests_empty.xml`);
- the same folder on the phone without network: « Couldn't load requests », « Try again »
  (`ig410_en_dm_requests_load_failed.xml`);
- the main inbox of that account, its header « Messages » and « Requests » above its rows
  (`ig410_en_dm_inbox_messages_header.xml`). No account of ours has an empty main inbox: its header
  is recognised here, on this capture and on the inbox captures of the other layout (pills).
"""

from types import SimpleNamespace

import pytest
from uiautomator2.xpath import XPathEntry

import taktik.core.social_media.instagram.workflows.dm.agent_handler as agent_handler
import taktik.core.social_media.instagram.workflows.dm.reader as reader_module
import taktik.core.social_media.instagram.workflows.dm.session as session
from taktik.core.compat.selectors.setup import apply_version_overrides, baseline_version
from taktik.core.shared.device.wait import find_element
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS
from taktik.core.social_media.instagram.workflows.dm.reader import DMConversationReaderMixin
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"


def _capture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


REQUESTS_LOADING = _capture("ig410_en_dm_requests_loading.xml")
REQUESTS_EMPTY = _capture("ig410_en_dm_requests_empty.xml")
REQUESTS_LOAD_FAILED = _capture("ig410_en_dm_requests_load_failed.xml")
INBOX_MESSAGES_HEADER = _capture("ig410_en_dm_inbox_messages_header.xml")


class _Phone:
    """Shows its captures one after the other, one per look at the screen, then stays on the last."""

    wait_timeout = 0.0
    info = {"displayWidth": 576, "displayHeight": 1280}

    def __init__(self, *screens):
        self.screens = list(screens)
        self.taps = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.screens.pop(0) if len(self.screens) > 1 else self.screens[0]

    def app_current(self):
        return {"package": "com.instagram.android"}

    def click(self, x, y):
        self.taps.append((x, y))

    def press(self, *_a):
        pass


class _Runtime(DMConversationReaderMixin):
    """A DM runtime that has already put the screen it is given on display."""

    def __init__(self, phone, requests_folder_opens=True):
        self.device = phone
        self.requests_folder_opens = requests_folder_opens

    def restart_instagram(self):
        return True

    def navigate_to_dm_inbox(self):
        return True

    def open_requests_folder(self):
        return self.requests_folder_opens

    def _emit_dm_event(self, event, flush=False):
        pass

    def _is_accounts_to_follow_visible(self):
        return False


@pytest.fixture(autouse=True)
def _a_410_phone(monkeypatch):
    no_wait = SimpleNamespace(sleep=lambda *_: None)
    for module in (reader_module, agent_handler):
        monkeypatch.setattr(module, "time", no_wait)
    monkeypatch.setattr(agent_handler, "_detect_app_language", lambda runtime: None)
    monkeypatch.setattr(agent_handler, "account_id_from_inbox_header", lambda runtime: None)
    set_active_locale("en")
    apply_version_overrides("instagram", baseline_version("instagram"))
    yield
    set_active_locale(None)


def _read_requests(*screens, folder_opens=True):
    return agent_handler._read_requests(_Runtime(_Phone(*screens), requests_folder_opens=folder_opens), 0)


def test_an_empty_requests_folder_on_screen_is_a_read_of_zero():
    result = _read_requests(REQUESTS_EMPTY)

    assert result["success"] is True, result
    assert result["total"] == 0 and result["conversations"] == []


def test_a_folder_still_loading_is_waited_for_then_read_empty():
    """The two captures in the order the phone showed them: the reader waits for the empty page."""
    result = _read_requests(REQUESTS_LOADING, REQUESTS_LOADING, REQUESTS_EMPTY)

    assert result["success"] is True, result
    assert result["total"] == 0


def test_a_folder_that_never_loads_is_not_read(monkeypatch):
    monkeypatch.setattr(session, "LIST_LOAD_TIMEOUT_S", 0.0, raising=False)

    result = _read_requests(REQUESTS_LOADING)

    assert result["success"] is False, f"a list that did not load read as an empty one: {result}"
    assert result["error_code"] == "DM_LIST_NOT_LOADED"


def test_a_folder_instagram_could_not_load_is_not_read():
    result = _read_requests(REQUESTS_LOAD_FAILED)

    assert result["success"] is False, f"a list Instagram could not load read as an empty one: {result}"
    assert result["error_code"] == "DM_LIST_LOAD_FAILED"


def test_a_requests_folder_that_did_not_open_is_not_read():
    result = _read_requests(INBOX_MESSAGES_HEADER, folder_opens=False)

    assert result["success"] is False, f"a folder not on screen read as an empty one: {result}"
    assert result["error_code"] == "DM_REQUESTS_NOT_OPENED"


def test_the_reader_taps_nothing_on_a_list_without_rows():
    phone = _Phone(REQUESTS_LOAD_FAILED)

    _Runtime(phone).read_conversations(0)

    assert phone.taps == [], f"« Try again » or « Hidden Requests » tapped: {phone.taps}"


@pytest.mark.parametrize("capture, version", [
    pytest.param("ig410_en_dm_inbox_messages_header.xml", None, id="410-header-messages"),
    pytest.param("ig410_en_dm_inbox.xml", None, id="410-pills-en"),
    pytest.param("ig410_fr_dm_inbox_pills.xml", None, id="410-pills-fr"),
    pytest.param("ig447_fr_dm_inbox_pills_no_ids.xml", "447.0.0.55.81", id="447-pills-fr"),
])
def test_the_header_of_the_main_inbox_is_recognised(capture, version):
    set_active_locale("fr" if "_fr_" in capture else "en")
    if version:
        apply_version_overrides("instagram", version)
    try:
        assert find_element(_Phone(_capture(capture)), DM_SELECTORS.list_loaded_markers) is not None
    finally:
        apply_version_overrides("instagram", baseline_version("instagram"))


def test_a_list_still_loading_shows_neither_header_nor_empty_page():
    """Its action bar and its bare thread list are up, which prove the screen and not its content."""
    phone = _Phone(REQUESTS_LOADING)

    assert session.dm_inbox_shown(phone)
    assert find_element(phone, DM_SELECTORS.list_loaded_markers) is None
