"""Reopening a TikTok post from its link (`open_post_by_url`): the phone gets the whole link.

The link went to adb as a bare argument; adb joins its arguments into one line and the phone's
shell splits it again, so the `&` of a link copied from the web (`?is_from_webapp=1&sender_device=pc`)
ran `am start ... -d https://...?is_from_webapp=1` in the background and then tried a command named
after the package. What the phone reads is replayed on the arguments adb is launched with.
"""

import subprocess

from taktik.core.shared.device import adb
from taktik.core.social_media.tiktok.services.navigation import deeplink
from unit.android_shell import adb_line, phone_words

LINK = "https://www.tiktok.com/@creator/video/7412345678901234567?is_from_webapp=1&sender_device=pc"


def test_the_link_reaches_am_start_whole(monkeypatch):
    launched = []

    def run(argv, **kwargs):
        launched.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, "Starting: Intent { act=android.intent.action.VIEW }", "")

    monkeypatch.setattr(adb.subprocess, "run", run)
    monkeypatch.setattr(deeplink.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(deeplink, "first_matching", lambda device, selectors: True)

    assert deeplink.open_post_by_url(object(), LINK, device_id="SERIAL") is True

    stop, start = (phone_words(adb_line(argv)) for argv in launched)
    assert stop == ["am", "force-stop", deeplink._PACKAGE]
    assert start == ["am", "start", "-a", "android.intent.action.VIEW", "-d", LINK, deeplink._PACKAGE]
    assert all(argv[:3] == ["adb", "-s", "SERIAL"] for argv in launched)
