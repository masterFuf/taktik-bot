"""Business logic for Instagram follower interactions.

Single workflow since the deep-link era ended: workflows/direct.py's
interact_with_followers_direct (click-in-list navigation). Multi-target runs
distribute the budget at the automation level, one direct run per target.

Also hosts interact_with_profile_list (../profile_list): interacting with a chosen
list of profiles is the same extract->filter->interact pipeline with a different source
of usernames, so it is mixed in here rather than duplicating the plumbing elsewhere.
"""

import os

from taktik.core.shared.app_paths import get_app_data_dir
from pathlib import Path
from typing import Dict, Any

from ....core.base_business import BaseBusinessAction

from .mixins import (
    FollowerNavigationMixin,
    FollowerCheckpointsMixin,
    FollowerExtractionMixin,
)
from .workflows import (
    FollowerDirectWorkflowMixin,
)
from ..profile_list import ProfileListWorkflowMixin


class FollowerBusiness(
    FollowerDirectWorkflowMixin,
    ProfileListWorkflowMixin,
    FollowerNavigationMixin,
    FollowerCheckpointsMixin,
    FollowerExtractionMixin,
    BaseBusinessAction
):
    """Business logic for Instagram follower interactions."""
    
    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device, session_manager, automation, "follower", init_business_modules=True)
        
        from ...common.workflow_defaults import FOLLOWERS_DEFAULTS
        self.default_config = {**FOLLOWERS_DEFAULTS}
        # Use AppData folder for checkpoints to avoid permission issues
        app_data = get_app_data_dir()
        self.checkpoint_dir = Path(app_data) / 'temp' / 'checkpoints'
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.current_checkpoint_file = None
        self.current_followers_list = []
        self.current_index = 0
        
        # Sélecteurs centralisés (depuis selectors.py)
        from taktik.core.social_media.instagram.ui.selectors.shell.navigation import NAVIGATION_SELECTORS
        from taktik.core.social_media.instagram.ui.selectors.surfaces.followers_following import (
            FOLLOWERS_LIST_SELECTORS,
        )
        self._back_button_selectors = NAVIGATION_SELECTORS.back_buttons
        self._followers_list_selectors = FOLLOWERS_LIST_SELECTORS
