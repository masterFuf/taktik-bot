"""The cold DM takes no keyboard from its host.

The send is the production one (`MessagingBusiness.send_in_open_conversation`), which reads the
keyboard of the device itself. A `keyboard` the host built and handed to the workflow was only kept,
never read: a second, unused way to say which keyboard types. The host's runtime and the workflow
no longer have the slot; a payload that still carries a `keyboard` key is read like any other key
it does not know (the payload reader keeps only the keys it names).
"""

import dataclasses
import inspect

from taktik.core.social_media.instagram.workflows.cold_dm.agent_handler import ColdDmRuntime
from taktik.core.social_media.instagram.workflows.cold_dm.payload import cold_dm_request_from_payload
from taktik.core.social_media.instagram.workflows.cold_dm.workflow import ColdDMWorkflow


def test_the_host_runtime_has_no_keyboard_slot():
    assert "keyboard" not in {field.name for field in dataclasses.fields(ColdDmRuntime)}


def test_the_workflow_asks_no_keyboard_of_its_host():
    assert "keyboard" not in inspect.signature(ColdDMWorkflow.__init__).parameters


def test_the_workflow_keeps_no_keyboard():
    workflow = ColdDMWorkflow(object(), object())
    assert not hasattr(workflow, "_keyboard")


def test_a_payload_that_still_carries_a_keyboard_key_is_read_without_it():
    request = cold_dm_request_from_payload(
        {"deviceId": "demo", "recipients": ["user_a"], "messages": ["hello"], "keyboard": "adb"},
        default_session_id="demo",
    )
    assert request.recipients == ["user_a"]
    assert not hasattr(request, "keyboard")
