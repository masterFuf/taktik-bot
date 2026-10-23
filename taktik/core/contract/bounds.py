"""What a reader refuses before the phone is touched: a setting outside its declared bounds.

The bounds are declared once, on the settings of a declaration (`Field.bounds`, `schema.py`). Each
reader of a declared workflow calls `refuse_out_of_bounds` first, with its declaration and the error
it refuses with; `scripts/audits/workflow_contract.py` renders the same bounds for the app.

Only the keys that carry bounds are read, each under the settings its reader reads it for (the
field's `when`, then the bounds' own): the contract tests, which watch every key a reader reads,
still see the reader's reads and nothing else. A value that does not read as a number is not
judged here: its type is its reader's to refuse or coerce.
"""

from __future__ import annotations

from typing import Any, List, Mapping, Optional, Tuple, Type

from .schema import Bounds, Field, ListOf, Shape, WorkflowContract, has_default


def _amount(value: float) -> str:
    """A bound or a value as a person reads it: 500, not 500.0."""
    return str(int(value)) if float(value).is_integer() else repr(float(value))


def _number_words(bounds: Bounds) -> str:
    low, high = bounds.minimum, bounds.maximum
    if low is not None and high is not None:
        words = f"{_amount(low)} to {_amount(high)}"
    elif low is not None:
        words = f"at least {_amount(low)}"
    elif high is not None:
        words = f"at most {_amount(high)}"
    else:
        words = ""
    if words and bounds.unbounded_at is not None:
        words += f", or {_amount(bounds.unbounded_at)} for no limit"
    return words


def _items_words(bounds: Bounds) -> str:
    low, high = bounds.min_items, bounds.max_items
    if low is not None and high is not None:
        return f"{low} to {high} items"
    if low is not None:
        return f"at least {low} items"
    if high is not None:
        return f"at most {high} items"
    return ""


def _length_words(bounds: Bounds) -> str:
    return f"at most {bounds.max_length} characters" if bounds.max_length is not None else ""


def describe(bounds: Bounds) -> str:
    """The bounds in words: "1 to 500", "at least 1", "1 to 50, or 0 for no limit", "at most 3 items"."""
    parts = [words for words in (_number_words(bounds), _items_words(bounds), _length_words(bounds)) if words]
    return ", ".join(parts)


def _as_number(value: Any) -> Optional[float]:
    """`value` as a number, or None when it is not one (a bool, a text that reads as no number)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            # Not a number: the reader refuses or coerces it, the bounds have nothing to say.
            return None
    return None


def _read(node: Mapping[str, Any], item: Field) -> Tuple[bool, Any]:
    """The value the reader takes for `item`: under its first name present, in its order of preference."""
    for name in item.names:
        if name in node:
            return True, node[name]
    return False, None


def _declared(fields: Tuple[Field, ...], key: str) -> Field:
    for item in fields:
        if item.key == key:
            return item
    raise KeyError(f"`{key}` is not a declared setting")


def _setting_value(fields: Tuple[Field, ...], node: Mapping[str, Any], parts: Tuple[str, ...]) -> Any:
    """What the reader sees at a dotted setting path: the value sent, else the declared default."""
    item = _declared(fields, parts[0])
    present, value = _read(node, item)
    if len(parts) == 1:
        if present:
            return value
        return item.default if has_default(item) else None
    if item.type == "json":
        # An opaque object (the AI block the notifications scan reads): what is inside it is its reader's
        # business, the path is read as it was sent, with no declared default.
        inside: Any = value if present else None
        for part in parts[1:]:
            inside = inside.get(part) if isinstance(inside, Mapping) else None
        return inside
    if not isinstance(item.type, Shape):
        raise KeyError(f"`{item.key}` holds no setting `{'.'.join(parts[1:])}`")
    inner = value if present and isinstance(value, Mapping) else {}
    return _setting_value(item.type.fields, inner, parts[1:])


def holds(settings: Tuple[Field, ...], payload: Mapping[str, Any], when: Mapping[str, Any]) -> bool:
    """`payload` is under the settings `when` names (a tuple: any of its values), the value sent or else
    the declared default; a setting the declaration does not have is a `KeyError`, never a silent false."""
    for dotted, wanted in when.items():
        value = _setting_value(settings, payload, tuple(dotted.split(".")))
        if not (value in wanted if isinstance(wanted, tuple) else value == wanted):
            return False
    return True


def _bounded(item: Field) -> bool:
    """The field, or a setting under it, carries bounds."""
    if item.bounds is not None:
        return True
    spec = item.type
    if isinstance(spec, ListOf):
        spec = spec.item
    return isinstance(spec, Shape) and any(_bounded(sub) for sub in spec.fields)


def _violations(path: str, item: Field, value: Any) -> List[str]:
    bounds = item.bounds
    out: List[str] = []
    if bounds is None:
        return out
    if isinstance(item.type, ListOf):
        if isinstance(value, list):
            count = len(value)
            if ((bounds.min_items is not None and count < bounds.min_items)
                    or (bounds.max_items is not None and count > bounds.max_items)):
                out.append(f"{path} has {count} items, outside its bounds ({_items_words(bounds)})")
            if bounds.max_length is not None:
                for index, element in enumerate(value):
                    if isinstance(element, str) and len(element) > bounds.max_length:
                        out.append(f"{path}[{index}] has {len(element)} characters, "
                                   f"outside its bounds ({_length_words(bounds)})")
        return out
    if item.type == "string":
        if isinstance(value, str) and bounds.max_length is not None and len(value) > bounds.max_length:
            out.append(f"{path} has {len(value)} characters, outside its bounds ({_length_words(bounds)})")
        return out
    number = _as_number(value)
    if number is not None and not number_within(bounds, number):
        out.append(f"{path} = {_amount(number)}, outside its bounds ({_number_words(bounds)})")
    return out


def number_within(bounds: Bounds, number: float) -> bool:
    """`number` lies inside the bounds, or is the one that says no limit."""
    if bounds.unbounded_at is not None and number == bounds.unbounded_at:
        return True
    # Written as "not inside" so that a NaN, which compares false to everything, is refused too.
    below = bounds.minimum is not None and not number >= bounds.minimum
    above = bounds.maximum is not None and not number <= bounds.maximum
    return not (below or above)


def _walk(fields: Tuple[Field, ...], node: Mapping[str, Any], prefix: str, inherited: Mapping[str, Any],
          settings: Tuple[Field, ...], payload: Mapping[str, Any], problems: List[str]) -> None:
    for item in fields:
        if not _bounded(item):
            continue
        when = {**inherited, **item.when}
        # The reader reads the key only under its condition: neither does this.
        if not holds(settings, payload, when):
            continue
        present, value = _read(node, item)
        if not present or value is None:
            continue
        path = f"{prefix}{item.key}"
        if item.bounds is not None and holds(settings, payload, item.bounds.when):
            problems.extend(_violations(path, item, value))
        if isinstance(item.type, Shape) and isinstance(value, Mapping):
            _walk(item.type.fields, value, f"{path}.", when, settings, payload, problems)
        elif isinstance(item.type, ListOf) and isinstance(item.type.item, Shape) and isinstance(value, list):
            for index, element in enumerate(value):
                if isinstance(element, Mapping):
                    _walk(item.type.item.fields, element, f"{path}[{index}].", when, settings, payload, problems)


def out_of_bounds(contract: WorkflowContract, payload: Mapping[str, Any]) -> List[str]:
    """Each setting of `payload` outside its declared bounds, in words, in the declaration's order."""
    problems: List[str] = []
    _walk(contract.settings, payload, "", {}, contract.settings, payload, problems)
    return problems


def refuse_out_of_bounds(contract: WorkflowContract, payload: Mapping[str, Any],
                         error: Type[Exception] = ValueError) -> None:
    """Raise `error` (the reader's refusal) naming every setting of `payload` outside its bounds."""
    problems = out_of_bounds(contract, payload)
    if problems:
        raise error("Refused before the phone is touched: " + "; ".join(problems))


__all__ = ["describe", "holds", "number_within", "out_of_bounds", "refuse_out_of_bounds"]
