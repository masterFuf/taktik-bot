"""The popup handler escapes surfaces the workflow does not own.

The inbox is the case that matters: the app drops accounts onto it unprompted, so
leaving it is right for a workflow browsing videos and wrong for the one that came to
read it. Which of the two applies is the WORKFLOW's business, declared once through
``OWNED_SURFACES``, not a flag repeated at every popup check.
"""

from taktik.core.social_media.tiktok.actions.business.workflows._internal.popup_handler import (
    PopupHandler,
)


class FakeClick:
    def __init__(self):
        self.escaped = 0

    def escape_inbox_page(self):
        self.escaped += 1
        return True


def _handler_on_inbox(owned_surfaces=frozenset()):
    """PopupHandler whose fast detection reports only the Inbox page."""
    handler = PopupHandler(FakeClick(), detection=object(), owned_surfaces=owned_surfaces)
    handler._fast_detect = lambda: {"inbox_page"}
    return handler


def test_an_unowned_inbox_is_left():
    """Landing on the inbox by accident, we leave it."""
    handler = _handler_on_inbox()
    assert handler.close_all() is True
    assert handler.click.escaped == 1


def test_an_owned_inbox_is_never_left():
    """DM read: the inbox IS the target, so the escape must not fire."""
    handler = _handler_on_inbox(owned_surfaces={"inbox_page"})
    assert handler.close_all() is False
    assert handler.click.escaped == 0


def test_the_slow_fallback_obeys_the_same_ownership():
    """lxml missing or the dump failing must not change who owns the screen."""

    class FakeDetection:
        def is_on_inbox_page(self):
            return True

        def _element_exists(self, selectors, timeout=1):
            return False

    for owned, expected in ((frozenset(), 1), ({"inbox_page"}, 0)):
        handler = PopupHandler(FakeClick(), FakeDetection(), owned_surfaces=owned)
        handler.click.close_system_popup = lambda: False
        handler.click.dismiss_notification_banner = lambda: False
        handler.detection.has_link_email_popup = lambda: False
        handler.detection.has_gdpr_popup = lambda: False
        handler.detection.has_follow_friends_popup = lambda: False
        handler.detection.has_collections_popup = lambda: False
        handler.detection.has_popup = lambda: False
        handler._close_all_slow()
        assert handler.click.escaped == expected


def test_the_dm_workflow_declares_the_inbox_as_its_own():
    """The declaration is what keeps the handler from fleeing the screen to read."""
    from taktik.core.social_media.tiktok.actions.business.workflows.dm.workflow import (
        DMWorkflow,
    )

    assert "inbox_page" in DMWorkflow.OWNED_SURFACES


def test_a_workflow_owns_nothing_unless_it_says_so():
    from taktik.core.social_media.tiktok.actions.business.workflows._internal.base_workflow import (
        BaseTikTokWorkflow,
    )

    assert BaseTikTokWorkflow.OWNED_SURFACES == frozenset()
