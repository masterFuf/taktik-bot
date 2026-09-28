"""No "share" setting on a TikTok profile visit (decision Q4 of 2026-09-27).

`shareProbability` was declared, read and drawn for every video, then nothing happened: the
branch was a "to implement" left empty. No page sent it. A setting the bot draws but never acts
on is a setting that lies, so it is gone from the declaration, the reader and the run's config.
"""

from __future__ import annotations

import dataclasses

from taktik.core.app.contract.tiktok_profiles import PROFILE_SETTINGS
from taktik.core.social_media.tiktok.actions.business.workflows.followers.models import FollowersConfig
from taktik.core.social_media.tiktok.actions.business.workflows.followers.payload import (
    followers_settings_from_payload,
)


def test_the_profile_settings_declare_no_share():
    declared = {name for field in PROFILE_SETTINGS for name in (field.key, *field.aliases)}

    assert not declared & {"shareProbability", "share_probability"}


def test_the_reader_reads_no_share():
    settings = followers_settings_from_payload({"shareProbability": 40, "share_probability": 0.4})

    assert "share_probability" not in settings


def test_the_run_config_has_no_share():
    assert "share_probability" not in {field.name for field in dataclasses.fields(FollowersConfig)}
