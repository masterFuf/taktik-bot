"""Every Lab action id the bot registers is visible to a reader of the source.

The desktop app's gate (`check-cartography-contracts.cjs`) and the census
(`scripts/inventory_capabilities.py`) compare the bot's action ids with the Lab catalogue by
reading the source, not by importing it. An id registered any other way (a loop, a computed name)
would escape both and the mirror would pass while a capability had no Lab entry.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import inventory_capabilities as inventory  # noqa: E402


def _live_registries():
    from bridges.compat.diagnostics.actions import instagram, tiktok
    from bridges.youtube.diagnostics import actions as youtube
    from bridges.youtube.diagnostics.runtime.registry import ACTION_REGISTRY as youtube_registry

    instagram.register_actions()
    tiktok.register_actions()
    youtube.register_actions()
    return {
        "instagram": instagram.ACTION_REGISTRY,
        "tiktok": tiktok.ACTION_REGISTRY,
        "youtube": youtube_registry,
    }


@pytest.mark.parametrize("platform", ["instagram", "tiktok", "youtube"])
def test_the_source_scan_finds_every_registered_id(platform):
    scanned = {action_id for action_id, _ in inventory.load_lab_actions().get(platform, [])}
    registered = set(_live_registries()[platform])

    assert registered, f"no {platform} action registered"
    assert sorted(registered - scanned) == [], "registered but not declared as a literal action(\"id\")"
    assert sorted(scanned - registered) == [], "declared in the source but never registered"
