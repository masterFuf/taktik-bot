"""The TikTok publication reads its clone the way every run does (`package_name_from_payload`).

It read `packageName`, then `package_name`, by its own rule (`_first_given`: the first that is not
None): a package with spaces around it was taken as it was, a blank one was taken for a clone, and an
empty `packageName` hid the `package_name` behind it. The selectors were then patched for a package
that does not exist, and the video upload launched it.
"""

from __future__ import annotations

import pytest

from taktik.core.social_media.tiktok.workflows.publish.payload import publish_request_from_payload

CLONE = "com.example.tiktokclone"


def _package(**keys):
    return publish_request_from_payload({"localPath": "C:/media/clip.mp4", **keys}).package_name


@pytest.mark.parametrize("keys, package", [
    ({"packageName": f" {CLONE} "}, CLONE),
    ({"packageName": "  "}, None),
    ({"packageName": "", "package_name": CLONE}, CLONE),
    ({"package_name": CLONE}, CLONE),
    ({}, None),
], ids=["padded", "blank", "empty-wire-key-hides-the-alias", "cli-name", "absent"])
def test_the_clone_is_read_like_every_run_reads_it(keys, package):
    assert _package(**keys) == package
