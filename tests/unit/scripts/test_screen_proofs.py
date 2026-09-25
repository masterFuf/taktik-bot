"""The two proofs of the screen photo: selector equality, and screen decisions replayed.

Captures are invented (public repository); the real corpus stays outside it.
"""

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

CORE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE / "scripts"))

import check_snapshot_equality as equality  # noqa: E402
import replay_screen_decisions as replay  # noqa: E402

PKG = "com.zhiliaoapp.musically:id/"


def _node(cls, rid="", text="", desc="", children="", bounds="[0,0][100,100]"):
    return (f'<node class="android.widget.{cls}" resource-id="{PKG + rid if rid else ""}" text="{text}" '
            f'content-desc="{desc}" package="com.zhiliaoapp.musically" clickable="true" enabled="true" '
            f'bounds="{bounds}">{children}</node>')


def _screen(*nodes):
    return '<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">' + "".join(nodes) + "</hierarchy>"


VIDEO = _screen(_node("FrameLayout", "long_press_layout", desc="Video", bounds="[0,0][1080,2400]", children=(
    _node("TextView", "title", text="demo_author", bounds="[40,1900][400,1950]")
    + _node("TextView", "desc", text="A caption that goes on and on... more", bounds="[40,1960][900,2100]")
    + _node("Button", "nhe", desc="Sound: original sound - demo_author", bounds="[900,2200][1040,2340]")
)))
LIVE = _screen(_node("FrameLayout", "long_press_layout", desc="LIVE", bounds="[0,0][1080,2400]", children=(
    _node("TextView", "tv_live_tips", text="Tap to watch LIVE", bounds="[300,1800][800,1850]")
    + _node("Button", "tv_live_nickname", text="demo_host", bounds="[40,1900][400,1950]")
)))


def test_every_version_override_is_checked():
    """An entry that exists only in an override (46.9.3 `video_state.live_preview`) was evaluated
    by no proof: the catalogue walk sees the baseline only."""
    data = yaml.safe_load((CORE / "taktik/core/compat/data/overrides/tiktok.yaml").read_text(encoding="utf-8"))
    entries = {selector for version in data["versions"].values() for selectors in version.values()
               for selector in selectors}
    assert entries and entries <= equality.override_selectors(("tiktok",))
    assert entries <= set(equality.catalogue_selectors(("tiktok",))[0])


def test_a_dump_is_filed_under_the_app_it_shows():
    assert equality.dump_platform(VIDEO) == "tiktok"
    assert equality.dump_platform('<node package="com.instagram.android" />') == "instagram"
    assert equality.dump_platform('<node package="com.android.systemui" />') is None


def test_the_lxml_comparison_sees_what_only_d_xpath_understands():
    check = equality.DumpCheck(VIDEO)
    assert check.lxml_agrees(f'//*[@resource-id="{PKG}title"]')
    assert not check.lxml_agrees(f"@{PKG}title")  # a uiautomator2 shorthand: lxml rejects it


def _answers(**overrides):
    base = {probe: {"answer": False, "gestures": [], "dumps": 3} for probe in replay.PROBES[:-1]}
    for probe, answer in overrides.items():
        base[probe] = answer
    return base


def test_identical_states_differ_nowhere():
    states = {("a.xml", "43.1.4"): _answers(), ("a.xml", "46.9.3"): _answers()}
    outcome = replay.compare(states, copy.deepcopy(states))
    assert (outcome["compared"], outcome["differences"]) == (2 * (len(replay.PROBES) - 1), 0)


def test_an_answer_or_a_gesture_that_changes_is_a_difference():
    before = {("a.xml", "43.1.4"): _answers(), ("b.xml", "43.1.4"): _answers()}
    after = {("a.xml", "43.1.4"): _answers(comments={"answer": True, "gestures": [], "dumps": 1}),
             ("b.xml", "43.1.4"): _answers(video_info_full={"answer": False, "gestures": ["click"], "dumps": 3})}
    outcome = replay.compare(before, after)
    assert outcome["differences"] == 2
    assert {example[2] for example in outcome["examples"]} == {"comments", "video_info_full"}


def test_a_read_that_exists_in_one_state_only_is_listed_not_compared():
    before = {("a.xml", "43.1.4"): _answers()}
    after = {("a.xml", "43.1.4"): dict(_answers(), read_screen={"answer": "video", "gestures": [], "dumps": 1})}
    outcome = replay.compare(before, after)
    assert outcome["differences"] == 0 and outcome["only_one_side"] == ["read_screen"]


def test_a_capture_missing_from_the_new_state_is_not_a_silent_pass():
    outcome = replay.compare({("a.xml", "43.1.4"): _answers()}, {})
    assert outcome["differences"] == len(replay.PROBES) - 1


def _child(tmp_path, xml, version, language="en", platform="tiktok"):
    capture = tmp_path / f"capture-{version}.xml"
    capture.write_text(xml, encoding="utf-8")
    files, out = tmp_path / f"files-{version}", tmp_path / f"out-{version}.json"
    files.write_text(str(capture), encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(CORE), "PYTHONIOENCODING": "utf-8"}
    done = subprocess.run(
        [sys.executable, str(CORE / "scripts" / "replay_screen_decisions.py"), "--child", "decisions",
         "--files", str(files), "--out", str(out), "--version", version, "--language", language,
         "--platform", platform],
        cwd=str(CORE), env=env, capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stderr[-1500:]
    return json.loads(out.read_text(encoding="utf-8"))[str(capture)]


def test_the_child_runs_the_production_reads_on_a_capture(tmp_path):
    answers = _child(tmp_path, VIDEO, "43.1.4")
    feed = answers["video_info_feed"]
    assert feed["answer"]["author"] == "demo_author" and feed["answer"]["is_ad"] is False
    assert feed["gestures"] == ["click"]  # production taps a cut English caption open
    assert feed["dumps"] > 0 and answers["comments"]["answer"] is False


def test_the_child_applies_the_version_overrides(tmp_path):
    """The 46.9.3 LIVE ids live in the YAML only: the version decides what the reads see."""
    assert _child(tmp_path, LIVE, "43.1.4")["video_info_feed"]["answer"]["is_live"] is False
    assert _child(tmp_path, LIVE, "46.9.3")["video_info_feed"]["answer"]["is_live"] is True


IG = "com.instagram.android"


def _ig_node(rid, text, bounds):
    return (f'<node index="0" text="{text}" resource-id="{IG}:id/{rid}" class="android.widget.TextView" '
            f'package="{IG}" content-desc="" clickable="true" enabled="true" bounds="{bounds}" />')


FOLLOW_LIST = ('<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
               f'<node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="{IG}" '
               'bounds="[0,0][1080,2400]">'
               + _ig_node("follow_list_username", "alice_demo", "[200,600][700,650]")
               + _ig_node("follow_list_row_large_follow_button", "Following", "[760,590][1040,660]")
               + _ig_node("follow_list_username", "bob_demo", "[200,780][700,830]")
               + _ig_node("follow_list_row_large_follow_button", "Follow back", "[760,770][1040,840]")
               + "</node></hierarchy>")


def test_the_instagram_child_reads_a_follow_list_as_production_mounts_it(tmp_path):
    answers = _child(tmp_path, FOLLOW_LIST, "410.0.0.53.71", platform="instagram")
    assert [row[0] for row in answers["list_rows"]["answer"]] == ["alice_demo", "bob_demo"]
    assert answers["row_states"]["answer"] == {"alice_demo": "following", "bob_demo": "follow_back"}
    assert answers["row_states"]["calls"] == 2
    assert answers["click_row"]["answer"] is True and answers["click_row"]["gestures"] == ["long_click"]
    assert [row[:2] for row in answers["unfollow_rows"]["answer"]["rows"]] == [
        ["alice_demo", "following"], ["bob_demo", "follow_back"]]


def test_the_instagram_child_asks_the_funnel_every_selector_list(tmp_path):
    """The shared funnel is asked every selector list of the catalogues its callers read, one
    call per list, on the same screen."""
    answers = _child(tmp_path, FOLLOW_LIST, "410.0.0.53.71", platform="instagram")
    field = "DETECTION_SELECTORS.follow_list_username_selectors"
    assert answers["funnel_present"]["answer"][field] is True
    assert answers["funnel_text"]["answer"][field] == "alice_demo"
    assert answers["funnel_wait"]["answer"][field] is True
    calls = answers["funnel_present"]["calls"]
    assert calls == len(answers["funnel_present"]["answer"]) > 100
    assert answers["funnel_present"]["dumps"] <= calls


def test_the_reads_made_once_per_row_are_counted_per_row():
    def answers(dumps):
        return {"list_rows": {"answer": [["a", [0, 0, 1, 1]]], "gestures": [], "dumps": 1},
                "row_states": {"answer": {"a": "follow"}, "gestures": [], "dumps": dumps, "calls": 2}}

    outcome = replay.compare({("a.xml", "410"): answers(8)}, {("a.xml", "410"): answers(2)},
                             replay.INSTAGRAM_PROBES)
    cell = outcome["per_probe"]["row_states"]["list"]
    assert outcome["differences"] == 0
    assert (cell["calls"], cell["sum_before"], cell["sum_after"]) == (2, 8, 2)
