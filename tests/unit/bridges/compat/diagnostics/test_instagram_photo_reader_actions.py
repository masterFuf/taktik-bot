"""The Lab actions of the readers moved onto the screen photo (steps 3 L5-L6): the production reads."""

from types import SimpleNamespace

from uiautomator2.xpath import XPathEntry

from bridges.compat.diagnostics.actions.instagram.comment import read_visible_texts
from bridges.compat.diagnostics.actions.instagram.profile import extract_avatar, extract_own_avatar
from taktik.core.shared.device.facade import BaseDeviceFacade

# One Compose comment row (IG 442 shape: no body id, "<author> said <text>"), invented names.
THREAD = """<hierarchy rotation="0">
  <node class="android.view.ViewGroup" bounds="[0,1037][1080,1280]" content-desc="">
    <node class="android.widget.ImageView" bounds="[42,1068][137,1163]" content-desc="Go to demo_one's profile"/>
    <node class="android.view.ViewGroup" bounds="[148,1058][933,1199]" content-desc="">
      <node class="android.widget.TextView" bounds="[172,1058][423,1099]" text="demo_one" content-desc="demo_one&#160; "/>
      <node class="android.view.ViewGroup" bounds="[426,1058][472,1099]" text="6h" content-desc="6h"/>
      <node class="android.view.ViewGroup" bounds="[172,1110][933,1199]"
            text="demo_one said nice light" content-desc="demo_one said nice light"/>
    </node>
    <node class="android.view.View" bounds="[172,1199][363,1280]" text="Reply" content-desc="Reply"/>
  </node>
</hierarchy>"""


class _Phone:
    """uiautomator2 as the persona reader touches it: `xpath()` and a dump, both counted."""

    wait_timeout = 1.0

    def __init__(self, xml):
        self.xml, self.dumps = xml, 0
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        self.dumps += 1
        return self.xml


def test_the_avatar_actions_run_the_production_crops_and_never_return_the_picture():
    calls = []
    detection = SimpleNamespace(
        extract_profile_image=lambda: calls.append("header") or "data:image/jpeg;base64," + "A" * 4096,
        extract_own_avatar_from_tab=lambda: calls.append("tab") or None,
    )
    header = extract_avatar(SimpleNamespace(detection=detection), {})
    tab = extract_own_avatar(SimpleNamespace(detection=detection), {})
    assert calls == ["header", "tab"]
    assert header["success"] is True and header["details"] == {"extracted": True, "size_kb": 3}
    assert "base64" not in str(header)
    assert tab["success"] is False and tab["details"] == {"extracted": False, "size_kb": 0}


def test_the_persona_reading_reads_the_rows_of_one_photo_and_gives_the_lab_its_logger_back(monkeypatch):
    from bridges.compat.diagnostics.runtime import events

    restored = []
    monkeypatch.setattr(events, "configure_logger", lambda: restored.append(True))
    phone = _Phone(THREAD)
    result = read_visible_texts(SimpleNamespace(device=BaseDeviceFacade(phone)), {})
    assert result["success"] is True and result["details"]["count"] == 1
    assert "nice light" in result["details"]["texts"][0]
    assert restored == [True]
    assert phone.dumps == 2  # the id path's `d.xpath()`, then one photo
