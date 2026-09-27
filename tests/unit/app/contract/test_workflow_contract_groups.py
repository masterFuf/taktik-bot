"""The keys of a nested group follow the declaration, like top-level settings do.

A group is a nested setting whose keys are declared one by one (`actionProbabilities.follow`,
`filters.minFollowers`). For each key: the reader reads it, applies the declared default when it
is absent, puts its value where the declaration says, and takes the group's aliases (and its own)
with the wire names first.
"""

from __future__ import annotations

import pytest

from contract_probe import (
    Recording,
    expected,
    expected_default,
    is_group,
    payload_for,
    probe,
    read,
    value_of,
)
from taktik.core.app.contract import WORKFLOW_CONTRACTS

GROUPS = [
    pytest.param(contract, group, id=f"{contract.workflow_id}:{group.key}")
    for contract in WORKFLOW_CONTRACTS
    for group in contract.settings
    if is_group(group)
]
LEAVES = [
    pytest.param(contract, group, leaf, id=f"{contract.workflow_id}:{group.key}.{leaf.key}")
    for contract in WORKFLOW_CONTRACTS
    for group in contract.settings
    if is_group(group)
    for leaf in group.type.fields
]


@pytest.mark.parametrize("contract, group", GROUPS)
def test_the_reader_reads_every_key_of_a_group_and_no_other(contract, group):
    log = set()
    payload = payload_for(contract, {group.key: {leaf.key: probe(leaf) for leaf in group.type.fields}})
    read(contract, Recording(payload, log))

    below = {path[1] for path in log if len(path) == 2 and path[0] == group.key}
    declared = {name for leaf in group.type.fields for name in leaf.names}
    assert below <= declared, "a key of the group read and not declared"
    assert {leaf.key for leaf in group.type.fields} <= below, "a declared key of the group never read"


@pytest.mark.parametrize("contract, group, leaf", LEAVES)
def test_an_absent_key_of_a_group_takes_the_declared_default(contract, group, leaf):
    for payload in (payload_for(contract, {}), payload_for(contract, {group.key: {}})):
        assert value_of(contract, leaf, payload) == expected_default(leaf)


@pytest.mark.parametrize("contract, group, leaf", LEAVES)
def test_the_wire_key_of_a_group_sets_what_the_declaration_says(contract, group, leaf):
    value = probe(leaf)
    payload = payload_for(contract, {group.key: {leaf.key: value}})

    assert value_of(contract, leaf, payload) == expected(leaf, value)


@pytest.mark.parametrize("contract, group, leaf", LEAVES)
def test_the_aliases_of_a_group_are_accepted_and_the_wire_names_come_first(contract, group, leaf):
    value, other = probe(leaf, 0), probe(leaf, 1)
    for alias in group.aliases:
        alone = payload_for(contract, {alias: {leaf.key: value}})
        assert value_of(contract, leaf, alone) == expected(leaf, value)
        both = payload_for(contract, {group.key: {leaf.key: value}, alias: {leaf.key: other}})
        assert value_of(contract, leaf, both) == expected(leaf, value)
    for alias in leaf.aliases:
        alone = payload_for(contract, {group.key: {alias: value}})
        assert value_of(contract, leaf, alone) == expected(leaf, value)
        both = payload_for(contract, {group.key: {leaf.key: value, alias: other}})
        assert value_of(contract, leaf, both) == expected(leaf, value)
