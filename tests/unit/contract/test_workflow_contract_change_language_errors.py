"""The error types an Instagram language change declares are the ones its workflow and bridge emit.

`INSTAGRAM_CHANGE_LANGUAGE_ERROR` (`contract/accounts.py`) is the closed set of `account_result.error_type`
of `instagram.account.change_language`. Read from the source: each code the workflow fails with
(`ChangeLanguageWorkflow._fail(result, message, <code>, step)`) and the one its bridge gives a crash.
A code emitted and not declared, or declared and emitted nowhere, is red.
"""

import ast

from taktik.core.contract.accounts import INSTAGRAM_CHANGE_LANGUAGE_ERROR
from unit.paths import CORE

WORKFLOW = CORE / "taktik/core/social_media/instagram/workflows/account/change_language_workflow.py"
BRIDGE = CORE / "bridges/instagram/account/language.py"


def _failure_codes(path):
    """The literal codes passed to `_fail(...)` (third argument) in `path`."""
    codes = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "_fail":
            code = node.args[2]
            assert isinstance(code, ast.Constant), f"{path.name}:{node.lineno}: a code is a literal"
            codes.add(code.value)
    return codes


def _error_type_keywords(path):
    """The literal `error_type=` values written in `path`."""
    return {
        keyword.value.value
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "error_type" and isinstance(keyword.value, ast.Constant) and keyword.value.value
    }


def test_the_declared_error_types_are_the_ones_emitted():
    emitted = _failure_codes(WORKFLOW) | _error_type_keywords(BRIDGE)

    assert set(INSTAGRAM_CHANGE_LANGUAGE_ERROR.values) == emitted


def test_a_language_not_applied_has_its_own_code():
    assert {"language_not_applied", "language_unreadable", "app_not_restarted"} <= _failure_codes(WORKFLOW)
