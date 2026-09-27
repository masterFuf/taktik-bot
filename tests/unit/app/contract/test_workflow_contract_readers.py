"""The payload readers follow the declared contract (`taktik/core/app/contract/`).

The declaration is the source of the app's types. These tests hold each reader to it: it reads
the declared keys and no other, applies the declared default when a key is absent, puts the
value of the wire key where the declaration says, accepts each alias with the wire key first, and
refuses what the declaration says it refuses, before the phone is touched.
"""

from __future__ import annotations

import pytest

from contract_probe import (
    Recording,
    by_iteration,
    call_reader,
    expected,
    matches,
    expected_default,
    launch,
    names,
    payload_for,
    probe,
    read,
    resolve,
    value_of,
)
from taktik.core.app.contract import WORKFLOW_CONTRACTS
from taktik.core.app.contract.schema import Computed

SETTINGS = [
    pytest.param(contract, item, id=f"{contract.workflow_id}:{item.key}")
    for contract in WORKFLOW_CONTRACTS
    for item in contract.settings
]
ALIASES = [
    pytest.param(contract, item, alias, id=f"{contract.workflow_id}:{item.key}<-{alias}")
    for contract in WORKFLOW_CONTRACTS
    for item in contract.settings
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
    payload = Recording(payload_for(contract, {}), log)
    read(contract, payload)
    for item in contract.settings:
        if item.reader:
            call_reader(item.reader, payload, item.reader_kwargs)

    read_keys = {path[0] for path in log}
    # A reader may read what the bridge carries too (the dispatcher's `workflowType`).
    assert read_keys <= names(contract.settings) | names(contract.bridge_fields), "a key read and not declared"
    # Every wire key is read; an alias may be skipped once a name before it was given. A filter
    # criterion is read when present, by the merge of every flat key.
    # A key its reader skips because the run's required key came first (a single message beside
    # the list) is read in the alias and wire tests below instead.
    given = {contract.setting(key).reader for key in payload if key in names(contract.settings)}
    skipped = {item.key for item in contract.settings
               if item.reader in given and item.reader and item.key not in payload}
    assert {item.key for item in contract.settings if not by_iteration(item)} - skipped <= read_keys


@pytest.mark.parametrize("contract, item", SETTINGS)
def test_an_absent_key_takes_the_declared_default(contract, item):
    if item.required or isinstance(item.default, Computed) or item.unit == "merged":
        pytest.skip("no default to apply")
    payload = payload_for(contract, {})
    if any(name in payload for name in item.names):
        pytest.skip("the run needs it here")
    if item.reader and any(contract.setting(key).reader == item.reader for key in payload):
        pytest.skip("its reader returns the key the run needs instead")

    assert matches(item, value_of(contract, item, payload), expected_default(item))


@pytest.mark.parametrize("contract, item", SETTINGS)
def test_the_wire_key_sets_what_the_declaration_says(contract, item):
    value = probe(item)
    payload = payload_for(contract, {item.key: value})

    assert matches(item, value_of(contract, item, payload), expected(item, value))


@pytest.mark.parametrize("contract, item, alias", ALIASES)
def test_an_alias_is_accepted_and_the_wire_key_comes_first(contract, item, alias):
    value, other = probe(item, 0), probe(item, 1)

    assert matches(item, value_of(contract, item, payload_for(contract, {alias: value})), expected(item, value))
    if by_iteration(item):
        return  # the criteria merge keeps the last name of the payload, whichever it is
    both = payload_for(contract, {item.key: value, alias: other})
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
        for item in contract.settings:
            assert item.attr or item.reader, f"{contract.workflow_id}:{item.key}"
