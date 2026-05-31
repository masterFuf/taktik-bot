"""
BaseBusinessAction facade — composes all business action mixins.

Sub-modules:
- profile_processing.py  — Pipeline unifié extract→filter→interact→record
- popup_handling.py      — Gestion popups (likers, comments, follow suggestions)
- config_parsing.py      — Parsing config (filter criteria, interactions)
- interaction_engine.py   — Moteur d'interaction unifié (perform_interactions, stories, IPC)
- liker_extraction.py    — Extraction likers (post régulier, reel)
- stats_recording.py     — Enregistrement actions DB + stats + validation limites
"""

import time
import random
from typing import Optional, List, Dict, Any
from loguru import logger

from ..base_action import BaseAction
from ...atomic.navigation import NavigationActions
from ...atomic.detection import DetectionActions
from ...atomic.interaction import ClickActions
from ...atomic.scroll import ScrollActions
from ..stats import BaseStatsManager
from ....ui.selectors.shell.navigation import BUTTON_SELECTORS, NAVIGATION_SELECTORS
from ....ui.selectors.shell.popups import POPUP_SELECTORS
from ....ui.selectors.shell.screen_state import DETECTION_SELECTORS
from ....ui.selectors.surfaces.post import POST_SELECTORS
from ....ui.selectors.surfaces.profile import PROFILE_SELECTORS
from ....ui.extractors import InstagramUIExtractors

from .profile_processing import ProfileProcessingMixin, ProfileProcessingResult
from .popup_handling import PopupHandlingMixin
from .config_parsing import ConfigParsingMixin
from .interaction_engine import InteractionEngineMixin
from .liker_extraction import LikerExtractionMixin
from .stats_recording import StatsRecordingMixin


class BaseBusinessAction(
    ProfileProcessingMixin,
    PopupHandlingMixin,
    ConfigParsingMixin,
    InteractionEngineMixin,
    LikerExtractionMixin,
    StatsRecordingMixin,
    BaseAction
):
    def __init__(self, device, session_manager=None, automation=None, module_name="business", 
                 init_business_modules=False):
        super().__init__(device)
        self.session_manager = session_manager
        self.automation = automation
        self.logger = logger.bind(module=f"instagram-{module_name}-business")
        
        self.popup_selectors = POPUP_SELECTORS
        self.post_selectors = POST_SELECTORS
        self.detection_selectors = DETECTION_SELECTORS
        self.navigation_selectors = NAVIGATION_SELECTORS
        self.profile_selectors = PROFILE_SELECTORS
        self.button_selectors = BUTTON_SELECTORS
        
        self.selectors = DETECTION_SELECTORS
        
        self.ui_extractors = InstagramUIExtractors(device)
        
        self._init_atomic_actions()
        
        self.stats_manager = BaseStatsManager(module_name)
        
        if automation and hasattr(automation, 'active_account_id'):
            self.active_account_id = automation.active_account_id
        else:
            self.active_account_id = 1
        
        if init_business_modules:
            self._init_business_modules()
        
        self.default_config = {}
    
    def _init_atomic_actions(self):
        self.nav_actions = NavigationActions(self.device)
        self.detection_actions = DetectionActions(self.device)
        self.click_actions = ClickActions(self.device)
        self.scroll_actions = ScrollActions(self.device)
    
    def _init_business_modules(self):
        from ...business.management.profile import ProfileBusiness
        from ...business.management.content import ContentBusiness
        from ...business.management.filtering import FilteringBusiness
        from ...business.actions.like import LikeBusiness
        from ...business.actions.comment import CommentBusiness
        from ...business.actions.story import StoryBusiness
        
        self.profile_business = ProfileBusiness(self.device, self.session_manager)
        self.content_business = ContentBusiness(self.device, self.session_manager)
        self.filtering_business = FilteringBusiness(self.device, self.session_manager)
        self.like_business = LikeBusiness(self.device, self.session_manager, self.automation)
        self.comment_business = CommentBusiness(self.device, self.session_manager, self.automation)
        self.story_business = StoryBusiness(self.device, self.session_manager, self.automation)

    def _is_valid_username(self, username: str) -> bool:
        """Validate an Instagram username. Delegates to ui_extractors."""
        return self.ui_extractors.is_valid_username(username)

    def _is_reel_post(self) -> bool:
        return self.ui_extractors.is_reel_post(logger_instance=self.logger)


# Export for easier import
__all__ = ['BaseBusinessAction']
