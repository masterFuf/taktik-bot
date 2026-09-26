"""No handle of a real test account, and no serial of a real phone, in this public repository.

Tests use invented handles, and examples a placeholder serial (`emulator-5554`). What is guarded is
kept as SHA-256 digests so that this guard does not publish what it guards: every word of the
scanned files that could be a handle or a serial is hashed and looked up.
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

#: ADB serials of real phones, guarded everywhere, root files included.
_DEVICE_SERIALS = {
    "3c73122474d68fdd933015f5fd879a8321cb4335e7610194a5ada679332626cd",
    "9e0181b06a4b340ebcf3cf198ced38d8947546b7b3ed30cc9c56e79629bc68b6",
    "7c596951ddcfdb8fa1835c58164d5d2be0e63ef0e5b7f5f17bc93b79f45c9548",
    "75b39b8f68968e7d865b1c6c2eb4d89db89ddf0870fd7a087201842dbe0698f3",
    "99f2e8b062f450378c184982056121694bc75c5dee0486fb32602c242d95e3a0",
    "40fa4a45937a602209ae6c361c0292a8f760a9f12a2243ffc1d64a9721dd5aca",
    "2da4bf6d01c040dfe23dda2c934b9ae9f0c3e9b96e514ba0c32818b9360a9932",
    "9b09c0ce3107c5b02a6c625076958bac3f307422751be40cca2b5882917677e6",
}

_WORD = re.compile(r"[a-z0-9._]+")
# A serial sits inside names such as `config_<serial>.json`: split on anything but letters/digits.
_SERIAL_WORD = re.compile(r"[a-z0-9]+")
_TEXT_SUFFIXES = {".py", ".json", ".yaml", ".yml", ".md", ".txt", ".xml", ".toml", ".cfg", ".ini", ".spec"}
_SKIPPED_DIRS = {"__pycache__", ".pytest_cache", ".git", "build", "dist", "debug_ui"}


def _source_files(root: pathlib.Path):
    if root.is_file():
        yield root
        return
    for path in root.rglob("*"):
        skipped = _SKIPPED_DIRS.intersection(path.relative_to(root).parts)
        if path.suffix in _TEXT_SUFFIXES and not skipped and path.is_file():
            yield path


@functools.lru_cache(maxsize=None)
def _digest(word: str) -> str:
    return hashlib.sha256(word.strip(".").encode()).hexdigest()


def _hits(roots, digests, word=_WORD):
    hits = []
    for root in roots:
        for path in _source_files(root):
            words = set(word.findall(path.read_text(encoding="utf-8", errors="ignore").lower()))
            if any(_digest(word) in digests for word in words):
                hits.append(str(path.relative_to(_CORE)))
    return sorted(hits)


def test_no_guarded_handle_in_the_tests():
    assert _hits([_CORE / "tests"], _IN_TESTS) == []


def test_no_handle_guarded_everywhere_in_the_sources():
    roots = [_CORE / name for name in ("taktik", "bridges", "scripts")]
    assert _hits(roots, _EVERYWHERE) == []


def test_no_real_phone_serial_anywhere():
    roots = [_CORE / name for name in ("taktik", "bridges", "scripts", "tests", ".github")]
    roots += [path for path in _CORE.iterdir() if path.is_file() and path.suffix in _TEXT_SUFFIXES]
    assert _hits(roots, _DEVICE_SERIALS, word=_SERIAL_WORD) == []
