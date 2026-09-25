"""No catalogue selector may be written for the raw dump tree.

`d.xpath()` evaluates a selector on uiautomator2's rewritten tree: the tag is the widget class and
the `class` attribute is gone. `@class` or a `node[` step therefore never matches there, silently,
and every lxml reader now sees the same tree through `parse_ui_dump`. Filtering on the class is
written as a tag step (`//android.widget.TextView[...]`) or, for a partial class, `name()`.
"""

import io
import pathlib
import re
import tokenize

SELECTORS = pathlib.Path(__file__).resolve().parents[3] / "taktik" / "core" / "social_media"
RAW_TREE_IDIOM = re.compile(r"@class\b|(?:^|[/(\[:])node\[")


def _string_literals(path):
    source = path.read_text(encoding="utf-8")
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.STRING:
            yield token.start[0], token.string


def test_no_selector_uses_the_raw_tree_idiom():
    files = sorted(SELECTORS.glob("*/ui/selectors/**/*.py"))
    assert files, "selector catalogues not found"
    offenders = [
        f"{path.relative_to(SELECTORS)}:{line}: {literal}"
        for path in files
        for line, literal in _string_literals(path)
        if RAW_TREE_IDIOM.search(literal)
    ]
    assert offenders == []


def test_the_pattern_catches_both_raw_tree_forms():
    assert RAW_TREE_IDIOM.search('//*[@class="android.widget.TextView"]')
    assert RAW_TREE_IDIOM.search('//node[@resource-id="x"]')
    assert not RAW_TREE_IDIOM.search('//android.widget.TextView[starts-with(@text, "#")]')
    assert not RAW_TREE_IDIOM.search('//*[contains(name(), "ImageView")]')
