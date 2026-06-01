"""Scroll actions for Instagram compat diagnostics."""

from bridges.compat.diagnostics.actions.instagram import action


@action("scroll.up")
def scroll_up(a, p):
    scale = float(p.get("scale", 0.8))
    a.device.swipe_up(scale=scale)
    return True


@action("scroll.down")
def scroll_down(a, p):
    scale = float(p.get("scale", 0.8))
    a.device.swipe_down(scale=scale)
    return True


@action("scroll.left")
def scroll_left(a, p):
    scale = float(p.get("scale", 0.8))
    a.device.swipe_left(scale=scale)
    return True


@action("scroll.right")
def scroll_right(a, p):
    scale = float(p.get("scale", 0.8))
    a.device.swipe_right(scale=scale)
    return True

