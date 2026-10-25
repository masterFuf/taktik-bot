"""The bridges' entry registers the platforms' selectors before it builds the bridge, so before any
phone connects, and each loader hands the platform's one declaration."""

import json
import sys

import pytest

from bridges.common import entrypoint
from bridges.common.selector_platforms import register_selector_platforms
from taktik.core.compat.selectors import platforms
from taktik.core.social_media.instagram.ui.selectors import domains as instagram_domains
from taktik.core.social_media.tiktok.ui.selectors import domains as tiktok_domains


@pytest.fixture
def no_host(monkeypatch):
    monkeypatch.setattr(platforms, "_LOADERS", {})
    monkeypatch.setattr(platforms, "_LOADED", {})


def test_the_entry_of_every_bridge_registers_the_platforms_before_building_it(no_host, monkeypatch, tmp_path):
    seen = []

    class _Bridge:
        def __init__(self, config):
            seen.append(platforms.registered_platforms())

        def run(self):
            return 0

    config = tmp_path / "config.json"
    config.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["bridge", str(config)])
    with pytest.raises(SystemExit) as exit_info:
        entrypoint.run_bridge_main(_Bridge)

    assert exit_info.value.code == 0
    assert seen == [("instagram", "tiktok")]


def test_the_bridges_register_each_platform_s_declaration(no_host):
    register_selector_platforms()
    assert platforms.platform_selectors("instagram") is instagram_domains.CATALOGUES
    assert platforms.platform_selectors("tiktok") is tiktok_domains.CATALOGUES

