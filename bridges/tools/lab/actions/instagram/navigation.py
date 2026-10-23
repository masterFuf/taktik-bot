"""Navigation actions for Instagram compat diagnostics."""

import time

from loguru import logger

from bridges.tools.lab.actions.instagram import action
from bridges.tools.lab.action_test.params import lab_flag


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
    """The production profile search (`navigate_to_profile`). `forceSearch` (default no): the
    search alone, never the deep link, as the cold DM opens its recipients; without it a search
    that finds nothing is hidden by the deep link that follows it."""
    username = p.get("username", "")
    if not username:
        logger.error("Missing 'username' param")
        return False
    return a.nav.navigate_to_profile(username, force_search=lab_flag(p, "forceSearch", False))


@action("navigation.press_back")
def nav_back(a, p):
    count = int(p.get("count", 1))
    for _ in range(count):
        a.device.press_back()
        time.sleep(0.6)
    return True


@action("navigation.go_home_button")
def go_home_button(a, p):
    a.device.home()
    time.sleep(1)
    return True

