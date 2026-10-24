"""The DM reply finds the composer of an open conversation, and the composer lookup answers one way.

Measured on a Pixel 6 Pro (Instagram 410, Android 17, in French), 2026-10-24: the production DM
reply (`instagram.engagement.dm_send`, `DMSenderMixin.send_message`) crashed with
"AttributeError: 'XMLElement' object has no attribute 'exists'". The shared lookup
(`dm_composer.find_message_input`) handed back the resolved uiautomator2 `XMLElement` when its
xpath catalogue matched (the composer's resource-id, the first entry: every conversation), a
selector otherwise; the reply checks `.exists` on what it gets.

The screens are real dumps, anonymized: an open conversation on the Pixel 6 Pro (410) and one on
a Pixel 6a (447), both in French. The phone is uiautomator2's own xpath engine behind the clone
proxy the bridges mount, so the lookup gets exactly what it gets on a phone.
"""

import pytest
from uiautomator2.xpath import XPathEntry

import taktik.core.social_media.instagram.workflows.dm.sender as sender
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.social_media.instagram.actions.atomic.text import dm_composer
from taktik.core.social_media.instagram.workflows.dm.sender import DMSenderMixin
from unit.paths import CORE

PKG = "com.instagram.android"
FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
CONVERSATIONS = {
    "410": ((FIXTURES / "ig410_fr_dm_thread_pixel6pro.xml").read_text(encoding="utf-8"), (210, 1741, 827, 1916)),
    "447": ((FIXTURES / "ig447_fr_dm_thread.xml").read_text(encoding="utf-8"), (158, 1349, 621, 1480)),
}


class _Phone:
    wait_timeout = 0.0
    serial = "PHONE-1"

    def __init__(self, screen):
        self.screen = screen
        self.xpath = XPathEntry(self)
        self.taps = []

    def dump_hierarchy(self, *_a, **_k):
        return self.screen

    def app_current(self):
        return {"package": PKG}

    def click(self, x, y):
        self.taps.append((x, y))

    def long_click(self, x, y, _duration=0.0):
        self.click(x, y)


class _Reply(DMSenderMixin):
    """The DM runtime as far as the reply reads it: the device a bridge hands it."""

    def __init__(self, phone):
        self.device = CloneAwareDeviceProxy(phone, PKG)
        self.device_id = phone.serial
        self.typed = []

    def _type_dm_message(self, msg_input, message):
        self.typed.append(message)
        return False  # stop here: what follows the typing is not under test


@pytest.mark.parametrize("version", sorted(CONVERSATIONS))
def test_the_composer_lookup_answers_a_selector_on_a_real_conversation(version):
    screen, (left, top, right, bottom) = CONVERSATIONS[version]
    composer = dm_composer.find_message_input(CloneAwareDeviceProxy(_Phone(screen), PKG))

    assert composer is not None
    assert composer.exists
    bounds = composer.info["bounds"]
    assert (bounds["left"], bounds["top"], bounds["right"], bounds["bottom"]) == (left, top, right, bottom)


@pytest.mark.parametrize("version", sorted(CONVERSATIONS))
def test_the_dm_reply_taps_the_composer_and_types(monkeypatch, version):
    monkeypatch.setattr(sender, "ensure_taktik_keyboard", lambda _device_id: True)
    monkeypatch.setattr(sender.time, "sleep", lambda *_: None)
    screen, (left, top, right, bottom) = CONVERSATIONS[version]
    phone = _Phone(screen)
    reply = _Reply(phone)

    from taktik.core.social_media.instagram.workflows.dm.reply_check import ReplyOutcome

    assert reply.send_message("Bonjour") is ReplyOutcome.NOT_SENT  # the typing is stubbed out

    assert reply.typed == ["Bonjour"]
    (x, y), = phone.taps
    assert left <= x <= right and top <= y <= bottom
