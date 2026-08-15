"""Selectors supporting raw TEXT reading — words that are not what we are looking for.

Reading a handle off a row means reading whatever TextView the extractor landed on, and
that node is sometimes the action label next to the handle rather than the handle itself.
"Suivre" and "Like" are perfectly valid Instagram usernames in shape, so only the word
itself can tell them apart — which makes this a language-dependent catalogue, not a
neutral selector.
"""
from typing import List
from dataclasses import dataclass

from ..locales import L


@dataclass
class TextReadingSelectors:
    """Bare labels a text extractor must never mistake for content."""

    # Purely localized: there is no resource-id to fall back on, the whole point is the
    # word. With an unknown active locale, `L` returns the union of every language, so an
    # undetected language degrades to "reject the labels of all languages" — never to
    # "accept a label as a username".
    @property
    def not_a_username(self) -> List[str]:
        return L("text.not_a_username")


TEXT_READING_SELECTORS = TextReadingSelectors()
