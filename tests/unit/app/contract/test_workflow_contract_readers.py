"""The payload readers follow the declared contract (`taktik/core/app/contract/`).

The declaration is the source of the app's types. These tests hold each reader to it: it reads
the declared keys and no other, applies the declared default when a key is absent, puts the
value of the wire key where the declaration says, accepts each alias with the wire key first, and
refuses what the declaration says it refuses, before the phone is touched. A setting read only
under a condition (`when`) is held to it under that condition, and not read without it; the
fields of a nested setting (`ai.*`) are held one by one.
"""

from __future__ import annotations

import pytest

from contract_probe import (
    Recording,
    declared_setting_paths,
    expected,
    expected_default,
    given,
    launch,
    leaves,
    payload_for,
    payload_of,
    probe,
    read,
    resolve,
    satisfied,
    value_of,
)
from taktik.core.app.contract import WORKFLOW_CONTRACTS
from taktik.core.app.contract.schema import Computed, OneOf


def _name(prefix, key):
    return ".".join((*prefix, key))


SETTINGS = [
    pytest.param(contract, prefix, item, id=f"{contract.workflow_id}:{_name(prefix, item.key)}")
    for contract in WORKFLOW_CONTRACTS
    for prefix, item in leaves(contract)
]
ALIASES = [
    pytest.param(contract, prefix, item, alias, id=f"{contract.workflow_id}:{_name(prefix, item.key)}<-{alias}")
    for contract in WORKFLOW_CONTRACTS
    for prefix, item in leaves(contract)
    for alias in item.aliases
]
REFUSALS = [
    pytest.param(contract, refusal, id=f"{contract.workflow_id}:{refusal.missing}")
    for contract in WORKFLOW_CONTRACTS
    for refusal in contract.refusals
]
CONTRACTS = [pytest.param(contract, id=contract.workflow_id) for contract in WORKFLOW_CONTRACTS]


def _payloads(contract):
    """A payload without any condition, and one per condition the declaration names."""
    out, seen = [payload_for(contract, {})], set()
    for prefix, item in leaves(contract):
        key = repr(sorted(item.when.items()))
        if item.when and key not in seen:
            seen.add(key)
            out.append(payload_of(contract, prefix, item, {}))
    return out


@pytest.mark.parametrize("contract", CONTRACTS)
def test_the_readers_read_the_declared_keys_and_no_other(contract):
    for base in _payloads(contract):
        log = set()
        payload = Recording(base, log)
        read(contract, payload)
        for item in contract.settings:
            if item.reader:
                resolve(item.reader)(payload)

        assert log <= declared_setting_paths(contract), f"read and not declared, under {base}"
        for prefix, item in leaves(contract):
            wire = (*prefix, item.key)
            if satisfied(item, base):
                # Every wire key is read, the fields of a nested setting when it is given; an alias
                # may be skipped once a name before it was given.
                if given(base, prefix) is not None:
                    assert wire in log, f"{wire} not read under {base}"
            else:
                assert wire not in log, f"{wire} read outside of its condition {dict(item.when)}"


@pytest.mark.parametrize("contract, prefix, item", SETTINGS)
def test_an_absent_key_takes_the_declared_default(contract, prefix, item):
    if item.required or isinstance(item.default, Computed):
        pytest.skip("no default to apply")
    payload = payload_of(contract, prefix, item, {})
    if any(given(payload, (*prefix, name)) is not None for name in item.names):
        pytest.skip("the run needs it here")

    assert value_of(contract, item, payload) == expected_default(item)


@pytest.mark.parametrize("contract, prefix, item", SETTINGS)
def test_the_wire_key_sets_what_the_declaration_says(contract, prefix, item):
    value = probe(item)
    payload = payload_of(contract, prefix, item, {item.key: value})

    assert value_of(contract, item, payload) == expected(item, value)


@pytest.mark.parametrize("contract, prefix, item, alias", ALIASES)
def test_an_alias_is_accepted_and_the_wire_key_comes_first(contract, prefix, item, alias):
    value, other = probe(item, 0), probe(item, 1)

    assert value_of(contract, item, payload_of(contract, prefix, item, {alias: value})) == expected(item, value)
    both = payload_of(contract, prefix, item, {item.key: value, alias: other})
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
        for prefix, item in leaves(contract):
            assert item.attr or item.reader, f"{contract.workflow_id}:{_name(prefix, item.key)}"


def test_every_condition_names_a_declared_setting_and_a_value_it_takes():
    for contract in WORKFLOW_CONTRACTS:
        declared = {(*prefix, item.key): item for prefix, item in leaves(contract)}
        for prefix, item in leaves(contract):
            for dotted, wanted in item.when.items():
                condition = declared.get(tuple(dotted.split(".")))
                where = f"{contract.workflow_id}:{_name(prefix, item.key)}"
                assert condition is not None, f"{where} depends on {dotted}, which is not declared"
                values = set(wanted) if isinstance(wanted, tuple) else {wanted}
                if isinstance(condition.type, OneOf):
                    assert values <= set(condition.type.values), where
                elif condition.type == "bool":
                    assert values <= {True, False}, where
