"""How a Lab action reads a yes/no parameter: one reading for every action.

The Lab page sends its switches as booleans, an operator typing params sends text ("true", "oui",
"0"). Five actions each read them their own way: some took any unknown text for yes, others for no.
"""

from typing import Any, Mapping

_YES = frozenset({"1", "true", "yes", "oui"})
_NO = frozenset({"0", "false", "no", "non"})


def lab_flag(params: Mapping[str, Any], name: str, default: bool) -> bool:
    """`params[name]` as a yes/no, `default` when it is absent or empty.

    A text that says neither yes nor no is refused (ValueError naming the parameter): the runner
    reports it, instead of the action running on a guess.
    """
    value = params.get(name)
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in _YES:
        return True
    if text in _NO:
        return False
    raise ValueError(f"Lab parameter '{name}' is neither yes nor no: {value!r}")
