#!/usr/bin/env python3
"""
DM Bridge for TAKTIK Desktop
Unified bridge for reading and sending Instagram DM messages.

Usage:
    python dm_bridge.py read <device_id> <limit>
    python dm_bridge.py send <device_id> <username> <message>
"""

import sys
import os

# Bootstrap: UTF-8 + loguru + sys.path in one call
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, bot_dir)
from bridges.common.runtime.bootstrap import setup_environment
setup_environment()

from bridges.common.input.keyboard import KeyboardService
from bridges.instagram.runtime.bridge import InstagramBridgeBase
from bridges.instagram.engagement.runtime.dm_navigation import DMInboxNavigationMixin
from bridges.instagram.engagement.runtime.dm_reader import DMConversationReaderMixin
from bridges.instagram.engagement.runtime.dm_sender import DMSenderMixin


class DMBridge(DMSenderMixin, DMConversationReaderMixin, DMInboxNavigationMixin, InstagramBridgeBase):
    """Bridge for DM operations between TAKTIK Desktop and Instagram."""

    def __init__(self, device_id: str, package_name: str = None):
        super().__init__(device_id, package_name=package_name)
        self._keyboard = KeyboardService(device_id)


def main():
    from bridges.instagram.engagement.runtime.dm_commands import run_dm_cli

    run_dm_cli(sys.argv[1:])


if __name__ == "__main__":
    main()
