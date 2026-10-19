"""The catalogue of the bridges' error codes (`contract/error_codes.py`) is the codes the bot emits.

The census reads the source of the bridges and of the core (`bridges/`, `taktik/`): every
`error_code=` given to a call, every second argument of `send_error` or of an IPC's `error`, every
`"error_code"` of a line written as a dict, every `error_code` a coded exception declares. A code the
bot starts emitting and the catalogue does not list (so without a sentence in the app), or a listed
code nothing emits any more, is red. A code the census cannot read (built from a variable it cannot
follow) is red too: the catalogue could not be held to it.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, Iterator, Optional, Set, Tuple

from taktik.core.contract.error_codes import BRIDGE_ERROR_CODE, BRIDGE_ERROR_PHRASES
from taktik.core.contract.shared import ERROR_EVENT
from unit.paths import CORE

ROOTS = ("bridges", "taktik")

#: Codes read from a value the census cannot follow, and where they come from instead. The Instagram
#: publication sends the `error_type` its workflow returns, built by `InstagramPostWorkflow._error`.
PUBLISH_BRIDGE = "bridges/instagram/publish/bridge.py"
PUBLISH_WORKFLOW = "taktik/core/social_media/instagram/workflows/publish/post_workflow.py"


def _string(node) -> Optional[str]:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _factory_codes(path: Path, factory: str) -> Set[str]:
    """The first argument of every call to `self.<factory>(...)` in `path`, all written as literals."""
    codes = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == factory:
            code = _string(node.args[0]) if node.args else None
            assert code is not None, f"{path}:{node.lineno}: a code built from a variable"
            codes.add(code)
    return codes


def _functions(tree: ast.Module) -> Iterator[ast.AST]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _parameters(function) -> Set[str]:
    args = function.args
    return {a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)}


def _enclosing(tree: ast.Module, target: ast.AST):
    """The innermost function that holds `target`, or None at module level."""
    found = None
    for function in _functions(tree):
        if any(node is target for node in ast.walk(function)):
            if found is None or any(node is function for node in ast.walk(found)):
                found = function
    return found


class Census:
    def __init__(self) -> None:
        self.codes: Dict[str, Set[str]] = {}
        self.unreadable: list = []

    def add(self, code: str, where: str) -> None:
        self.codes.setdefault(code, set()).add(where)

    def resolve(self, value, tree, at, where: str) -> None:
        """Every code `value` can be: a literal, either side of a condition, a variable of the function
        or a constant of the module set from them. A parameter, or the `error_code` of a coded
        exception, is counted where it is set."""
        if isinstance(value, ast.Constant):
            if value.value is not None:
                self.add(value.value, where)
            return
        if isinstance(value, ast.IfExp):
            self.resolve(value.body, tree, at, where)
            self.resolve(value.orelse, tree, at, where)
            return
        if isinstance(value, ast.Attribute) and value.attr == "error_code":
            return
        if isinstance(value, ast.Name):
            function = _enclosing(tree, at)
            if function is not None and value.id in _parameters(function):
                return
            assigned = _assigned(function, value.id) if function is not None else []
            assigned = assigned or [node.value for node in tree.body if isinstance(node, ast.Assign)
                                    and any(isinstance(t, ast.Name) and t.id == value.id for t in node.targets)]
            if assigned:
                for item in assigned:
                    self.resolve(item, tree, at, where)
                return
        if where.startswith(PUBLISH_BRIDGE):
            for code in _factory_codes(CORE / PUBLISH_WORKFLOW, "_error"):
                self.add(code, where)
            return
        self.unreadable.append(f"{where}: {ast.unparse(value)}")


def _assigned(scope, name: str) -> list:
    """The values `name` is set to in `scope`."""
    return [node.value for node in ast.walk(scope) if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)]


def _emitter_receiver(func) -> bool:
    """`ipc.error(...)`, `_ipc.error(...)`, `notifier.error(...)`, `self.ipc.error(...)`: an IPC's error."""
    if not (isinstance(func, ast.Attribute) and func.attr == "error"):
        return False
    receiver = ast.unparse(func.value).lower()
    return "ipc" in receiver or "notifier" in receiver


def census() -> Census:
    found = Census()
    for root in ROOTS:
        for path in sorted((CORE / root).rglob("*.py")):
            relative = path.relative_to(CORE).as_posix()
            if relative.startswith("taktik/core/contract/"):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                where = f"{relative}:{getattr(node, 'lineno', 0)}"
                if isinstance(node, ast.Call):
                    for keyword in node.keywords:
                        if keyword.arg == "error_code":
                            found.resolve(keyword.value, tree, node, where)
                    name = node.func.id if isinstance(node.func, ast.Name) else None
                    if (name == "send_error" or _emitter_receiver(node.func)) and len(node.args) >= 2:
                        found.resolve(node.args[1], tree, node, where)
                elif isinstance(node, ast.Dict):
                    for key, value in zip(node.keys, node.values):
                        if key is not None and _string(key) == "error_code":
                            found.resolve(value, tree, node, where)
                elif isinstance(node, ast.ClassDef):
                    for statement in node.body:
                        if isinstance(statement, ast.Assign) and any(
                                isinstance(t, ast.Name) and t.id == "error_code" for t in statement.targets):
                            found.resolve(statement.value, tree, statement, where)
    return found


def test_every_code_the_bot_emits_is_in_the_catalogue_and_nothing_else():
    found = census()

    assert not found.unreadable, f"codes the census cannot read: {found.unreadable}"
    emitted = set(found.codes)
    missing = {code: sorted(found.codes[code]) for code in sorted(emitted - set(BRIDGE_ERROR_PHRASES))}
    assert not missing, f"codes emitted without an entry (and a sentence) in contract/error_codes.py: {missing}"
    dead = sorted(set(BRIDGE_ERROR_PHRASES) - emitted)
    assert not dead, f"codes of the catalogue nothing emits any more: {dead}"


def test_the_network_door_emits_its_code_from_the_core():
    """The motive of a phone without network is declared by the core's exception, which both hosts
    say: the census reads it there, not in a bridge."""
    found = census()

    assert any(where.startswith("taktik/core/shared/device/network_door.py")
               for where in found.codes["NETWORK_UNREACHABLE"])


def test_each_code_names_the_key_of_its_sentence():
    for code, key in BRIDGE_ERROR_PHRASES.items():
        assert key.startswith("error") and key[5:6].isupper() and key.isidentifier(), (code, key)


def test_one_cause_has_one_code():
    """Two codes for one cause make the app translate one and miss the other: a sentence shared by
    two codes is a synonym to rename, not a second entry."""
    codes_by_sentence: Dict[str, list] = {}
    for code, key in BRIDGE_ERROR_PHRASES.items():
        codes_by_sentence.setdefault(key, []).append(code)
    synonyms = {key: codes for key, codes in codes_by_sentence.items() if len(codes) > 1}
    assert not synonyms, f"one cause, several codes: {synonyms}"


def test_the_error_line_refers_to_the_catalogue():
    field = next(item for item in ERROR_EVENT.fields if item.key == "error_code")

    assert field.type is BRIDGE_ERROR_CODE
    assert BRIDGE_ERROR_CODE.values == tuple(BRIDGE_ERROR_PHRASES)


def _census_of(source: str) -> Tuple[Set[str], list]:
    """The census of one module's source, for the self-tests below."""
    found = Census()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "error_code":
                    found.resolve(keyword.value, tree, node, "self-test")
    return set(found.codes), found.unreadable


def test_the_census_follows_a_condition_and_a_local_variable():
    codes, unreadable = _census_of(
        'def report(message, reason):\n'
        '    code = "MISSING_CONFIG" if reason == "missing" else "CONFIG_ERROR"\n'
        '    ipc.send("error", error=message, error_code=code)\n'
    )

    assert codes == {"MISSING_CONFIG", "CONFIG_ERROR"} and unreadable == []


def test_the_census_refuses_a_code_it_cannot_read():
    codes, unreadable = _census_of('send_error("x", error_code=build_code())\n')

    assert codes == set() and unreadable == ["self-test: build_code()"]
