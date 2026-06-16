"""Tests for PopupHandler.close_all skip_inbox_escape (DM read keeps the Inbox)."""

from taktik.core.social_media.tiktok.actions.business.workflows._internal.popup_handler import (
    PopupHandler,
)


class FakeClick:
    def __init__(self):
        self.escaped = 0

    def escape_inbox_page(self):
        self.escaped += 1
        return True


def _handler_on_inbox():
    """PopupHandler whose fast detection reports only the Inbox page."""
    handler = PopupHandler(FakeClick(), detection=object())
    handler._fast_detect = lambda: {"inbox_page"}
    return handler


def test_close_all_escapes_inbox_by_default():
    """Comportement historique : sur l'Inbox 'par accident', on la quitte."""
    handler = _handler_on_inbox()
    assert handler.close_all() is True
    assert handler.click.escaped == 1


def test_close_all_keeps_inbox_when_skip_requested():
    """DM read : l'Inbox est la cible — skip_inbox_escape ne doit PAS la quitter."""
    handler = _handler_on_inbox()
    assert handler.close_all(skip_inbox_escape=True) is False
    assert handler.click.escaped == 0
