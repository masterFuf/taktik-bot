"""The replay of the Lab corpus reads its dumps where `--corpus` says, the repository by default.

`scripts/lab/replay_selector_corpus.py` looked for the dumps under its own repository only
(`debug_ui/`, local and never versioned): from a worktree, which holds no corpus, the replay said
« nothing to replay » and checked nothing. `--corpus <folder>` names the checkout that holds
`debug_ui/`; the dumps are read there, in place.

The replay itself (two states of the catalogue, a pool of workers) is replaced here by its result:
what is under test is where the dumps are read from. The dump is a real one, Instagram 410 in French.
"""

import shutil
import sys

import pytest

from unit.paths import CORE

sys.path.insert(0, str(CORE / "scripts/lab"))

import replay_selector_corpus as script  # noqa: E402

DUMP = CORE / "tests/unit/social_media/instagram/fixtures/ig410_fr_profile_follow_back.xml"
MATCHES = "//*[@package]"
MATCHES_NOTHING = "//*[@resource-id='no.such.screen']"


class _InlinePool:
    """The pool of workers, run in this process."""

    def __init__(self, _workers):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def map(self, function, items):
        return [function(item) for item in items]


@pytest.fixture
def corpus(tmp_path):
    """A checkout that holds a corpus: one baseline dump, where the Lab writes them."""
    folder = tmp_path / "debug_ui" / "cartography" / "device_1" / "instagram" / script.BASELINE / "profile"
    folder.mkdir(parents=True)
    shutil.copyfile(DUMP, folder / "profile_follow_back.xml")
    return tmp_path


def _replay(monkeypatch, capsys, args, now):
    """`main` on `args`, the base catalogue matching the dump and the working tree's `now`."""
    states = {"base": {"PROFILE_SELECTORS.header": [MATCHES]}, "now": {"PROFILE_SELECTORS.header": now}}
    monkeypatch.setattr(script, "_extract", lambda revision, workdir: workdir)
    monkeypatch.setattr(script, "_fields_of", lambda root, workdir, label: states[label])
    monkeypatch.setattr(script.multiprocessing, "Pool", _InlinePool)
    code = script.main(args)
    return code, capsys.readouterr().out


def test_the_dumps_are_read_under_the_corpus_given(monkeypatch, capsys, corpus):
    code, out = _replay(monkeypatch, capsys, ["--corpus", str(corpus)], [MATCHES])

    assert code == 0, out
    assert f"1 dumps {script.BASELINE}" in out


def test_a_field_that_loses_a_dump_of_the_corpus_given_is_said(monkeypatch, capsys, corpus):
    code, out = _replay(monkeypatch, capsys, ["--corpus", str(corpus)], [MATCHES_NOTHING])

    assert code == 1
    assert "LOSS PROFILE_SELECTORS.header: 1 -> 0" in out
    # The dump is named from the corpus it was read in, not from the repository of the script.
    assert "debug_ui" in out and "profile_follow_back.xml" in out and ".." not in out


def test_a_corpus_without_baseline_dumps_says_so(monkeypatch, capsys, tmp_path):
    code, out = _replay(monkeypatch, capsys, ["--corpus", str(tmp_path)], [MATCHES])

    assert code == 0
    assert "nothing to replay" in out
    assert str(tmp_path) in out


def test_without_the_option_the_corpus_is_the_repository():
    assert script.parse_args([]).corpus == script.ROOT
