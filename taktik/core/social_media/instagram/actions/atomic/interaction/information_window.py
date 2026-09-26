"""Instagram information windows: acknowledged, never answered.

Instagram announces a feature in a promo dialog laid over the screen: an image, a headline, a
body, a primary action and sometimes a secondary one. On the story editor (IG 410.0.0.53.71,
English), "Your stories can now reach more people" covered the "Your story" button and the publish
stopped on `share_not_found`; once closed with "OK", the same flow published.

A window is recognised by its whole promo structure, and closed through its primary action only
when that action acknowledges ("OK"): an acknowledgement changes no setting. The secondary action
("View settings") is never tapped. A promo whose primary action is anything else is left on screen
and reported: the `igds_headline_*` ids are a generic chassis, and a button that accepts something
must not be pressed on the strength of its ids.
"""

import random
import time
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from loguru import logger

from ....ui.selectors.shell.popups import POPUP_SELECTORS

# A window that follows another one comes up quickly, if at all.
_NEXT_WINDOW_WAIT_S = 1.5


@dataclass(frozen=True)
class InformationWindows:
    """What `acknowledge_information_windows` did."""

    acknowledged: int = 0
    # Headline of a window left on screen (primary action not an acknowledgement, or tap failed).
    left_on_screen: str = ""

    @property
    def ok(self) -> bool:
        return not self.left_on_screen


def acknowledge_information_windows(
    device,
    *,
    unless_on_screen: Sequence[str] = (),
    wait_s: float = 6.0,
    settle_s: float = 3.0,
    max_windows: int = 2,
    log: Optional[Callable[[str, str], None]] = None,
) -> InformationWindows:
    """Close the information windows on screen through their acknowledgement ("OK").

    Waits up to `wait_s` for a window; stops waiting as soon as `unless_on_screen` shows (what the
    caller is after), and touches nothing then. At most `max_windows` taps.
    `device`: the Instagram device facade, or a uiautomator2 device (wrapped in it).
    """
    facade = _as_facade(device)
    say = log or _log_to_logger
    sel = POPUP_SELECTORS
    wanted = [unless_on_screen] if isinstance(unless_on_screen, str) else list(unless_on_screen)
    acknowledged = 0
    for _ in range(max_windows):
        photo = facade.wait_for_snapshot(
            lambda p: p.exists(sel.information_window) or bool(wanted and p.exists(wanted)),
            wait_s,
        )
        if photo is None or not photo.exists(sel.information_window):
            return InformationWindows(acknowledged)
        headline = _headline(photo)
        button = photo.first(sel.information_window_acknowledgement)
        if button is None or not button.bounds:
            say("warning", f"Information window left on screen, its primary action does not acknowledge: {headline}")
            return InformationWindows(acknowledged, headline)
        _reading_pause()
        if not facade.human_tap(button.bounds):
            return InformationWindows(acknowledged, headline)
        acknowledged += 1
        say("info", f"Information window acknowledged (OK): {headline}")
        facade.invalidate_snapshot()
        facade.wait_for_snapshot(lambda p: not p.exists(sel.information_window), settle_s)
        wait_s = _NEXT_WINDOW_WAIT_S
    return InformationWindows(acknowledged)


def _as_facade(device):
    # Looked up on the class: a mock answering every attribute is not taken for a facade.
    if callable(getattr(type(device), "wait_for_snapshot", None)):
        return device
    from ...core.device.facade import DeviceFacade

    return DeviceFacade(device)


def _headline(photo) -> str:
    node = photo.first(POPUP_SELECTORS.information_window_headline)
    return (node.text if node is not None else "") or "untitled"


def _reading_pause() -> None:
    # A person reads the window before closing it.
    time.sleep(random.uniform(0.6, 1.5))


def _log_to_logger(level: str, message: str) -> None:
    getattr(logger, level, logger.info)(f"[InformationWindow] {message}")
