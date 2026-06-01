"""Navigation actions for Instagram compat diagnostics."""

import time

from loguru import logger

from bridges.compat.diagnostics.actions.instagram import action


@action("navigation.go_home")
def go_home(a, p):
    return a.nav.navigate_to_home()


@action("navigation.go_search")
def go_search(a, p):
    return a.nav.navigate_to_search()


@action("navigation.go_profile_tab")
def go_profile_tab(a, p):
    return a.nav.navigate_to_profile_tab()


@action("navigation.open_profile")
def open_profile(a, p):
    username = p.get("username", "")
    if not username:
        logger.error("Missing 'username' param")
        return False
    return a.nav.navigate_to_profile(username)


@action("navigation.press_back")
def nav_back(a, p):
    count = int(p.get("count", 1))
    for _ in range(count):
        a.device.press("back")
        time.sleep(0.6)
    return True


@action("navigation.go_home_button")
def go_home_button(a, p):
    a.device.home()
    time.sleep(1)
    return True

