"""The payload readers follow the declared contract (`taktik/core/app/contract/`).

The declaration is the source of the app's types. These tests hold each reader to it: it reads
the declared keys and no other, applies the declared default when a key is absent, puts the
value of the wire key where the declaration says, accepts each alias with the wire key first, and
refuses what the declaration says it refuses, before the phone is touched.

A nested setting (`limits.maxProfiles`) is held like a top-level one, under the settings it is
read for (`when`). A key the declaration says is handed on (`via`: the AI hooks, the AI service)
is held by being read, here for what the reader reads of it and by the bridge test for the rest.
"""

from __future__ import annotations

import pytest

from contract_probe import (
    Recording,
    by_iteration,
    call_reader,
    conditions,
    declared_reads,
    expected,
    matches,
    expected_default,
    launch,
    lookup,
    merge,
    names,
    nest,
    payload_for,
    probe,
    read,
    reading_variants,
    resolve,
    held_leaves,
    under,
    value_of,
)
from taktik.core.app.contract import WORKFLOW_CONTRACTS
from taktik.core.app.contract.schema import Computed, Shape, nested_fields

SETTINGS = [
    pytest.param(contract, path, item, when, id=f"{contract.workflow_id}:{'.'.join(path)}")
    for contract in WORKFLOW_CONTRACTS
    for path, item, when in held_leaves(contract)
]
ALIASES = [
    pytest.param(contract, path, item, when, alias, id=f"{contract.workflow_id}:{'.'.join(path)}<-{alias}")
    for contract in WORKFLOW_CONTRACTS
    for path, item, when in held_leaves(contract)
    for alias in item.aliases
]
REFUSALS = [
    pytest.param(contract, refusal, id=f"{contract.workflow_id}:{refusal.missing}")
    for contract in WORKFLOW_CONTRACTS
    for refusal in contract.refusals
]
CONTRACTS = [pytest.param(contract, id=contract.workflow_id) for contract in WORKFLOW_CONTRACTS]


@pytest.mark.parametrize("contract", CONTRACTS)
def test_the_readers_read_the_declared_keys_and_no_other(contract):
    log = set()
    skipped: set = set()
    for variant in reading_variants(contract):
        payload = Recording(payload_for(contract, variant), log)
        read(contract, payload)
        # A key its reader skips because a key of the same reader came first (the list beside a
        # single message) is read in the alias and wire tests below instead.
        shared = {contract.setting(key).reader for key in payload if key in names(contract.settings)} - {None}
        skipped |= {(item.key,) for item in contract.settings if item.reader in shared and item.key not in payload}
        for _, item, _, _ in nested_fields(contract.settings):
            if item.reader:
                call_reader(item.reader, payload, item.reader_kwargs)

    declared, owned = declared_reads(contract.settings)
    # A reader may read what the bridge carries too (the dispatcher's `workflowType`).
    declared = declared | {(name,) for name in names(contract.bridge_fields)}
    assert not {path for path in log if path not in declared and not under(path, owned)}, "a key read and not declared"
    # Every wire key is read; an alias may be skipped once a name before it was given. A filter
    # criterion is read when present, by the merge of every flat key. A key handed on whole (`via`)
    # is read further on: the bridge test holds it.
    must = {path for path, item, _, via in nested_fields(contract.settings) if via is None and not by_iteration(item)}
    assert must - skipped <= log, f"declared, never read: {sorted(must - skipped - log)}"



def _holds(when, payload) -> bool:
    """`payload` holds what `when` asks (a tuple: any of its values)."""
    for dotted, wanted in when.items():
        present, value = lookup(payload, tuple(dotted.split(".")))
        if not present or not (value in wanted if isinstance(wanted, tuple) else value == wanted):
            return False
    return True


@pytest.mark.parametrize("contract", CONTRACTS)
def test_a_key_is_never_read_outside_its_condition(contract):
    """`when` says the reader reads the key under it, and only there."""
    for variant in reading_variants(contract):
        base = payload_for(contract, variant)
        log: set = set()
        read(contract, Recording(base, log))
        wires = {}
        # A nested setting's object may be fetched whole before its condition is looked at: its
        # values are held, not the object.
        for path, item, when, _ in nested_fields(contract.settings):
            if not isinstance(item.type, Shape):
                wires.setdefault(path, []).append(when)
        for path, whens in wires.items():
            # A wire key declared under several conditions is read under any of them.
            if all(when for when in whens) and not any(_holds(when, base) for when in whens):
                assert path not in log, f"{'.'.join(path)} read outside of its condition, under {variant}"

@pytest.mark.parametrize("contract, path, item, when", SETTINGS)
def test_an_absent_key_takes_the_declared_default(contract, path, item, when):
    if item.required or isinstance(item.default, Computed) or item.unit == "merged":
        pytest.skip("no default to apply")
    payload = payload_for(contract, conditions(when))
    if any(lookup(payload, (*path[:-1], name))[0] for name in item.names):
        pytest.skip("the run needs it here")
    if item.reader and any(contract.setting(key).reader == item.reader for key in payload):
        pytest.skip("its reader returns the key the run needs instead")

    assert matches(item, value_of(contract, item, payload), expected_default(item))


@pytest.mark.parametrize("contract, path, item, when", SETTINGS)
def test_the_wire_key_sets_what_the_declaration_says(contract, path, item, when):
    value = probe(item)
    payload = payload_for(contract, merge(conditions(when), nest(path, value)))

    assert matches(item, value_of(contract, item, payload), expected(item, value))


@pytest.mark.parametrize("contract, path, item, when, alias", ALIASES)
def test_an_alias_is_accepted_and_the_wire_key_comes_first(contract, path, item, when, alias):
    value, other = probe(item, 0), probe(item, 1)
    at = conditions(when)

    alone = payload_for(contract, merge(at, nest((*path[:-1], alias), value)))
    assert matches(item, value_of(contract, item, alone), expected(item, value))
    if by_iteration(item):
        return  # the criteria merge keeps the last name of the payload, whichever it is
    both = payload_for(contract, merge(at, nest(path, value), nest((*path[:-1], alias), other)))
    assert matches(item, value_of(contract, item, both), expected(item, value))


@pytest.mark.parametrize("contract, refusal", REFUSALS)
def test_the_launcher_refuses_what_the_declaration_refuses(contract, refusal):
    extra = dict(refusal.when)
    payload = payload_for(contract, extra)
    for name in contract.setting(refusal.missing).names:
        payload.pop(name, None)

    with pytest.raises(ValueError):
        launch(contract, payload)


def test_every_setting_says_where_its_value_goes():
    for contract in WORKFLOW_CONTRACTS:
        for path, item, _, via in nested_fields(contract.settings):
            if not isinstance(item.type, Shape):
                assert item.attr or item.reader or via, f"{contract.workflow_id}:{'.'.join(path)}"
