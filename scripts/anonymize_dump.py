"""Turn a real uiautomator dump into a test fixture: same screen, nobody's data.

A screen test reads a real capture (anti-drift doctrine, "Tester ce qui touche l'ecran"), and this
repository is public. What a dump shows of other people goes; what the app itself writes stays:

- the tree is untouched: nodes, nesting, classes, resource-ids, bounds, every flag;
- in `text`, `content-desc` and `hint`, a word is kept when the app's own strings (selector
  catalogues, locales, version overrides) hold it next to one of its neighbours, or hold it as a
  label on its own: "Suivre en retour" or "Attribuer un « J'aime » à la vidéo. 12" survive, a
  message made of common words does not;
- the words of the screens are learned too: what a fixture already in the repository keeps (it was
  read value by value before it entered) is an app word, beside its neighbours or alone ("Trié par
  Par défaut", "Appuyez deux fois pour lire ou mettre en pause"); its placeholders are not;
- any other word is replaced, the same word by the same value across the dump: a handle-like
  word (`@`, `_`, `.` or a digit inside) becomes `user_1`, `user_2`..., any other word `name_1`,
  `name_2`...; a word made of letters and a long digit run ("marie123456") is a handle, replaced
  whole; a possessive keeps its mark (`user_1's story`);
- clock times become `12:00`, numeric dates `01/01/2000`, phone numbers and digit runs of six or
  more become zeros; short counts stay, the parsers read them, and so does a count glued to an app
  label ("295followers"); a resource reference (`@2131974114`, an `@` and digits only) stays.

The result is printed, value by value: read it before the fixture enters the repository. A word
the vocabulary happens to hold (a first name that is also a label) is kept, and only a reader
sees it; `--drop WORD` replaces it anyway.

Several captures of one scene (the screen before and after a gesture) go in one call: a word gets
the same placeholder in all of them, so a name seen before and after the gesture still reads the
same in both, which is what a test that pairs the two screens compares.

    python scripts/anonymize_dump.py IN.xml OUT.xml [IN2.xml OUT2.xml ...] [--drop WORD ...] [--quiet]
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from functools import lru_cache
from pathlib import Path

from lxml import etree

CORE = Path(__file__).resolve().parents[1]
VOCABULARY_ROOTS = (
    "taktik/core/social_media/instagram/ui",
    "taktik/core/social_media/tiktok/ui",
    "taktik/core/shared/ui",
    "taktik/core/compat/data/overrides",
)
#: Where the reviewed screens live: every `fixtures/*.xml` under it.
FIXTURES_ROOT = "tests"
READ_ATTRIBUTES = ("text", "content-desc", "hint")

WORD = re.compile(r"@?\w(?:[\w.'’-]*\w)?")
TIME = re.compile(r"\b\d{1,2}[:h]\d{2}\b")
DATE = re.compile(r"\b\d{1,4}[/.-]\d{1,2}[/.-]\d{2,4}\b")
COUNT = re.compile(r"\d{1,5}(?:[.,]\d{1,3})?[kKmM]?")
LONG_DIGITS = re.compile(r"\d{6,}")
#: A phone number; never the digits of a resource reference (`@2131974114`).
PHONE = re.compile(r"(?<![@\d])\+?\d(?:[ .-]?\d){7,}")
#: What this tool writes in place of a word: never an app word to learn.
PLACEHOLDER = re.compile(r"(?:user|name)_\d+")
#: A possessive: the word, then its mark ("karine's", "karine’s").
POSSESSIVE = re.compile(r"(.+?)(['’]s)")
#: A reference to an Android resource, as TikTok writes some descriptions: not a number of anyone.
RESOURCE_REFERENCE = re.compile(r"@\d+")
#: A count glued to its label, as a counter is sometimes read ("295followers").
GLUED_COUNT = re.compile(r"\d{1,5}(?:[.,]\d{1,3})?[kKmM]?([^\W\d_]+)")


def _strings(path: Path):
    source = path.read_text(encoding="utf-8-sig", errors="ignore")
    if path.suffix != ".py":
        yield source
        return
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value
        elif isinstance(node, ast.JoinedStr):
            yield " ".join(v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str))


QUOTED = re.compile(r"\"([^\"]*)\"|'([^']*)'")


def _words(value: str) -> list[str]:
    return [w.lstrip("@").casefold() for w in WORD.findall(value)]


def _possessive(word: str) -> tuple[str, str]:
    """The word and its possessive mark, or the word and nothing."""
    match = POSSESSIVE.fullmatch(word)
    return (match.group(1), match.group(2)) if match else (word, "")


def _fixture_values():
    """The text of every reviewed screen: the attribute values of the repository's fixtures."""
    for path in sorted((CORE / FIXTURES_ROOT).rglob("*.xml")):
        if "fixtures" not in path.parts:
            continue
        try:
            root = etree.parse(str(path)).getroot()
        except etree.XMLSyntaxError as exc:
            print(f"anonymize_dump: {path} does not parse, its words are not learned: {exc}", file=sys.stderr)
            continue
        for node in root.iter():
            for attribute in READ_ATTRIBUTES:
                value = node.get(attribute)
                if value:
                    yield value


def _learn(part: str, labels: set, pairs: set) -> None:
    """The words of one app string: a label alone, pairs of neighbours, never across a placeholder."""
    words = [w for w in _words(part) if not COUNT.fullmatch(w)]
    runs, run = [], []
    for word in words:
        if PLACEHOLDER.fullmatch(_possessive(word)[0]):
            runs.append(run)
            run = []
        else:
            run.append(word)
    runs.append(run)
    if len(words) == 1 and words == run and len(part.strip()) <= 40:
        labels.add(words[0])
    for run in runs:
        pairs.update(zip(run, run[1:]))


@lru_cache(maxsize=1)
def vocabulary() -> tuple[frozenset[str], frozenset[tuple[str, str]]]:
    """The app's labels: the words it writes alone, and the pairs of words it writes side by side,
    in its own strings and on the screens already reviewed."""
    labels, pairs = set(), set()
    for root in VOCABULARY_ROOTS:
        for path in (CORE / root).rglob("*"):
            if path.suffix not in (".py", ".yaml", ".yml", ".json") or "__pycache__" in path.parts:
                continue
            for value in _strings(path):
                for part in [value] + [a or b for a, b in QUOTED.findall(value)]:
                    _learn(part, labels, pairs)
    for value in _fixture_values():
        _learn(value, labels, pairs)
    return frozenset(labels), frozenset(pairs)


def _handle_like(word: str) -> bool:
    return word.startswith("@") or any(c in word for c in "_.") or (
        any(c.isdigit() for c in word) and any(c.isalpha() for c in word))


class Anonymizer:
    def __init__(self, drop: tuple[str, ...] = ()):
        labels, pairs = vocabulary()
        dropped = {w.casefold() for w in drop}
        self.labels = labels - dropped
        self.pairs = {pair for pair in pairs if not dropped.intersection(pair)}
        self.replacements: dict[str, str] = {}
        self.counters = {"user": 0, "name": 0}

    def _replacement(self, word: str) -> str:
        key = word.lstrip("@").casefold()
        if key not in self.replacements:
            kind = "user" if _handle_like(word) else "name"
            self.counters[kind] += 1
            self.replacements[key] = f"{kind}_{self.counters[kind]}"
        return ("@" if word.startswith("@") else "") + self.replacements[key]

    def _kept(self, words: list[str]) -> set[int]:
        """Positions of the words the app writes: a label alone, or a word beside its neighbour."""
        kept = set()
        for i, word in enumerate(words):
            if word in self.labels:
                kept.add(i)
            if i and (words[i - 1], word) in self.pairs:
                kept.update((i - 1, i))
        return kept

    def value(self, text: str) -> str:
        text = TIME.sub("12:00", text)
        text = DATE.sub("01/01/2000", text)
        text = PHONE.sub(lambda m: re.sub(r"\d", "0", m.group(0)), text)
        matches = list(WORD.finditer(text))
        words = [m.group(0) for m in matches if not COUNT.fullmatch(m.group(0))]
        kept = self._kept([w.lstrip("@").casefold() for w in words])
        out, last, index = [], 0, 0
        for match in matches:
            word = match.group(0)
            out.append(text[last:match.start()])
            last = match.end()
            glued = GLUED_COUNT.fullmatch(word)
            stem, mark = _possessive(word)
            if RESOURCE_REFERENCE.fullmatch(word) or COUNT.fullmatch(word):
                out.append(word)
            elif LONG_DIGITS.search(word) and not any(c.isalpha() for c in word):
                out.append(LONG_DIGITS.sub(lambda m: "0" * len(m.group(0)), word))
            elif glued and glued.group(1).casefold() in self.labels:
                out.append(word)
            elif index in kept:
                out.append(word)
            else:
                out.append(self._replacement(stem) + mark)
            if not COUNT.fullmatch(word):
                index += 1
        out.append(text[last:])
        return "".join(out)

    def tree(self, root) -> None:
        for node in root.iter():
            for attribute in READ_ATTRIBUTES:
                value = node.get(attribute)
                if value:
                    node.set(attribute, self.value(value))


def anonymize(xml: bytes | str, drop: tuple[str, ...] = ()) -> bytes:
    return anonymize_series([xml], drop)[0]


def anonymize_series(xmls: list[bytes | str], drop: tuple[str, ...] = ()) -> list[bytes]:
    """Captures of one scene, one placeholder per word across all of them."""
    anonymizer = Anonymizer(drop)
    out = []
    for xml in xmls:
        raw = xml.encode("utf-8") if isinstance(xml, str) else xml
        raw = re.sub(rb"\r+\n", b"\n", raw)  # a dump saved on Windows ends its lines with \r\r\n
        root = etree.fromstring(raw, etree.XMLParser(remove_blank_text=False))
        anonymizer.tree(root)
        out.append(etree.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True))
    return out


def read_values(xml: bytes) -> list[str]:
    root = etree.fromstring(xml)
    return sorted({node.get(a) for node in root.iter() for a in READ_ATTRIBUTES if node.get(a)})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="+", metavar="SOURCE TARGET",
                        help="one or more pairs: a capture, then the fixture it becomes")
    parser.add_argument("--drop", action="append", default=[], help="a kept word to replace anyway")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    if len(args.paths) % 2:
        parser.error("give the paths in pairs: SOURCE TARGET [SOURCE TARGET ...]")
    sources, targets = args.paths[0::2], args.paths[1::2]
    outs = anonymize_series([Path(source).read_bytes() for source in sources], tuple(args.drop))
    for target, out in zip(targets, outs):
        Path(target).write_bytes(out)
        if not args.quiet:
            print(f"Values left in {target} (read them all):")
            for value in read_values(out):
                print(f"  {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
