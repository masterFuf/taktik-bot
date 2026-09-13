from taktik.core.social_media.tiktok.ui.video_snapshot import parse_video_snapshot


VIDEO_43_XML = """<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <android.widget.FrameLayout package="com.zhiliaoapp.musically" resource-id="com.zhiliaoapp.musically:id/gy_" clickable="true" bounds="[0,0][720,1476]">
    <android.widget.Button resource-id="com.zhiliaoapp.musically:id/f57" clickable="true" content-desc="Creator profile" bounds="[620,650][720,750]">
      <android.widget.ImageView resource-id="com.zhiliaoapp.musically:id/f4u" content-desc="Profile" bounds="[635,665][705,735]" />
    </android.widget.Button>
    <android.widget.Button resource-id="com.zhiliaoapp.musically:id/dtv" clickable="true" content-desc="Open creator profile" bounds="[620,700][720,800]" />
    <android.widget.ImageView resource-id="com.zhiliaoapp.musically:id/yx4" clickable="true" content-desc="Nympha Ophis profile" bounds="[628,752][705,829]" />
    <android.widget.Button resource-id="com.zhiliaoapp.musically:id/hi1" clickable="true" content-desc="Follow Nympha Ophis" bounds="[614,800][720,861]" />
    <android.widget.Button resource-id="com.zhiliaoapp.musically:id/f57" clickable="true" content-desc="Like video. 63.9K likes" bounds="[608,861][720,966]">
      <android.widget.ImageView resource-id="com.zhiliaoapp.musically:id/f4u" content-desc="Like" bounds="[628,861][707,940]" />
      <android.widget.Button resource-id="com.zhiliaoapp.musically:id/f4z" clickable="true" text="63.9K" bounds="[608,940][720,955]" />
    </android.widget.Button>
    <android.widget.Button resource-id="com.zhiliaoapp.musically:id/dtv" clickable="true" content-desc="Read or add comments. 311 comments" bounds="[580,966][720,1071]" />
    <android.widget.Button resource-id="com.zhiliaoapp.musically:id/title" clickable="true" text="Nympha Ophis" bounds="[21,1221][227,1260]" />
    <com.bytedance.tux.input.TuxTextLayoutView resource-id="com.zhiliaoapp.musically:id/desc" clickable="true" text="Twirling around #Versailles&#10;…more" bounds="[21,1267][580,1333]" />
    <android.widget.Button resource-id="com.zhiliaoapp.musically:id/nhe" clickable="true" content-desc="Sound: Golden Brown by Roksolana" bounds="[580,1281][720,1390]" />
    <android.widget.FrameLayout clickable="true" content-desc="For You" bounds="[459,77][568,179]" />
    <android.widget.FrameLayout resource-id="com.zhiliaoapp.musically:id/mkq" clickable="true" content-desc="Home" bounds="[0,1390][144,1476]" />
  </android.widget.FrameLayout>
</hierarchy>"""


# Reduced to the nodes relevant to video perception from the live Galaxy A11 hierarchy
# captured in TikTok 43.1.4 DetailActivity on 2026-09-04. Unlike the original feed fixture,
# this surface has no gy_ node: long_press_layout is its video container, the author is in the
# top title button, and the like count exists only in f57's accessibility description.
DETAIL_ACTIVITY_43_XML = """<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node resource-id="com.zhiliaoapp.musically:id/s28" class="android.widget.FrameLayout" package="com.zhiliaoapp.musically" clickable="true" bounds="[0,0][720,1476]">
    <node resource-id="com.zhiliaoapp.musically:id/long_press_layout" class="android.view.View" package="com.zhiliaoapp.musically" clickable="false" bounds="[0,91][720,1364]" />
    <node resource-id="com.zhiliaoapp.musically:id/title" class="android.widget.Button" package="com.zhiliaoapp.musically" text="xenq2" clickable="true" bounds="[91,146][174,181]" />
    <node resource-id="com.zhiliaoapp.musically:id/f57" class="android.widget.LinearLayout" package="com.zhiliaoapp.musically" content-desc="Like video. 5 likes" clickable="true" bounds="[552,1385][629,1462]">
      <node resource-id="com.zhiliaoapp.musically:id/f4u" class="android.widget.ImageView" package="com.zhiliaoapp.musically" content-desc="Like" bounds="[570,1390][611,1431]" />
    </node>
    <node resource-id="com.zhiliaoapp.musically:id/qwx" class="android.widget.EditText" package="com.zhiliaoapp.musically" text="Message..." clickable="true" bounds="[16,1385][530,1462]" />
  </node>
</hierarchy>"""


# Reduced from the actual selector-miss capture made when the long-run regression was active:
# 2026-09-04-18-47-05_selector_miss_aa997d65.xml. It is a creator profile, not another feed
# layout, and a successful parse of it must remain distinguishable from an unavailable dump.
CREATOR_PROFILE_43_XML = """<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node class="android.widget.FrameLayout" package="com.zhiliaoapp.musically" bounds="[0,77][720,1476]">
    <node class="android.widget.ImageView" package="com.zhiliaoapp.musically" content-desc="Notifications" bounds="[566,87][636,157]" />
    <node class="android.widget.ImageView" package="com.zhiliaoapp.musically" content-desc="Share" bounds="[636,87][706,157]" />
    <node class="android.widget.Button" package="com.zhiliaoapp.musically" text="Nordicmilkman" clickable="true" bounds="[224,226][477,270]" />
    <node resource-id="com.zhiliaoapp.musically:id/qh5" class="android.widget.Button" package="com.zhiliaoapp.musically" text="@nordicmilkman" clickable="true" bounds="[224,270][396,306]" />
    <node resource-id="com.zhiliaoapp.musically:id/qfv" class="android.widget.TextView" package="com.zhiliaoapp.musically" text="Following" bounds="[28,414][125,442]" />
    <node resource-id="com.zhiliaoapp.musically:id/qfv" class="android.widget.TextView" package="com.zhiliaoapp.musically" text="Follower" bounds="[196,414][282,442]" />
    <node resource-id="com.zhiliaoapp.musically:id/qfv" class="android.widget.TextView" package="com.zhiliaoapp.musically" text="Like" bounds="[353,414][394,442]" />
    <node resource-id="com.zhiliaoapp.musically:id/eme" class="android.widget.TextView" package="com.zhiliaoapp.musically" text="Follow" bounds="[28,518][321,581]" />
    <node class="android.widget.RelativeLayout" package="com.zhiliaoapp.musically" content-desc="Videos" clickable="true" selected="true" bounds="[28,599][249,669]" />
    <node resource-id="com.zhiliaoapp.musically:id/xxy" class="android.widget.TextView" package="com.zhiliaoapp.musically" text="2,339" bounds="[7,954][238,982]" />
  </node>
</hierarchy>"""


def test_43_1_4_snapshot_extracts_author_and_like_count_from_one_hierarchy():
    snapshot = parse_video_snapshot(VIDEO_43_XML)

    assert snapshot.author == "Nympha Ophis"
    assert snapshot.like_count == "63.9K"
    assert snapshot.description == "Twirling around #Versailles\n…more"
    assert snapshot.sound == "Golden Brown by Roksolana"
    assert snapshot.signature


def test_43_1_4_detail_activity_alternate_video_layout_is_recognized():
    snapshot = parse_video_snapshot(DETAIL_ACTIVITY_43_XML)

    assert snapshot.hierarchy_parsed is True
    assert snapshot.video_visible is True
    assert snapshot.author == "xenq2"
    assert snapshot.like_count == "5"
    assert snapshot.signature


def test_43_1_4_creator_profile_is_a_parsed_non_video_surface():
    snapshot = parse_video_snapshot(CREATOR_PROFILE_43_XML)

    assert snapshot.hierarchy_parsed is True
    assert snapshot.video_visible is False


def test_touch_down_exclusions_cover_caption_creator_actions_header_and_navigation():
    bounds = parse_video_snapshot(VIDEO_43_XML).interactive_bounds

    assert (21, 1267, 580, 1333) in bounds
    assert (628, 752, 705, 829) in bounds
    assert (608, 861, 720, 966) in bounds
    assert (580, 966, 720, 1071) in bounds
    assert (459, 77, 568, 179) in bounds
    assert (0, 1390, 144, 1476) in bounds
    assert (0, 0, 720, 1476) not in bounds


def test_signature_changes_when_the_video_identity_changes():
    first = parse_video_snapshot(VIDEO_43_XML).signature
    second = parse_video_snapshot(VIDEO_43_XML.replace("Nympha Ophis", "Next Creator")).signature

    assert first != second
