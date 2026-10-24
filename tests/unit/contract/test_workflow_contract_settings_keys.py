"""A key the declaration of a workflow does not have is named, with where it is declared.

Phone session of 2026-10-24 (P8): `taktik workflows run instagram.automation.feed --json
'{"maxProfiles": 2, "durationMinutes": 10, ...}'` was accepted without a word, the dry run said
« resolves », and the run took its defaults (20 posts): the declaration reads those two settings
under `limits` and `session`. `undeclared_settings` reads the same declaration the app turns into
its tools' strict schema (`workflowSettingsSchema`): the names, the aliases, the nested settings,
the settings another value of the selector reads.
"""

import pytest

from taktik.core.contract.settings_keys import undeclared_settings


def _said(workflow_id, payload, host_keys=()):
    return [(item.path, item.declared_at, item.read_by) for item in
            undeclared_settings(workflow_id, payload, host_keys)]


def test_the_session_keys_at_the_root_are_named_with_where_they_are_declared():
    said = _said("instagram.automation.feed", {"maxProfiles": 2, "durationMinutes": 10})
    assert said == [
        ("maxProfiles", ("limits.maxProfiles", "feedStories.maxProfiles"), ()),
        ("durationMinutes", ("session.durationMinutes",), ()),
    ]


def test_the_same_settings_where_the_declaration_reads_them_pass():
    assert _said("instagram.automation.feed",
                 {"limits": {"maxProfiles": 2}, "session": {"durationMinutes": 10}}) == []


def test_a_key_unknown_inside_a_nested_setting_is_named_by_its_path():
    assert _said("instagram.automation.feed", {"limits": {"max_profile": 2}}) == [
        ("limits.max_profile", (), ()),
    ]


def test_a_spelling_the_reader_accepts_passes():
    # `max_videos` is an alias of `maxVideos`, the name a CLI run or an Agent plan may send.
    assert _said("tiktok.automation.for_you", {"max_videos": 20, "maxVideos": 20}) == []


def test_another_spelling_of_a_declared_name_is_shown_its_name():
    assert _said("instagram.automation.feed", {"limits": {"max_profiles": 2}}) == [
        ("limits.max_profiles", ("limits.maxProfiles", "feedStories.maxProfiles"), ()),
    ]


def test_what_a_setting_read_whole_holds_is_not_judged():
    # `ai.nicheTaxonomy` of the TikTok automation is an object its reader takes whole.
    assert _said("tiktok.automation.for_you", {"ai": {"nicheTaxonomy": {"anything": {"deep": 1}}}}) == []


def test_what_a_setting_handed_to_a_function_holds_is_that_function_s():
    # `behaviorPolicy` goes whole to the pacing parser (`via`), which reads `profile` too.
    assert _said("instagram.automation.feed", {"behaviorPolicy": {"profile": "prudent"}}) == []


def test_a_setting_another_workflow_of_the_declaration_reads_is_refused_with_who_reads_it():
    said = _said("instagram.automation.target_followers", {"feedStories": {"enabled": True}})
    assert said == [("feedStories", (), ("workflowType feed",))]


def test_the_bridge_fields_and_the_keys_the_host_fills_pass():
    assert _said("instagram.automation.feed", {"deviceId": "x", "networkReset": {}}) == []
    assert _said("tiktok.standalone.tiktok_unfollow", {"deviceId": "x"}, host_keys=("deviceId",)) == []
    assert _said("tiktok.standalone.tiktok_unfollow", {"deviceId": "x"}) == [("deviceId", (), ())]


def test_a_workflow_no_declaration_serves_is_a_key_error():
    with pytest.raises(KeyError):
        undeclared_settings("instagram.automation.nothing_like_it", {})
