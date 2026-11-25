"""The terms an account keeps away from, on data alone (the « termes exclus » of its frame).

The operator sets two lists in the account's frame, and the app sends them with the run
(`excludedTerms`, declared in `taktik/core/contract/shared.py`):

- the profile terms: a term in a profile's handle, its name or its bio, and the profile gets no gesture
  (no like, follow, comment, story nor DM);
- the post terms: a term in a post's caption, and the post gets neither like nor comment; its author
  stays a target.

A handle glues its words, so a term is looked for anywhere in it (`term_in_handle`); in a name, a bio or
a caption a term catches the words it starts (`term_starting_a_word`, the comparison of the DM rule).
No device, no platform: a platform maps what it read onto the vocabulary of the profile filter
(`username`, `full_name`, `biography`) and says where a term was found by that key.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from taktik.core.shared.text import term_in_handle, term_starting_a_word

#: The profile's handle, searched anywhere.
HANDLE_FIELD = "username"
#: The profile's texts, searched at the start of their words, in this order.
TEXT_FIELDS = ("full_name", "biography")


@dataclass(frozen=True)
class ExcludedTerms:
    """The two lists of one run: none set, nothing is excluded and nothing is read for them."""

    profile_terms: Tuple[str, ...] = ()
    post_terms: Tuple[str, ...] = ()

    def as_config(self) -> Dict[str, List[str]]:
        """The lists as the built config of a run keeps them (`excluded_terms`), plain JSON."""
        return {"profile_terms": list(self.profile_terms), "post_terms": list(self.post_terms)}

    @classmethod
    def from_config(cls, block: Optional[Mapping[str, Any]]) -> "ExcludedTerms":
        """The lists of a built config (`as_config`); absent: none."""
        if not block:
            return cls()
        return cls(
            profile_terms=tuple(block.get("profile_terms") or ()),
            post_terms=tuple(block.get("post_terms") or ()),
        )


def _terms(block: Mapping[str, Any], key: str) -> Tuple[str, ...]:
    value = block.get(key)
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)) or not all(isinstance(term, str) for term in value):
        raise ValueError(f"excludedTerms.{key}: a list of texts is expected")
    return tuple(term.strip() for term in value if term.strip())


def excluded_terms_from_payload(block: Any) -> ExcludedTerms:
    """The lists an `excludedTerms` block sends; absent: none. A block that is not an object of two
    lists of texts refuses the run: running without the terms the operator set is not a safe answer."""
    if block is None:
        return ExcludedTerms()
    if not isinstance(block, Mapping):
        raise ValueError(f"excludedTerms: an object is expected, got {type(block).__name__}")
    return ExcludedTerms(profile_terms=_terms(block, "profileTerms"), post_terms=_terms(block, "postTerms"))


def profile_term_found(profile: Mapping[str, Any], terms: Sequence[str]) -> Optional[Tuple[str, str]]:
    """The first term found in `profile`, as declared, and the key it was found in (`username`,
    `full_name`, `biography`); None when none is. The handle first, then the name, then the bio. A text
    that was not read is not searched: the profile is judged on what was read."""
    if not terms:
        return None
    term = term_in_handle(profile.get(HANDLE_FIELD), terms)
    if term is not None:
        return term, HANDLE_FIELD
    for key in TEXT_FIELDS:
        term = term_starting_a_word(profile.get(key), terms)
        if term is not None:
            return term, key
    return None


__all__ = [
    "HANDLE_FIELD",
    "TEXT_FIELDS",
    "ExcludedTerms",
    "excluded_terms_from_payload",
    "profile_term_found",
]
