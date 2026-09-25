"""The profile header of Instagram 447 against the 410 baseline, on invented dumps of the real shapes.

410: the category line has its own id, outside the info block; the bio sits in the info block
(`profile_user_info_compose_view`), two Views down. 447: the category line lost its id and moved
into the info block, as the TextView right under its first View; the bio stays two Views down.
The 447 entries live in the version overrides, never in the baseline.
"""

from pathlib import Path

import yaml

from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.selectors import DETECTION_SELECTORS, PROFILE_SELECTORS

OVERRIDES = Path(__file__).resolve().parents[4] / "taktik" / "core" / "compat" / "data" / "overrides" / "instagram.yaml"

_INFO = 'resource-id="com.instagram.android:id/profile_user_info_compose_view" class="com.facebook.compose.view.MetaComposeView"'


def _dump(category_410: str = "", category_447: str = "", bio: str = "A bio written by nobody") -> str:
    outside = (f'<node text="{category_410}" resource-id="com.instagram.android:id/profile_header_business_category"'
               f' class="android.widget.TextView" />') if category_410 else ""
    inside = f'<node text="{category_447}" resource-id="" class="android.widget.TextView" />' if category_447 else ""
    return f"""<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node text="" resource-id="com.instagram.android:id/profile_header_container" class="android.widget.LinearLayout">
    {outside}
    <node text="" {_INFO}>
      <node text="" resource-id="" class="android.view.View">
        {inside}
        <node text="" resource-id="" class="android.view.View">
          <node text="{bio}" resource-id="" class="android.widget.TextView" />
        </node>
      </node>
    </node>
  </node>
</hierarchy>"""


def _overrides_447() -> dict:
    return yaml.safe_load(OVERRIDES.read_text(encoding="utf-8"))["versions"]["447.0.0.0"]


def _first_text(tree, selectors):
    for selector in selectors:
        nodes = tree.xpath(selector)
        if nodes:
            return nodes[0].get("text")
    return None


def _matches(tree, selectors) -> bool:
    return any(tree.xpath(selector) for selector in selectors)


def test_447_professional_header_reads_category_flag_and_bio():
    tree = parse_ui_dump(_dump(category_447="Gaming"))
    o = _overrides_447()
    assert _matches(tree, o["detection._business_account_indicators_base"])
    assert _first_text(tree, o["profile.enrichment_category_selectors"]) == "Gaming"
    assert _first_text(tree, o["profile.bio"]) == "A bio written by nobody"
    assert _first_text(tree, o["profile.enrichment_bio_selectors"]) == "A bio written by nobody"


def test_447_personal_header_is_not_professional():
    tree = parse_ui_dump(_dump())
    o = _overrides_447()
    assert not _matches(tree, o["detection._business_account_indicators_base"])
    assert _first_text(tree, o["profile.enrichment_category_selectors"]) is None
    assert _first_text(tree, o["profile.bio"]) == "A bio written by nobody"


def test_410_baseline_is_unchanged():
    tree = parse_ui_dump(_dump(category_410="Gaming"))
    assert _matches(tree, DETECTION_SELECTORS._business_account_indicators_base)
    assert _first_text(tree, PROFILE_SELECTORS.enrichment_category_selectors) == "Gaming"
    assert _first_text(tree, PROFILE_SELECTORS.bio) == "A bio written by nobody"
    personal = parse_ui_dump(_dump())
    assert not _matches(personal, DETECTION_SELECTORS._business_account_indicators_base)


def test_the_447_entries_stay_out_of_the_baseline():
    baseline = (DETECTION_SELECTORS._business_account_indicators_base
                + PROFILE_SELECTORS.enrichment_category_selectors)
    assert not any("profile_user_info_compose_view" in selector for selector in baseline)


class _Dumping:
    def __init__(self, xml):
        self._xml = xml

    def dump_hierarchy(self, *args, **kwargs):
        return self._xml


def test_batch_check_sees_the_tree_d_xpath_sees():
    """A selector written by tag (the uiautomator2 idiom) matches in the batch reader too."""
    facade = DeviceFacade(_Dumping(_dump(category_447="Gaming")))
    facade.get_xml_dump = lambda *a, **k: _dump(category_447="Gaming")
    result = facade.batch_xpath_check({"pro": _overrides_447()["detection._business_account_indicators_base"]})
    assert result == {"pro": True}
