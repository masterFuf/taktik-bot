"""Business logic for Instagram follower interactions.

Combines all follower-related mixins into a single class.
Each workflow lives in its own file for maintainability:
- workflow_legacy.py: interact_with_followers (pre-scraped list)
- workflow_direct.py: interact_with_followers_direct (click-in-list)
- workflow_multi_target.py: interact_with_target_followers (multi-target extraction)
"""

import os
from pathlib import Path
from typing import Dict, Any

from ....core.base_business_action import BaseBusinessAction

from .mixins import (
    FollowerNavigationMixin,
    FollowerCheckpointsMixin,
    FollowerExtractionMixin,
    FollowerInteractionsMixin,
)
from .workflows import (
    FollowerLegacyWorkflowMixin,
    FollowerDirectWorkflowMixin,
    FollowerMultiTargetWorkflowMixin,
)


class FollowerBusiness(
    FollowerLegacyWorkflowMixin,
    FollowerDirectWorkflowMixin,
    FollowerMultiTargetWorkflowMixin,
    FollowerNavigationMixin,
    FollowerCheckpointsMixin,
    FollowerExtractionMixin,
    FollowerInteractionsMixin,
    BaseBusinessAction
):
    """Business logic for Instagram follower interactions."""
    
    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device, session_manager, automation, "follower", init_business_modules=True)
        
        from ...common.workflow_defaults import FOLLOWERS_DEFAULTS
        self.default_config = {**FOLLOWERS_DEFAULTS}
        # Use AppData folder for checkpoints to avoid permission issues
        app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
        self.checkpoint_dir = Path(app_data) / 'taktik-desktop' / 'temp' / 'checkpoints'
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.current_checkpoint_file = None
        self.current_followers_list = []
        self.current_index = 0
        
        # Sélecteurs centralisés (depuis selectors.py)
        from .....ui.selectors import NAVIGATION_SELECTORS, FOLLOWERS_LIST_SELECTORS
        self._back_button_selectors = NAVIGATION_SELECTORS.back_buttons
        self._followers_list_selectors = FOLLOWERS_LIST_SELECTORS
