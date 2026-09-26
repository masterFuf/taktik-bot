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
    conditions,
    declared_reads,
    expected,
    expected_default,
    launch,
    lookup,
    merge,
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
    for variant in reading_variants(contract):
        payload = Recording(payload_for(contract, variant), log)
        read(contract, payload)
        for _, item, _, _ in nested_fields(contract.settings):
            if item.reader:
                resolve(item.reader)(payload)

    declared, owned = declared_reads(contract.settings)
    must = {(*path[:-1], name) for path, item, _, via in nested_fields(contract.settings)
            if via is None for name in item.names}
    assert not {path for path in log if path not in declared and not under(path, owned)}, "read, not declared"
    assert must <= log, f"declared, never read: {sorted(must - log)}"


@pytest.mark.parametrize("contract, path, item, when", SETTINGS)
def test_an_absent_key_takes_the_declared_default(contract, path, item, when):
    if item.required or isinstance(item.default, Computed):
        pytest.skip("no default to apply")
    payload = payload_for(contract, conditions(when))
    if any(lookup(payload, (*path[:-1], name))[0] for name in item.names):
        pytest.skip("the run needs it here")

    assert value_of(contract, item, payload) == expected_default(item)


@pytest.mark.parametrize("contract, path, item, when", SETTINGS)
def test_the_wire_key_sets_what_the_declaration_says(contract, path, item, when):
    value = probe(item)
    payload = payload_for(contract, merge(conditions(when), nest(path, value)))

    assert value_of(contract, item, payload) == expected(item, value)


@pytest.mark.parametrize("contract, path, item, when, alias", ALIASES)
def test_an_alias_is_accepted_and_the_wire_key_comes_first(contract, path, item, when, alias):
    value, other = probe(item, 0), probe(item, 1)
    at = conditions(when)

    alone = payload_for(contract, merge(at, nest((*path[:-1], alias), value)))
    assert value_of(contract, item, alone) == expected(item, value)
    both = payload_for(contract, merge(at, nest(path, value), nest((*path[:-1], alias), other)))
    assert value_of(contract, item, both) == expected(item, value)


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
