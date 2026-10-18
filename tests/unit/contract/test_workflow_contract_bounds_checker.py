"""The checker of the settings' bounds (`contract/bounds.py`), on a declaration made for it.

What every reader of a declared workflow calls first: a number past either end, a list too short or
too long, a text too long, each named with its bounds; nested settings, lists of objects, aliases in
the reader's order, bounds under a condition; what is absent, null or no number left to the reader.
The declared bounds themselves are held in `test_workflow_contract_bounds.py`.
"""

from __future__ import annotations

import math

import pytest

from contract_probe import Recording
from taktik.core.contract.bounds import describe, out_of_bounds, refuse_out_of_bounds
from taktik.core.contract.schema import Bounds, Field, ListOf, OneOf, Shape, WorkflowContract

_ITEM = Shape(name="ProbeBoundsItem", fields=(Field("count", "int", bounds=Bounds(minimum=0, maximum=3)),))
_NESTED = Shape(name="ProbeBoundsNested", fields=(
    Field("rate", "number", default=5, bounds=Bounds(minimum=0, maximum=100)),
    Field("open", "int", bounds=Bounds(minimum=1, maximum=50, unbounded_at=0)),
))
PROBE = WorkflowContract(
    workflow_id="probe.bounds",
    name="ProbeBounds",
    bridge="probe_bridge",
    launcher="probe:launcher",
    reader="probe:reader",
    settings=(
        Field("mode", OneOf(("a", "b")), default="a"),
        Field("count", "int", aliases=("count_alias",), bounds=Bounds(minimum=1, maximum=10)),
        Field("onlyB", "int", when={"mode": "b"}, bounds=Bounds(maximum=5)),
        Field("scoped", "int", bounds=Bounds(minimum=1, when={"mode": ("b",)})),
        Field("names", ListOf("string"), bounds=Bounds(min_items=1, max_items=2, max_length=4)),
        Field("text", "string", bounds=Bounds(max_length=3)),
        Field("nested", _NESTED),
        Field("items", ListOf(_ITEM)),
        Field("free", "int"),
    ),
)


def test_values_inside_their_bounds_pass():
    payload = {"mode": "b", "count": 10, "onlyB": 5, "scoped": 1, "names": ["ab", "abcd"], "text": "abc",
               "nested": {"rate": 0, "open": 50}, "items": [{"count": 3}], "free": -99}
    assert out_of_bounds(PROBE, payload) == []


def test_a_number_past_either_end_is_named_with_its_bounds():
    assert out_of_bounds(PROBE, {"count": 11}) == ["count = 11, outside its bounds (1 to 10)"]
    assert out_of_bounds(PROBE, {"count": 0}) == ["count = 0, outside its bounds (1 to 10)"]
    assert out_of_bounds(PROBE, {"nested": {"rate": 100.5}}) == ["nested.rate = 100.5, outside its bounds (0 to 100)"]


def test_the_value_that_says_no_limit_is_accepted_beside_the_bounds():
    assert out_of_bounds(PROBE, {"nested": {"open": 0}}) == []
    assert out_of_bounds(PROBE, {"nested": {"open": 51}}) == [
        "nested.open = 51, outside its bounds (1 to 50, or 0 for no limit)"]


def test_the_name_the_reader_takes_is_the_one_held():
    # The alias alone is read; beside the wire key, the wire key wins, as the reader's order says.
    assert out_of_bounds(PROBE, {"count_alias": 0}) == ["count = 0, outside its bounds (1 to 10)"]
    assert out_of_bounds(PROBE, {"count": 5, "count_alias": 0}) == []


def test_a_key_outside_its_condition_is_neither_held_nor_read():
    log: set = set()
    assert out_of_bounds(PROBE, Recording({"mode": "a", "onlyB": 9}, log)) == []
    assert ("onlyB",) not in log
    assert out_of_bounds(PROBE, {"mode": "b", "onlyB": 9}) == ["onlyB = 9, outside its bounds (at most 5)"]


def test_bounds_under_a_condition_hold_only_there():
    assert out_of_bounds(PROBE, {"scoped": 0}) == []  # `mode` absent: its default, a
    assert out_of_bounds(PROBE, {"mode": "b", "scoped": 0}) == ["scoped = 0, outside its bounds (at least 1)"]


def test_a_list_is_held_to_its_count_and_each_text_to_its_length():
    assert out_of_bounds(PROBE, {"names": []}) == ["names has 0 items, outside its bounds (1 to 2 items)"]
    assert out_of_bounds(PROBE, {"names": ["a", "b", "c"]}) == ["names has 3 items, outside its bounds (1 to 2 items)"]
    assert out_of_bounds(PROBE, {"names": ["abcde"]}) == [
        "names[0] has 5 characters, outside its bounds (at most 4 characters)"]
    assert out_of_bounds(PROBE, {"text": "abcd"}) == ["text has 4 characters, outside its bounds (at most 3 characters)"]


def test_the_settings_of_a_list_of_objects_are_held_item_by_item():
    assert out_of_bounds(PROBE, {"items": [{"count": 1}, {"count": 4}]}) == [
        "items[1].count = 4, outside its bounds (0 to 3)"]


def test_absent_null_and_unreadable_values_are_left_to_the_reader():
    assert out_of_bounds(PROBE, {}) == []
    assert out_of_bounds(PROBE, {"count": None, "nested": None, "items": None}) == []
    assert out_of_bounds(PROBE, {"count": "many", "free": "x"}) == []
    assert out_of_bounds(PROBE, {"count": True}) == []


def test_a_number_written_as_text_or_not_a_number_is_held():
    assert out_of_bounds(PROBE, {"count": "11"}) == ["count = 11, outside its bounds (1 to 10)"]
    assert out_of_bounds(PROBE, {"count": math.nan}) == ["count = nan, outside its bounds (1 to 10)"]


def test_the_refusal_names_every_setting_out_of_bounds_in_the_readers_error():
    class ReaderError(ValueError):
        pass

    with pytest.raises(ReaderError) as refused:
        refuse_out_of_bounds(PROBE, {"count": 11, "text": "abcd"}, ReaderError)
    assert str(refused.value) == (
        "Refused before the phone is touched: count = 11, outside its bounds (1 to 10); "
        "text has 4 characters, outside its bounds (at most 3 characters)")
    refuse_out_of_bounds(PROBE, {"count": 3}, ReaderError)


def test_the_bounds_read_in_words():
    assert describe(Bounds(minimum=1, maximum=500)) == "1 to 500"
    assert describe(Bounds(minimum=0)) == "at least 0"
    assert describe(Bounds(maximum=0.5)) == "at most 0.5"
    assert describe(Bounds(minimum=1, maximum=50, unbounded_at=0)) == "1 to 50, or 0 for no limit"
    assert describe(Bounds(max_items=10, max_length=200)) == "at most 10 items, at most 200 characters"
