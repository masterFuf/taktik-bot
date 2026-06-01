"""Story actions for Instagram compat diagnostics."""

import time

from bridges.compat.diagnostics.actions.instagram import action


@action("story.like")
def like_story(a, p):
    return a.click.click_story_like_button()


@action("story.go_to_next")
def story_next(a, p):
    return a.nav.navigate_to_next_story()


@action("story.go_to_previous")
def story_prev(a, p):
    a.device.swipe_right()
    return True


@action("story.close")
def story_close(a, p):
    a.device.press("back")
    time.sleep(0.5)
    return True

