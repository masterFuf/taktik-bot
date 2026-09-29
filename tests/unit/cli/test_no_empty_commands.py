"""No CLI command that only prints: a command either runs something or does not exist.

`taktik setup`, `taktik proxy`, `taktik account` and `taktik run` were listed by `taktik --help`
and did nothing but print that they would come later. A user reading the help had no way to tell
them from the commands that work. A command whose body is only output calls (a docstring aside)
is that placeholder, whatever language it prints in.
"""

from __future__ import annotations

import ast

from click.testing import CliRunner
from unit.paths import CORE

CLI_ROOT = CORE / "taktik/cli"
OUTPUT_CALLS = {"print", "echo", "secho"}


def _is_command(function: ast.FunctionDef) -> bool:
    for decorator in function.decorator_list:
        call = decorator if isinstance(decorator, ast.Call) else None
        target = call.func if call else decorator
        if isinstance(target, ast.Attribute) and target.attr == "command":
            return True
    return False


def _only_prints(function: ast.FunctionDef) -> bool:
    body = list(function.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]  # the docstring
    if not body:
        return False
    for statement in body:
        if not (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call)):
            return False
        func = statement.value.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name not in OUTPUT_CALLS:
            return False
    return True


def test_no_command_only_prints():
    placeholders = []
    for path in sorted(CLI_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and _is_command(node) and _only_prints(node):
                placeholders.append(f"{path.relative_to(CLI_ROOT)}:{node.lineno} {node.name}")
    assert not placeholders, f"commands that only print a message: {placeholders}"


def test_the_help_lists_no_placeholder_command():
    from taktik.cli.main import cli

    result = CliRunner().invoke(cli, ["--lang", "en", "--help"])

    assert result.exit_code == 0, result.output
    listed = {line.split()[0] for line in result.output.split("Commands:", 1)[1].splitlines() if line.strip()}
    assert not listed & {"setup", "proxy", "account", "run"}, sorted(listed)
