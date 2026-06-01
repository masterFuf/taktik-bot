"""Navigation actions for TikTok compat diagnostics."""

from bridges.compat.diagnostics.actions.tiktok import action


@action("tt.navigation.go_home")
def go_home(a, p):
    return a.nav.navigate_to_home()


@action("tt.navigation.go_inbox")
def go_inbox(a, p):
    return a.nav.navigate_to_inbox()


@action("tt.navigation.go_profile")
def go_profile(a, p):
    return a.nav.navigate_to_profile()


@action("tt.navigation.go_back")
def go_back(a, p):
    return a.nav.go_back()

