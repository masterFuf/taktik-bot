"""A selector must mean the same thing under `d.xpath()` and under plain lxml.

This is the bug that cost the Instagram bio for two weeks. The device returns AOSP XML, where a
widget's type is an ATTRIBUTE of a `<node>` element. `uiautomator2` rewrites that tree before any
selector sees it — tag becomes the class, `class` is dropped — so all our class-based selectors are
written in the rewritten idiom. Code reading `get_xml_dump()` with plain lxml saw the raw tree, and
matched nothing, silently.

The fixture mirrors a real 2026-09-09 dump (the profile bio sits in an unnamed TextView inside
`profile_user_info_compose_view`) but carries invented content: a real dump is personal data.
"""

from taktik.core.shared.device.ui_dump import parse_ui_dump

# Same shape as the device's own output: every element is <node>, the widget type is an attribute.
RAW_DUMP = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout">
    <node index="1" text="someone" resource-id="com.instagram.android:id/action_bar_title"
          class="android.widget.TextView" />
    <node index="4" text="" resource-id="com.instagram.android:id/profile_user_info_compose_view"
          class="com.facebook.compose.view.MetaComposeView">
      <node index="0" text="Two lines of bio, written by nobody" resource-id=""
            class="android.widget.TextView" />
    </node>
  </node>
</hierarchy>"""

BIO_SELECTOR = (
    '//*[@resource-id="com.instagram.android:id/profile_user_info_compose_view"]'
    '//android.widget.TextView'
)


def test_the_production_selector_finds_the_bio_once_the_tree_is_normalised():
    """Unchanged selector, normalised tree: this is the whole fix."""
    root = parse_ui_dump(RAW_DUMP)
    assert root is not None

    hits = root.xpath(BIO_SELECTOR)
    assert len(hits) == 1
    assert hits[0].get("text") == "Two lines of bio, written by nobody"


def test_the_same_selector_finds_nothing_on_the_raw_tree():
    """The failure mode, pinned.

    Without this, a later "simplification" back to `etree.fromstring` reads as harmless: no test
    goes red, no run breaks, and the only symptom is a column that quietly stops being filled.
    """
    from lxml import etree

    raw = etree.fromstring(RAW_DUMP.encode("utf-8"))
    assert raw.xpath(BIO_SELECTOR) == []


def test_class_is_dropped_so_a_selector_cannot_rely_on_it():
    """Mirroring uiautomator2 exactly.

    Keeping `class` would let `@class` work here and fail under `d.xpath()` — reintroducing the
    very asymmetry this parser removes.
    """
    root = parse_ui_dump(RAW_DUMP)
    assert root.xpath('//*[@class="android.widget.TextView"]') == []


def test_resource_id_selectors_are_untouched():
    """They are why the loss stayed invisible: the name and the counters kept working."""
    root = parse_ui_dump(RAW_DUMP)
    hits = root.xpath('//*[@resource-id="com.instagram.android:id/action_bar_title"]')
    assert len(hits) == 1 and hits[0].get("text") == "someone"


def test_unusable_input_is_none_rather_than_a_raise():
    """A dump is best effort: an empty or malformed one must not end a run."""
    assert parse_ui_dump(None) is None
    assert parse_ui_dump("") is None
    assert parse_ui_dump("<not xml") is None



def test_a_class_with_a_dollar_or_an_ampersand_gets_uiautomator2s_own_tag():
    """A copy of the rule turned `$` into `_` (uiautomator2 writes `.`), and a class with `&`
    made this parser fail where uiautomator2 passes. The rule is now uiautomator2's function."""
    from uiautomator2.xpath import PageSource

    from taktik.core.shared.device.ui_dump import parse_ui_dump

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
        '<node class="com.example.Row$Inner" text="a" bounds="[0,0][1,1]"/>'
        '<node class="com.example.A&amp;B" text="b" bounds="[0,0][1,1]"/>'
        '</hierarchy>'
    )
    ours = [node.tag for node in parse_ui_dump(xml)]
    theirs = [node.tag for node in PageSource(xml).root]
    assert ours == theirs == ["com.example.Row.Inner", "com.example.A.B"]


def test_bytes_parse_like_text():
    """Some callers get bytes from the dump: they must see the same tree."""
    from_text = parse_ui_dump(RAW_DUMP)
    from_bytes = parse_ui_dump(RAW_DUMP.encode("utf-8"))
    assert [n.tag for n in from_bytes.iter()] == [n.tag for n in from_text.iter()]


def test_iter_widgets_visits_the_nodes_iter_node_visited_on_the_raw_tree():
    """The readers' `iter("node")` became `iter_widgets`: same widgets, same order, root excluded."""
    from lxml import etree

    from taktik.core.shared.device.ui_dump import iter_widgets

    raw = etree.fromstring(RAW_DUMP.encode("utf-8"))
    root = parse_ui_dump(RAW_DUMP)

    def signature(node):
        return (node.get("index"), node.get("text"), node.get("resource-id"))

    assert [signature(n) for n in iter_widgets(root)] == [signature(n) for n in raw.iter("node")]
    assert all(n.tag != "hierarchy" for n in iter_widgets(root))

    compose = root.xpath('//*[contains(@resource-id, "profile_user_info_compose_view")]')[0]
    raw_compose = raw.xpath('//*[contains(@resource-id, "profile_user_info_compose_view")]')[0]
    assert [signature(n) for n in iter_widgets(compose)] == [
        signature(n) for n in raw_compose.iter("node")
    ]
