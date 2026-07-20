"""'notifications' is not a desktop_bridge workflow — and must never fall through.

Reading the activity feed is owned by the notifications ENGAGEMENT bridge, which also
persists, dedups and closes Instagram. The legacy duplicate that treated notifications as
just another profile source has been removed.

The dangerous part is the config builder's `else`: anything it does not recognise becomes a
FOLLOWER interaction run. A stale caller asking for 'notifications' would therefore silently
start engaging profiles. It raises instead.
"""

import pytest

from taktik.core.social_media.instagram.workflows.core.config_builder import (
    build_instagram_automation_config,
)


def _raw(workflow_type: str) -> dict:
    return {
        "deviceId": "device-1",
        "workflowType": workflow_type,
        "target": "someone",
        "limits": {"maxProfiles": 10},
    }


def test_notifications_is_refused_rather_than_downgraded_to_a_follower_run():
    with pytest.raises(ValueError, match="notifications_bridge"):
        build_instagram_automation_config(_raw("notifications"))


def test_a_real_workflow_type_still_builds():
    config = build_instagram_automation_config(_raw("target_followers"))
    assert config["actions"][0]["type"] == "interact_with_followers"


def test_legacy_notifications_business_is_gone():
    # Its only caller was the removed runner branch; the module must not come back as a
    # second implementation of the same surface.
    with pytest.raises(ImportError):
        from taktik.core.social_media.instagram.actions.business.workflows import (  # noqa: F401
            NotificationsBusiness,
        )
