"""Blocking-modal recovery — the interaction engine must proactively back out of an UNEXPECTED
sheet (e.g. the Direct share sheet opened by a mis-tap next to the comment button) so a workflow
is never silently blocked, in ANY app language.

Covers both the shared signatures (single source of truth) and the ModalRecoveryMixin behaviour.
"""

import logging

from taktik.core.social_media.instagram.actions.base.base_business.modal_recovery import ModalRecoveryMixin
from taktik.core.social_media.instagram.ui.selectors.support.blocking_modals import (
    BLOCKING_MODAL_SELECTORS,
)


class _XPath:
    def __init__(self, exists):
        self._exists = exists

    @property
    def exists(self):
        return self._exists


class _ModalDevice:
    """Reports the blocking modal as present until a back press dismisses it; counts back presses."""

    def __init__(self, present):
        self._present = present
        self.back_presses = 0

    def xpath(self, query):
        return _XPath(self._present)

    def press(self, key):
        self.back_presses += 1
        self._present = False  # a back press closes the bottom sheet


class _Recoverer(ModalRecoveryMixin):
    def __init__(self, present):
        self.device = _ModalDevice(present)
        self.logger = logging.getLogger("test_modal_recovery")


# ── Centralized signatures (single source of truth) ──────────────────────────────────────────

def test_signatures_are_language_independent_resource_ids():
    combined = BLOCKING_MODAL_SELECTORS.combined_xpath()
    assert "direct_private_share_container_view" in combined
    assert "direct_private_share_recipients_recycler_view" in combined
    # No localized text — resource-id based, so it holds across languages.
    assert "@text" not in combined


def test_signature_xpath_list_matches_a_known_signature():
    lst = BLOCKING_MODAL_SELECTORS.signature_xpath_list("direct_share_sheet")
    assert lst, "the direct_share_sheet signature must expose its indicators"
    assert all("contains(@resource-id" in s for s in lst)


def test_identify_returns_the_matching_signature_name():
    # exists_fn that always reports present -> the first (only) signature matches.
    assert BLOCKING_MODAL_SELECTORS.identify(lambda q: True) == "direct_share_sheet"
    assert BLOCKING_MODAL_SELECTORS.identify(lambda q: False) is None


def test_comment_selector_sources_from_the_registry():
    """The comment action's share_sheet_indicators must be the SAME resource-ids as the registry
    (single source of truth — no drift between the inline guard and the proactive guard)."""
    from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_COMMENTS_SELECTORS
    assert (
        POST_COMMENTS_SELECTORS.share_sheet_indicators
        == BLOCKING_MODAL_SELECTORS.signature_xpath_list("direct_share_sheet")
    )


# ── ModalRecoveryMixin behaviour ─────────────────────────────────────────────────────────────

def test_detect_returns_name_when_modal_present():
    assert _Recoverer(True)._detect_blocking_modal() == "direct_share_sheet"


def test_detect_returns_none_when_clean():
    assert _Recoverer(False)._detect_blocking_modal() is None


def test_recover_backs_out_when_modal_open(monkeypatch):
    import taktik.core.social_media.instagram.actions.base.base_business.modal_recovery as mod
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)
    r = _Recoverer(True)
    assert r._recover_from_blocking_modal("someuser", context="test") == "direct_share_sheet"
    assert r.device.back_presses >= 1
    # And the screen is clean afterwards.
    assert r._detect_blocking_modal() is None


def test_recover_is_noop_when_clean(monkeypatch):
    import taktik.core.social_media.instagram.actions.base.base_business.modal_recovery as mod
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)
    r = _Recoverer(False)
    assert r._recover_from_blocking_modal("someuser") is None
    assert r.device.back_presses == 0


def test_recover_never_raises_on_device_error(monkeypatch):
    import taktik.core.social_media.instagram.actions.base.base_business.modal_recovery as mod
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)

    class _BoomDevice:
        def xpath(self, query):
            raise RuntimeError("uiautomator down")

        def press(self, key):
            pass

    r = _Recoverer(False)
    r.device = _BoomDevice()
    # Detection swallows the error -> treated as "no modal" -> no crash.
    assert r._recover_from_blocking_modal("someuser") is None
