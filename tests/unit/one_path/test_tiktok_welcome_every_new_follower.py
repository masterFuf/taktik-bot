"""The welcome DM the New followers page asks for, through the desktop bridge: every new follower
detected is written to, nobody is followed back, and the AI is asked nothing.

Product decision of 2026-09-27: no AI call, no cost and no AI licence when only the message is asked
for; the qualification serves the follow-back alone.

The payload is what the app's builder produces with the page's switch on
(`buildTikTokNewFollowersScrapeStartConfig`, held to these values by the app's
`scheduler:contracts`): the AI switch off, so the main process adds neither key nor persona. The
phone, the AI's answers and the send are the rig's; the bridge, the launcher, the welcome pass and
its decisions are the real ones.
"""
import json

#: The `ai` block of the page's payload, "Write to every new follower" on, key for key.
PAGE_WELCOME_AI = {
    "enabled": False,
    "newFollowers": {
        "enabled": True, "welcomeDm": True, "followBack": False, "dmRequiresFollowBack": False,
        "maxDms": 4, "messages": ["Bienvenue !", " Merci "],
    },
}


def _page_payload(inbox_payload, **ai_overrides):
    ai = json.loads(json.dumps(PAGE_WELCOME_AI))
    ai.update(ai_overrides)
    return inbox_payload("new_followers", maxItems=25, ai=ai)


def _turned_down(rig):
    rig.install_dm_database()
    rig.show_welcome_verdicts()
    rig.show_inbox_lists()
    rig.verdicts["fan_two"] = {"relevant": False, "score": 0.1, "reason": "off niche", "follow": False,
                               "comment": False, "like": False}


def _sent(rig):
    return [call.split(" ", 1)[1] for call in rig.calls if call.startswith("welcome_dm ")]


def _asked_the_ai(rig):
    return {
        "services": rig.ai_services,
        "calls": [call for call in rig.calls if call.startswith(("ai_classify", "screenshot"))],
        "events": [kind for kind, _event in rig.events if kind.startswith("ai_")],
    }


NOTHING_ASKED = {"services": [], "calls": [], "events": []}


def test_the_page_welcome_writes_to_every_new_follower_without_the_ai(rig, inbox_payload):
    """Would have caught the page's welcome, sent with the AI off, never reaching a follower: the
    pass required `ai.enabled`, and so the licence's AI and a key."""
    _turned_down(rig)

    code = rig.run_bridge(_page_payload(inbox_payload))

    assert code == 0
    assert _sent(rig) == ["fan_one", "fan_two"]
    run = [call for call in rig.calls if call.startswith("outreach_run ")]
    assert len(run) == 1 and "['Bienvenue !', 'Merci'] max=4" in run[0]
    results = {event["username"]: event["success"] for kind, event in rig.events if kind == "dm_result"}
    assert results == {"fan_one": True, "fan_two": True}
    assert _asked_the_ai(rig) == NOTHING_ASKED
    # Each row is still opened: the page shows display names, the handle is read on the profile.
    assert [call for call in rig.calls if call.startswith("open_follower_profile ")] == [
        "open_follower_profile fan_one", "open_follower_profile Fan Two", "open_follower_profile Emile B"]


def test_a_welcome_without_follow_back_asks_the_ai_nothing_even_with_the_ai_on(rig, inbox_payload):
    """A plan, or an app from before the decision, may still send the AI switch on with a key.

    Would have caught one paid qualification per follower for a welcome that reads no verdict, and
    a follower the AI turned down written to only by chance of the verdict being ignored.
    """
    _turned_down(rig)

    code = rig.run_bridge(_page_payload(inbox_payload, enabled=True, openrouterApiKey="test-openrouter-key"))

    assert code == 0
    assert _sent(rig) == ["fan_one", "fan_two"]
    assert _asked_the_ai(rig) == NOTHING_ASKED


def test_a_follow_back_asked_for_still_qualifies_each_follower(rig, inbox_payload):
    """The verdict decides the follow-back: asked for, each reached follower is qualified as before."""
    _turned_down(rig)
    ai = {"enabled": True, "openrouterApiKey": "test-openrouter-key"}
    payload = _page_payload(inbox_payload, **ai)
    payload["ai"]["newFollowers"]["followBack"] = True

    rig.run_bridge(payload)

    assert [call for call in rig.calls if call.startswith("ai_classify")] == ["ai_classify fan_one",
                                                                               "ai_classify fan_two"]
    assert len(rig.ai_services) == 1
    assert _sent(rig) == ["fan_one", "fan_two"]


def test_the_page_welcome_follows_nobody_back(rig, inbox_payload):
    """The operator picks each kind of action: this switch writes, the follow-back has its own button."""
    _turned_down(rig)

    rig.run_bridge(_page_payload(inbox_payload))

    assert not [kind for kind, _event in rig.events if kind == "follow_back_result"]
    assert not [call for call in rig.calls if "follow_back" in call]
