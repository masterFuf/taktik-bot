"""Navigation actions for YouTube diagnostics."""

import time

from bridges.youtube.diagnostics.actions.support import try_tap
from bridges.youtube.diagnostics.runtime.events import log
from bridges.youtube.diagnostics.runtime.registry import action


@action("yt.navigation.go_home")
def go_home(d, p, _S):
    result = try_tap(d, _S.home_tab, timeout=4, label="home-tab")
    if result:
        time.sleep(1)
    return result


@action("yt.navigation.press_back")
def press_back(d, p, _S):
    count = int(p.get("count", 1))
    for _ in range(count):
        d.press("back")
        time.sleep(0.6)
    return True


@action("yt.navigation.home_button")
def home_button(d, p, _S):
    d.press("home")
    time.sleep(1)
    return True


@action("yt.navigation.launch")
def launch_youtube(d, p, _S):
    from taktik.core.social_media.youtube.ui.selectors.upload import YOUTUBE_PACKAGE

    log("info", "Stopping YouTube")
    d.app_stop(YOUTUBE_PACKAGE)
    time.sleep(1)
    log("info", "Starting YouTube")
    d.app_start(YOUTUBE_PACKAGE, "com.google.android.youtube.app.honeycomb.Shell$HomeActivity")
    time.sleep(4)
    app = d.app_current()
    is_yt = app.get("package") == YOUTUBE_PACKAGE
    log("info" if is_yt else "warning", "YouTube launched" if is_yt else "YouTube may not be in foreground")
    return is_yt
