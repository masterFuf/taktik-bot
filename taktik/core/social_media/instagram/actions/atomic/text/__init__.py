"""Text actions facade - backward-compatible TextActions class."""

from loguru import logger

from ...core.base_action import BaseAction
from ....ui.selectors import TEXT_INPUT_SELECTORS, DETECTION_SELECTORS

from .text_input import TextInputMixin
from .content_input import ContentInputMixin
from .keyboard_control import KeyboardControlMixin


class TextActions(
    TextInputMixin,
    ContentInputMixin,
    KeyboardControlMixin
):
    """
    Facade composing all text mixins.
    
    Sub-modules:
    - text_input.py        - Core typing (type_text, human delays, clear, generic _type_in_field)
    - content_input.py     - Domain-specific fields (comment, caption, bio, search bar, DM, validate)
    - keyboard_control.py  - Keys (enter, backspace), hide keyboard, clipboard (paste, select all)
    """
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="instagram-text-atomic")
        self.text_selectors = TEXT_INPUT_SELECTORS
        self.detection_selectors = DETECTION_SELECTORS


__all__ = ['TextActions']
