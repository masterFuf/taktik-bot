"""Switching a comments thread's sort order, on a phone that is not in English.

The control used to be the single English content-desc "For you". On a French phone it matched
nothing, so the menu was never opened -- and the caller went on believing it had switched the
sort while the thread stayed on its default. The menu's own options were looked up by a
hardcoded English map, which failed the same way one step later.

Fixtures follow a real 442 capture: the control's label lives in the TEXT of a child View with
no content-desc, and a menu option carries it on content-desc AND on a child TextView.
"""

from lxml import etree

from taktik.core.social_media.instagram.ui.selectors.surfaces.post.comments import (
    POST_COMMENTS_SELECTORS,
)

LIST_ID = "com.instagram.android:id/sticky_header_list"

COMMENTS_SHEET = f"""
<hierarchy>
  <node class="android.view.ViewGroup" bounds="[0,100][1080,300]" text="Pour vous" content-desc="Pour vous"/>
  <node class="androidx.recyclerview.widget.RecyclerView" resource-id="{LIST_ID}" bounds="[0,934][1080,2104]">
    <node class="android.widget.Button" bounds="[32,935][304,1037]">
      <node class="android.view.View" bounds="[64,967][218,1005]" text="Pour vous" content-desc=""/>
    </node>
  </node>
</hierarchy>
"""

SORT_MENU = """
<hierarchy>
  <node class="android.widget.Button" resource-id="com.instagram.android:id/context_menu_item"
        bounds="[32,1048][539,1165]" content-desc="Pour vous" text="">
    <node class="android.widget.TextView" resource-id="com.instagram.android:id/context_menu_item_label"
          bounds="[106,1080][332,1133]" text="Pour vous" content-desc=""/>
  </node>
  <node class="android.widget.Button" resource-id="com.instagram.android:id/context_menu_item"
        bounds="[32,1165][539,1282]" content-desc="Les plus r&#233;cents" text="">
    <node class="android.widget.TextView" resource-id="com.instagram.android:id/context_menu_item_label"
          bounds="[106,1197][423,1250]" text="Les plus r&#233;cents" content-desc=""/>
  </node>
  <node class="android.widget.Button" resource-id="com.instagram.android:id/context_menu_item"
        bounds="[32,1282][539,1399]" content-desc="Meta Verified" text=""/>
</hierarchy>
"""

# The feed's own header says "Pour vous" as well, and so does a tab on the hashtag page. Neither
# screen has any comment sorting, so the control must not be found there.
FEED_HEADER_ONLY = """
<hierarchy>
  <node class="android.view.ViewGroup" bounds="[0,100][1080,300]" text="Pour vous" content-desc="Pour vous"/>
</hierarchy>
"""


def _count(xml, selector):
    return len(etree.fromstring(xml.encode()).xpath(selector))


def test_the_sort_control_is_found_on_a_french_comments_sheet():
    assert _count(COMMENTS_SHEET, POST_COMMENTS_SELECTORS.comment_sort_button) == 1


def test_a_feed_header_saying_the_same_words_is_not_the_sort_control():
    assert _count(FEED_HEADER_ONLY, POST_COMMENTS_SELECTORS.comment_sort_button) == 0


def test_every_sort_option_is_reachable_in_the_language_the_menu_uses():
    # French for the first two, English for Meta Verified -- which stays English on a French
    # phone, which is why both labels of each pair are tried rather than one guessed.
    for labels in POST_COMMENTS_SELECTORS.sort_options.values():
        found = [
            label
            for label in labels
            if _count(SORT_MENU, POST_COMMENTS_SELECTORS.sort_option_selector(label))
        ]
        assert found, f"none of {labels} matched the menu"
