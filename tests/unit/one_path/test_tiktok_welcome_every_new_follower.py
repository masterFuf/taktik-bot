"""The welcome DM the New followers page asks for, through the desktop bridge: every new follower
detected is written to, whatever the AI said of them, and nobody is followed back.

The payload is what the app's builder produces with the page's switch on
(`buildTikTokNewFollowersScrapeStartConfig`, held to these values by the app's
`scheduler:contracts`), plus what the main process adds (the key). The phone, the AI's answers and
the send are the rig's; the bridge, the launcher, the welcome pass and its decisions are the real
ones.
"""
import json

#: The `ai` block of the page's payload, "Write to every new follower" on, key for key.
PAGE_WELCOME_AI = {
    "enabled": True,
    "newFollowers": {
        "enabled": True, "welcomeDm": True, "followBack": False, "dmRequiresFollowBack": False,
        "maxDms": 4, "messages": ["Bienvenue !", " Merci "],
    },
}


def _page_payload(inbox_payload):
    ai = json.loads(json.dumps(PAGE_WELCOME_AI))
    ai["openrouterApiKey"] = "test-openrouter-key"  # added by the main process
    return inbox_payload("new_followers", maxItems=25, language="fr", ai=ai)


def _turned_down(rig):
    rig.install_dm_database()
    rig.show_welcome_verdicts()
    rig.show_inbox_lists()
    rig.verdicts["fan_two"] = {"relevant": False, "score": 0.1, "reason": "off niche", "follow": False,
                               "comment": False, "like": False}


def test_the_page_welcome_writes_to_a_follower_the_ai_turned_down(rig, inbox_payload):
    """Would have caught the page's switch reaching the bot and the pass writing only to the
    followers the AI approved: the product decision is every new follower detected."""
    _turned_down(rig)

    code = rig.run_bridge(_page_payload(inbox_payload))

    assert code == 0
    sent = [call.split(" ", 1)[1] for call in rig.calls if call.startswith("welcome_dm ")]
    assert sent == ["fan_one", "fan_two"]
    run = [call for call in rig.calls if call.startswith("outreach_run ")]
    assert len(run) == 1 and "['Bienvenue !', 'Merci'] max=4" in run[0]
    results = {event["username"]: event["success"] for kind, event in rig.events if kind == "dm_result"}
    assert results == {"fan_one": True, "fan_two": True}


def test_the_page_welcome_follows_nobody_back(rig, inbox_payload):
    """The operator picks each kind of action: this switch writes, the follow-back has its own button."""
    _turned_down(rig)

    rig.run_bridge(_page_payload(inbox_payload))

    assert not [kind for kind, _event in rig.events if kind == "follow_back_result"]
    assert not [call for call in rig.calls if "follow_back" in call]
