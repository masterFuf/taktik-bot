"""The screen-test gate: no new hand-written screen, and each kind of fake turns it red.

The fakes live in the gate itself (`self_test_cases`): written here, they would be screens this
file writes.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import audit_screen_test_fixtures as audit  # noqa: E402

SOURCES, FIXTURES = audit.read_tree()
CASES = audit.self_test_cases(SOURCES, FIXTURES)


def test_the_tests_write_no_screen_the_lists_do_not_name():
    assert audit.check(SOURCES, FIXTURES) == []


@pytest.mark.parametrize("name", CASES)
def test_each_fake_turns_the_gate_red(name):
    fake = CASES[name]
    assert audit.check(fake.get("sources", SOURCES), fake.get("fixtures", FIXTURES), fake.get("lists", audit.LISTS))


def test_a_real_dump_copied_into_fixtures_is_accepted():
    dump = FIXTURES["tests/unit/social_media/tiktok/fixtures/tt4314_fr_for_you_video.xml"]
    assert audit.fixture_problem("tests/unit/x/fixtures/copy.xml", dump) is None


def test_a_docstring_that_names_the_tag_is_not_a_screen():
    tag = "<" + "node>"  # split, or this file would write one
    source = f'"""Every element a {tag}, the widget type an attribute."""\nX = "{tag}"\n'
    assert audit.markup_literals(source) == 1
