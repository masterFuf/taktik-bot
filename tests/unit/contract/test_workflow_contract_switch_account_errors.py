"""The error types an Instagram account switch declares are the ones its action returns.

`INSTAGRAM_SWITCH_ACCOUNT_ERROR` (`contract/accounts.py`) is the closed set of `account_result.error_type`
of `instagram.account.switch_account`. Read from the source: each code a `SwitchResult(...)` of the
switch action carries (its third argument, or `error_type=`). Its bridge adds none: a crash there is an
`error` line, not an `account_result`. A code returned and not declared, or declared and returned
nowhere, is red; so is a code without the key of its sentence in the app.
"""

import ast

from taktik.core.contract.accounts import (
    INSTAGRAM_ACCOUNT_SWITCH,
    INSTAGRAM_SWITCH_ACCOUNT_ERROR,
    INSTAGRAM_SWITCH_ACCOUNT_ERROR_PHRASES,
)
from taktik.core.contract.error_codes import BRIDGE_ERROR_PHRASES
from unit.paths import CORE

ACTION = CORE / "taktik/core/social_media/instagram/actions/account/switch/__init__.py"
BRIDGE = CORE / "bridges/instagram/account/switch.py"


def _switch_result_codes(path):
    """The `error_type` of every `SwitchResult(...)` built in `path`, each written as a literal."""
    codes = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "SwitchResult"):
            continue
        given = [kw.value for kw in node.keywords if kw.arg == "error_type"]
        code = given[0] if given else (node.args[2] if len(node.args) > 2 else None)
        if code is None:
            continue  # a success: no error type
        assert isinstance(code, ast.Constant) and isinstance(code.value, str), (
            f"{path.name}:{node.lineno}: an error type is a literal")
        codes.add(code.value)
    return codes


def _account_result_field(key):
    result = next(event for event in INSTAGRAM_ACCOUNT_SWITCH.events if event.type == "account_result")
    return next(item for item in result.fields if item.key == key)


def test_the_declared_error_types_are_the_ones_returned():
    assert set(INSTAGRAM_SWITCH_ACCOUNT_ERROR.values) == _switch_result_codes(ACTION)


def test_the_bridge_adds_no_error_type_of_its_own():
    assert "error_type=\"" not in BRIDGE.read_text(encoding="utf-8")
    assert "error_type='" not in BRIDGE.read_text(encoding="utf-8")


def test_the_result_refers_to_the_closed_set():
    field = _account_result_field("error_type")

    assert field.type is INSTAGRAM_SWITCH_ACCOUNT_ERROR
    assert field.nullable
    assert INSTAGRAM_SWITCH_ACCOUNT_ERROR.values == tuple(INSTAGRAM_SWITCH_ACCOUNT_ERROR_PHRASES)


def test_the_account_read_may_be_none():
    """With `verification_failed`, `switched_to` is the account read after the selection, or null when
    none could be read: never the target reported without being read."""
    assert _account_result_field("switched_to").nullable


def test_each_code_names_its_own_sentence_apart_from_the_bridge_codes():
    """The app reads these keys in the same namespace as the bridges' codes (`sessionLive`): one
    sentence per code, and no code nor key shared with the bridges' catalogue."""
    keys = list(INSTAGRAM_SWITCH_ACCOUNT_ERROR_PHRASES.values())
    for code, key in INSTAGRAM_SWITCH_ACCOUNT_ERROR_PHRASES.items():
        assert key.startswith("errorSwitch") and key.isidentifier(), (code, key)
    assert len(set(keys)) == len(keys)
    assert not set(INSTAGRAM_SWITCH_ACCOUNT_ERROR_PHRASES) & set(BRIDGE_ERROR_PHRASES)
    assert not set(keys) & set(BRIDGE_ERROR_PHRASES.values())
