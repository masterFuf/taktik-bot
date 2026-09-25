"""No handle of a real test account in this public repository's sources.

Tests use invented handles. The guarded handles are kept as SHA-256 digests so that this guard
does not publish what it guards: every word of the scanned files that could be a handle is
hashed and looked up.
"""

import functools
import hashlib
import pathlib
import re

_CORE = pathlib.Path(__file__).resolve().parents[2]

#: Guarded in every source file of the repository.
_EVERYWHERE = {
    "bc079ff1d680112a4f65c1f1f2b6c18d00562c3e8a45c738714f08d65360bd21",
}

#: Guarded in the tests. Some still appear in code comments.
_IN_TESTS = _EVERYWHERE | {
    "26458a92477569154651e49b1fa8e01e598af21b074dc24ae4540e90c95f2435",
    "beaf8655df6ee40582cc0791ebc3658c23a6bd6858de3565d3cdf3829b4b3df7",
    "4d106fc32f8a46ab31b4fa4772139e72d77df04faf5475a4c264ee42a1457c2c",
    "d31da507cdcac043dffbea52dbd30ba225a427af11fe4ab176ae9939d6fda0c4",
    "1a56e07509932f44a1c8d3776cdaafa8e4ed52488b40f3981a8d583e4f4ef866",
    "4f557362e3f600b0f2e1d806ca465d323dedbf21a248d83849d9706c16b13573",
    "e930aca6a63a5aa84704f3659f17f1ef762a4ea4dcd6fe3fe729f025e7d1e993",
    "22084738e59544c58e2bd3f6587902bddd9331a4b9d156dc679a3556093a04b5",
    "fc27456739ef870b18c5d1e7e3993190db3297cf35d8054ad3dfb7b0feb8af48",
}

_WORD = re.compile(r"[a-z0-9._]+")
_TEXT_SUFFIXES = {".py", ".json", ".yaml", ".yml", ".md", ".txt", ".xml", ".toml", ".cfg", ".ini", ".spec"}
_SKIPPED_DIRS = {"__pycache__", ".pytest_cache", ".git", "build", "dist", "debug_ui"}


def _source_files(root: pathlib.Path):
    for path in root.rglob("*"):
        skipped = _SKIPPED_DIRS.intersection(path.relative_to(root).parts)
        if path.suffix in _TEXT_SUFFIXES and not skipped and path.is_file():
            yield path


@functools.lru_cache(maxsize=None)
def _digest(word: str) -> str:
    return hashlib.sha256(word.strip(".").encode()).hexdigest()


def _hits(roots, digests):
    hits = []
    for root in roots:
        for path in _source_files(root):
            words = set(_WORD.findall(path.read_text(encoding="utf-8", errors="ignore").lower()))
            if any(_digest(word) in digests for word in words):
                hits.append(str(path.relative_to(_CORE)))
    return sorted(hits)


def test_no_guarded_handle_in_the_tests():
    assert _hits([_CORE / "tests"], _IN_TESTS) == []


def test_no_handle_guarded_everywhere_in_the_sources():
    roots = [_CORE / name for name in ("taktik", "bridges", "scripts")]
    assert _hits(roots, _EVERYWHERE) == []
