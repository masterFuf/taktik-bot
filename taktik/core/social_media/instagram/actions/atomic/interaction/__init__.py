"""Interaction actions facade — backward-compatible ClickActions class."""

from loguru import logger

from ...core.base_action import BaseAction
from ....ui.selectors.shell.navigation import BUTTON_SELECTORS, NAVIGATION_SELECTORS
from ....ui.selectors.shell.popups import POPUP_SELECTORS
from ....ui.selectors.shell.screen_state import DETECTION_SELECTORS
from ....ui.selectors.surfaces.post import POST_SELECTORS
from ....ui.selectors.surfaces.profile import PROFILE_SELECTORS
from ....ui.selectors.surfaces.story_viewer import STORY_SELECTORS

from .post_interaction import PostInteractionMixin
from .profile_interaction import ProfileInteractionMixin
from .story_interaction import StoryInteractionMixin


class ClickActions(
    PostInteractionMixin,
    ProfileInteractionMixin,
    StoryInteractionMixin
):
    """
    Facade composing all interaction mixins.
    
    Sub-modules:
    - post_interaction.py      — Like/unlike/comment/share/save + grid clicks + close/back buttons
    - profile_interaction.py   — Follow/unfollow/message + follow state + review popup
    - story_interaction.py     — Story ring click + story like
    """
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="instagram-click-atomic")
        self.detection_selectors = DETECTION_SELECTORS
        self.selectors = BUTTON_SELECTORS  # Pour les boutons d'interaction
        self.profile_selectors = PROFILE_SELECTORS
        self.post_selectors = POST_SELECTORS
        self.navigation_selectors = NAVIGATION_SELECTORS
        self.story_selectors = STORY_SELECTORS
        self.popup_selectors = POPUP_SELECTORS


__all__ = ['ClickActions']
