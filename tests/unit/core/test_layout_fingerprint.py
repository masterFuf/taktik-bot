"""The fingerprint has one job: same screen -> same digest, changed screen -> different digest.

Fixtures are inline and minimal on purpose. The real dumps of the parity survey live under
`taktik-desktop/data/`, which is working data and not versioned — a test that reads them would
pass on one machine and error on every other.
"""

from taktik.core.shared.diagnostics.layout_fingerprint import (
    FINGERPRINT_VERSION,
    layout_fingerprint,
    screen_density,
    screen_skeleton,
    skeleton_similarity,
)


def _screen(rows: str) -> str:
    return (
        '<hierarchy rotation="0">'
        '<node class="android.widget.FrameLayout" resource-id="">'
        f"{rows}"
        "</node>"
        "</hierarchy>"
    )


ROW = (
    '<node class="android.widget.TextView" resource-id="com.zhiliaoapp.musically:id/desc"'
    ' text="{text}" content-desc="{desc}" bounds="[0,{top}][1080,{bottom}]" clickable="true" />'
)


def _rows(count: int, text: str = "une video") -> str:
    return "".join(
        ROW.format(text=f"{text} {i}", desc=f"desc {i}", top=100 * i, bottom=100 * i + 90)
        for i in range(count)
    )


def test_same_structure_different_content_has_the_same_fingerprint():
    """The whole point: scrolling to another video must not read as a new layout."""
    a = _screen(_rows(3, "chat qui danse"))
    b = _screen(_rows(3, "recette de tarte"))
    assert a != b
    assert layout_fingerprint(a) == layout_fingerprint(b)


def test_bounds_do_not_change_the_fingerprint():
    """One extra row shifts every coordinate below it; that is content, not a layout change."""
    shifted = _screen(
        "".join(
            ROW.format(text="x", desc="d", top=7 + 100 * i, bottom=7 + 100 * i + 90)
            for i in range(3)
        )
    )
    assert layout_fingerprint(shifted) == layout_fingerprint(_screen(_rows(3)))


def test_a_new_resource_id_changes_the_fingerprint():
    """The case the tool exists for: they changed the screen under us."""
    before = _screen(_rows(2))
    after = _screen(
        _rows(2)
        + '<node class="android.widget.Button" resource-id="com.zhiliaoapp.musically:id/new_cta" />'
    )
    assert layout_fingerprint(before) != layout_fingerprint(after)


def test_a_renamed_obfuscated_id_changes_the_fingerprint():
    """An id renamed by a new build is exactly what a version bump does to TikTok."""
    before = _screen('<node class="android.widget.TextView" resource-id="pkg:id/qh5" />')
    after = _screen('<node class="android.widget.TextView" resource-id="pkg:id/xw2" />')
    assert layout_fingerprint(before) != layout_fingerprint(after)


def test_package_is_stripped_so_a_clone_matches_its_original():
    """Two clones of the same app are the same screen — the package is not part of the shape."""
    original = _screen('<node class="android.widget.TextView" resource-id="com.zhiliaoapp.musically:id/desc" />')
    clone = _screen('<node class="android.widget.TextView" resource-id="com.zhiliaoapp.musically.go:id/desc" />')
    assert layout_fingerprint(original) == layout_fingerprint(clone)


def test_depth_matters():
    """A flat multiset of ids cannot tell a moved row from a rewritten one."""
    flat = _screen(
        '<node class="android.widget.TextView" resource-id="p:id/a" />'
        '<node class="android.widget.TextView" resource-id="p:id/b" />'
    )
    nested = _screen(
        '<node class="android.widget.TextView" resource-id="p:id/a">'
        '<node class="android.widget.TextView" resource-id="p:id/b" />'
        "</node>"
    )
    assert layout_fingerprint(flat) != layout_fingerprint(nested)


def test_uiautomator_tag_renaming_matches_a_raw_aosp_dump():
    """u2 renames `<node class="X">` to `<X>`. A stored dump and a live one must agree."""
    aosp = '<hierarchy><node class="android.widget.TextView" resource-id="p:id/desc" /></hierarchy>'
    renamed = '<hierarchy><android.widget.TextView resource-id="p:id/desc" /></hierarchy>'
    assert layout_fingerprint(aosp) == layout_fingerprint(renamed)


def test_unparseable_dump_has_no_fingerprint():
    """None, not a sentinel: a broken capture has no shape, and must not be filed as a layout."""
    assert layout_fingerprint("<hierarchy><node ") is None
    assert layout_fingerprint("") is None


def test_fingerprint_carries_its_version():
    """Without it, a definition change reads as 'they changed the screen'."""
    assert layout_fingerprint(_screen(_rows(1))).startswith(f"v{FINGERPRINT_VERSION}:")


def test_density_counts_beside_the_hash():
    density = screen_density(_screen(_rows(3)))
    assert density["clickable"] == 3
    assert density["with_text"] == 3
    assert density["with_desc"] == 3
    assert density["parsed"] is True


def test_density_reports_an_unparseable_dump_rather_than_zeroes_that_look_real():
    density = screen_density("<hierarchy><node ")
    assert density["parsed"] is False
    assert density["nodes"] == 0


# --- the skeleton: identity, where the exact hash proved too strict on real screens ---

def test_transient_chrome_does_not_change_the_skeleton_much():
    """The case that broke the first design: a coach mark arrives, a banner leaves, same screen."""
    base = _screen(_rows(3) + '<node class="android.view.View" resource-id="p:id/nav" />')
    with_chrome = _screen(
        _rows(3)
        + '<node class="android.view.View" resource-id="p:id/nav" />'
        + '<node class="android.view.ViewGroup" resource-id="p:id/wb_guide" />'
    )
    assert layout_fingerprint(base) != layout_fingerprint(with_chrome)
    assert skeleton_similarity(screen_skeleton(base), screen_skeleton(with_chrome)) > 0.6


def test_a_different_screen_shares_almost_no_ids():
    feed = _screen('<node class="android.view.View" resource-id="p:id/desc" />'
                   '<node class="android.view.View" resource-id="p:id/cover" />')
    search = _screen('<node class="android.view.View" resource-id="p:id/query" />'
                     '<node class="android.view.View" resource-id="p:id/results" />')
    assert skeleton_similarity(screen_skeleton(feed), screen_skeleton(search)) == 0.0


def test_skeleton_lists_the_ids_rather_than_hashing_them():
    """Stored as a list on purpose: the DIFF is what an operator reads, not a digest."""
    skeleton = screen_skeleton(_screen('<node class="android.view.View" resource-id="pkg:id/b" />'
                                       '<node class="android.view.View" resource-id="pkg:id/a" />'))
    assert skeleton == ["a", "b"]


def test_skeleton_of_an_unparseable_dump_is_none_and_similarity_is_zero():
    assert screen_skeleton("<hierarchy><node ") is None
    assert skeleton_similarity(None, ["a"]) == 0.0
