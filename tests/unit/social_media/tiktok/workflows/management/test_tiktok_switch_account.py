from taktik.core.social_media.tiktok.auth.switch import TikTokSwitchAccount
from taktik.core.social_media.tiktok.ui.selectors.shell.auth.account_switch import (
    ACCOUNT_SWITCH_SELECTORS,
)


def _profile_xml(username: str, *, own: bool = True) -> str:
    own_profile_marker = (
        '<node package="com.zhiliaoapp.musically" '
        'resource-id="com.zhiliaoapp.musically:id/mks" class="android.widget.FrameLayout" '
        'content-desc="Profile" selected="true" bounds="[576,1390][720,1476]" />'
        if own else ""
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node package="com.zhiliaoapp.musically" resource-id="com.zhiliaoapp.musically:id/qf8" class="android.widget.Button" text="Display name" clickable="true" bounds="[205,342][515,381]" />
  <node package="com.zhiliaoapp.musically" resource-id="com.zhiliaoapp.musically:id/qh5" class="android.widget.Button" text="@{username}" clickable="true" bounds="[251,386][468,412]" />
  {own_profile_marker}
</hierarchy>"""


SWITCHER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node package="com.zhiliaoapp.musically" resource-id="com.zhiliaoapp.musically:id/f0u" class="android.widget.FrameLayout" content-desc="Bottom sheet" bounds="[0,853][720,1476]">
    <node package="com.zhiliaoapp.musically" resource-id="com.zhiliaoapp.musically:id/nmh" class="android.widget.TextView" text="Switch account" content-desc="Switch account" bounds="[249,879][472,918]" />
    <node package="com.zhiliaoapp.musically" class="android.widget.Button" content-desc="Close" clickable="true" bounds="[636,863][706,933]" />
    <node package="com.zhiliaoapp.musically" resource-id="com.zhiliaoapp.musically:id/k5o" class="android.widget.Button" content-desc="explainedsummary" clickable="true" selected="true" bounds="[0,958][720,1084]">
      <node package="com.zhiliaoapp.musically" resource-id="com.zhiliaoapp.musically:id/ljk" class="android.widget.TextView" text="explainedsummary" selected="true" bounds="[147,1004][399,1039]" />
      <node package="com.zhiliaoapp.musically" resource-id="com.zhiliaoapp.musically:id/en4" class="android.widget.ImageView" content-desc="Checkmark" selected="true" bounds="[650,1000][692,1042]" />
    </node>
    <node package="com.zhiliaoapp.musically" resource-id="com.zhiliaoapp.musically:id/k5o" class="android.widget.Button" content-desc="toki6913" clickable="true" selected="false" bounds="[0,1084][720,1210]">
      <node package="com.zhiliaoapp.musically" resource-id="com.zhiliaoapp.musically:id/ljk" class="android.widget.TextView" text="toki6913" bounds="[147,1130][264,1165]" />
    </node>
    <node package="com.zhiliaoapp.musically" resource-id="com.zhiliaoapp.musically:id/k5o" class="android.widget.Button" content-desc="zlatan7405" clickable="true" selected="false" bounds="[0,1210][720,1336]">
      <node package="com.zhiliaoapp.musically" resource-id="com.zhiliaoapp.musically:id/ljk" class="android.widget.TextView" text="zlatan7405" bounds="[147,1256][295,1291]" />
    </node>
    <node package="com.zhiliaoapp.musically" resource-id="com.zhiliaoapp.musically:id/k5o" class="android.widget.Button" content-desc="Add account" clickable="true" bounds="[0,1336][720,1462]">
      <node package="com.zhiliaoapp.musically" resource-id="com.zhiliaoapp.musically:id/ljk" class="android.widget.TextView" text="Add account" bounds="[147,1382][315,1417]" />
    </node>
  </node>
</hierarchy>"""


def _profile_xml_4673(username: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node resource-id="com.zhiliaoapp.musically:id/su7" class="android.widget.Button" text="Display name" clickable="true" bounds="[28,200][422,248]" />
  <node resource-id="com.zhiliaoapp.musically:id/sr3" class="android.widget.Button" text="@{username}" clickable="true" bounds="[28,252][244,278]" />
  <node resource-id="com.zhiliaoapp.musically:id/oeg" class="android.widget.FrameLayout" content-desc="Profile" selected="true" bounds="[576,1390][720,1411]" />
</hierarchy>"""


SWITCHER_XML_4673 = """<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node resource-id="com.zhiliaoapp.musically:id/fxf" class="android.widget.FrameLayout" content-desc="Bottom sheet" bounds="[0,853][720,1411]">
    <node resource-id="com.zhiliaoapp.musically:id/pke" class="android.widget.TextView" text="Switch account" content-desc="Switch account" bounds="[249,879][472,918]" />
    <node class="android.widget.Button" content-desc="Close" clickable="true" bounds="[636,860][706,937]" />
    <node resource-id="com.zhiliaoapp.musically:id/lkp" class="android.widget.Button" content-desc="explainedsummary" clickable="true" selected="true" bounds="[0,958][720,1084]">
      <node resource-id="com.zhiliaoapp.musically:id/n72" class="android.widget.TextView" text="explainedsummary" selected="true" bounds="[147,1004][399,1039]" />
      <node resource-id="com.zhiliaoapp.musically:id/fiu" class="android.widget.ImageView" content-desc="Checkmark" selected="true" bounds="[650,1000][692,1042]" />
    </node>
    <node resource-id="com.zhiliaoapp.musically:id/lkp" class="android.widget.Button" content-desc="toki6913" clickable="true" selected="false" bounds="[0,1084][720,1210]">
      <node resource-id="com.zhiliaoapp.musically:id/n72" class="android.widget.TextView" text="toki6913" bounds="[147,1130][264,1165]" />
    </node>
    <node resource-id="com.zhiliaoapp.musically:id/lkp" class="android.widget.Button" content-desc="zlatan7405" clickable="true" selected="false" bounds="[0,1210][720,1336]">
      <node resource-id="com.zhiliaoapp.musically:id/n72" class="android.widget.TextView" text="zlatan7405" bounds="[147,1256][295,1291]" />
    </node>
    <node resource-id="com.zhiliaoapp.musically:id/lkp" class="android.widget.Button" content-desc="Add account" clickable="true" bounds="[0,1336][720,1411]">
      <node resource-id="com.zhiliaoapp.musically:id/n72" class="android.widget.TextView" text="Add account" bounds="[147,1382][315,1411]" />
    </node>
  </node>
</hierarchy>"""


def _save_login_prompt_xml(username: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node class="android.widget.FrameLayout" package="com.zhiliaoapp.musically" bounds="[0,0][720,1411]">
    <node resource-id="com.zhiliaoapp.musically:id/visual_area" class="android.widget.FrameLayout" content-desc="Dialog" bounds="[115,541][605,1011]">
      <node resource-id="com.zhiliaoapp.musically:id/yxo" class="android.widget.TextView" text="Save login for next time?" bounds="[153,695][566,739]" />
      <node resource-id="com.zhiliaoapp.musically:id/f43" class="android.widget.TextView" text="Log in to {username} on this device without needing to enter your info. You can change this at any time in Settings." bounds="[150,760][563,892]" />
      <node class="android.widget.Button" text="Save login" clickable="true" bounds="[360,928][604,1011]" />
      <node class="android.widget.Button" text="Not now" clickable="true" bounds="[115,928][359,1011]" />
    </node>
  </node>
</hierarchy>"""


HOME_XML_4673 = """<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node resource-id="com.zhiliaoapp.musically:id/of8" class="android.widget.TabHost">
    <node resource-id="com.zhiliaoapp.musically:id/oee" class="android.widget.FrameLayout" content-desc="Home" clickable="true" selected="true" />
    <node resource-id="com.zhiliaoapp.musically:id/oeg" class="android.widget.FrameLayout" content-desc="Profile" clickable="true" selected="false" />
  </node>
</hierarchy>"""


LOGIN_XML = """<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node class="android.widget.EditText" password="false" clickable="true" />
  <node class="android.widget.EditText" password="true" clickable="true" />
  <node class="android.widget.Button" text="Log in" clickable="true" />
</hierarchy>"""


DUPLICATE_SWITCHER_XML = SWITCHER_XML.replace(
    'content-desc="zlatan7405"',
    'content-desc="toki6913"',
)


class _Element:
    def __init__(self, device, selector: str, exists: bool):
        self.device = device
        self.selector = selector
        self.exists = exists

    def click(self):
        self.device.click_selector(self.selector)


class _SwitcherDevice:
    def __init__(self, active="explainedsummary", switch_result="toki6913", android_user=0):
        self.state = "profile"
        self.active = active
        self.switch_result = switch_result
        self.android_user = android_user
        self.clicked = []

    def shell(self, command):
        assert command == "am get-current-user"
        return str(self.android_user)

    def dump_hierarchy(self, compressed=False):
        if self.state == "switcher":
            return SWITCHER_XML
        if self.state == "visited_profile":
            return _profile_xml("toki6913", own=False)
        return _profile_xml(self.active) if self.active else "<hierarchy />"

    def xpath(self, selector):
        exists = False
        if ":id/qf8" in selector and self.state == "profile":
            exists = True
        elif ":id/k5o" in selector and self.state == "switcher":
            exists = any(name in selector for name in ("explainedsummary", "toki6913", "zlatan7405"))
        elif "@content-desc=\"Close\"" in selector and self.state == "switcher":
            exists = True
        return _Element(self, selector, exists)

    def click_selector(self, selector):
        self.clicked.append(selector)
        if ":id/qf8" in selector:
            self.state = "switcher"
        elif ":id/k5o" in selector:
            self.state = "profile"
            self.active = self.switch_result
        elif "Close" in selector:
            self.state = "profile"


class _SwitcherDevice4673(_SwitcherDevice):
    def dump_hierarchy(self, compressed=False):
        if self.state == "switcher":
            return SWITCHER_XML_4673
        return _profile_xml_4673(self.active) if self.active else "<hierarchy />"

    def xpath(self, selector):
        exists = False
        if ":id/su7" in selector and self.state == "profile":
            exists = True
        elif ":id/lkp" in selector and self.state == "switcher":
            exists = any(name in selector for name in ("explainedsummary", "toki6913", "zlatan7405"))
        elif "@content-desc=\"Close\"" in selector and self.state == "switcher":
            exists = True
        return _Element(self, selector, exists)

    def click_selector(self, selector):
        self.clicked.append(selector)
        if ":id/su7" in selector:
            self.state = "switcher"
        elif ":id/lkp" in selector:
            self.state = "profile"
            self.active = self.switch_result
        elif "Close" in selector:
            self.state = "profile"


class _SwitcherDevice4673WithSaveLoginPrompt(_SwitcherDevice4673):
    def dump_hierarchy(self, compressed=False):
        if self.state == "post_switch_prompt":
            return _save_login_prompt_xml(self.active)
        return super().dump_hierarchy(compressed=compressed)

    def xpath(self, selector):
        if self.state == "post_switch_prompt" and "Not now" in selector:
            return _Element(self, selector, True)
        return super().xpath(selector)

    def click_selector(self, selector):
        if self.state == "switcher" and ":id/lkp" in selector:
            self.clicked.append(selector)
            self.active = self.switch_result
            self.state = "post_switch_prompt"
        elif self.state == "post_switch_prompt" and "Not now" in selector:
            self.clicked.append(selector)
            self.state = "profile"
        else:
            super().click_selector(selector)


class _SwitcherDevice4673LandingOnHome(_SwitcherDevice4673):
    def dump_hierarchy(self, compressed=False):
        if self.state == "post_switch_home":
            return HOME_XML_4673
        return super().dump_hierarchy(compressed=compressed)

    def click_selector(self, selector):
        if self.state == "switcher" and ":id/lkp" in selector:
            self.clicked.append(selector)
            self.active = self.switch_result
            self.state = "post_switch_home"
        else:
            super().click_selector(selector)


class _LoginDevice(_SwitcherDevice):
    def __init__(self):
        super().__init__(active="")
        self.state = "login"

    def dump_hierarchy(self, compressed=False):
        return LOGIN_XML


class _DuplicateSwitcherDevice(_SwitcherDevice):
    def dump_hierarchy(self, compressed=False):
        if self.state == "switcher":
            return DUPLICATE_SWITCHER_XML
        return super().dump_hierarchy(compressed=compressed)


class _UnknownAfterSelectionDevice(_SwitcherDevice):
    def click_selector(self, selector):
        if self.state == "switcher" and ":id/k5o" in selector:
            self.clicked.append(selector)
            self.active = ""
            self.state = "unknown"
            return
        super().click_selector(selector)


class _LoginAfterSelectionDevice(_SwitcherDevice):
    def click_selector(self, selector):
        if self.state == "switcher" and ":id/k5o" in selector:
            self.clicked.append(selector)
            self.state = "login"
            return
        super().click_selector(selector)

    def dump_hierarchy(self, compressed=False):
        if self.state == "login":
            return LOGIN_XML
        return super().dump_hierarchy(compressed=compressed)


def _use_4673_selectors(monkeypatch):
    values = {
        "profile_switcher_button": [
            '//android.widget.Button[contains(@resource-id, ":id/su7")]'
        ],
        "profile_username": ['//*[contains(@resource-id, ":id/sr3")]'],
        "account_rows": ['//android.widget.Button[contains(@resource-id, ":id/lkp")]'],
        "username_labels": ['//*[contains(@resource-id, ":id/n72")]'],
        "active_indicators": ['//*[contains(@resource-id, ":id/fiu")]'],
        "account_row_templates": [
            '//android.widget.Button[contains(@resource-id, ":id/lkp") and '
            'translate(@content-desc, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", '
            '"abcdefghijklmnopqrstuvwxyz")="{username}"]'
        ],
    }
    for name, value in values.items():
        monkeypatch.setattr(ACCOUNT_SWITCH_SELECTORS, name, value, raising=False)


def _switcher(device, **kwargs):
    kwargs.setdefault("transition_timeout", 0.01)
    return TikTokSwitchAccount(
        device,
        "R9HN70LZYEJ",
        android_user_id=0,
        sleeper=lambda _: None,
        **kwargs,
    )


def test_switch_account_returns_success_without_opening_switcher_when_target_is_active():
    device = _SwitcherDevice(active="explainedsummary")

    result = _switcher(device).switch_account("@ExplainedSummary")

    assert result["success"] is True
    assert result["already_active"] is True
    assert result["active_username"] == "explainedsummary"
    assert device.clicked == []


def test_list_accounts_reads_native_rows_and_excludes_add_account():
    result = _switcher(_SwitcherDevice()).list_accounts()

    assert result["success"] is True
    assert result["active_username"] == "explainedsummary"
    assert result["accounts"] == ["explainedsummary", "toki6913", "zlatan7405"]
    assert result["android_user_id"] == 0


def test_switch_account_fails_safely_when_target_is_not_in_native_switcher():
    result = _switcher(_SwitcherDevice()).switch_account("missing.account")

    assert result["success"] is False
    assert result["error_type"] == "target_not_found"
    assert result["active_username"] == "explainedsummary"
    assert result["accounts"] == ["explainedsummary", "toki6913", "zlatan7405"]


def test_switch_account_verifies_the_profile_username_after_selecting_row():
    result = _switcher(_SwitcherDevice(switch_result="toki6913")).switch_account("toki6913")

    assert result["success"] is True
    assert result["already_active"] is False
    assert result["active_username"] == "toki6913"


def test_switch_account_reports_failure_when_selected_profile_cannot_be_verified():
    result = _switcher(_SwitcherDevice(switch_result="wrongaccount")).switch_account("toki6913")

    assert result["success"] is False
    assert result["error_type"] == "verification_failed"
    assert result["active_username"] == "wrongaccount"


def test_verification_failure_does_not_report_stale_previous_account_as_active():
    class _Navigator:
        def navigate_to_profile(self):
            return False

    result = _switcher(
        _UnknownAfterSelectionDevice(),
        navigator_factory=lambda _device: _Navigator(),
        max_attempts=1,
        transition_timeout=0,
    ).switch_account("toki6913")

    assert result["success"] is False
    assert result["error_type"] == "verification_failed"
    assert result["previous_username"] == "explainedsummary"
    assert result["active_username"] is None
    assert result["state_known"] is False


def test_viewed_creator_profile_is_not_mistaken_for_the_active_account():
    class _Navigator:
        calls = 0

        def __init__(self, device):
            self.device = device

        def navigate_to_profile(self):
            self.calls += 1
            self.device.state = "profile"
            return True

    device = _SwitcherDevice(active="explainedsummary", switch_result="toki6913")
    device.state = "visited_profile"
    navigator = _Navigator(device)

    result = _switcher(device, navigator_factory=lambda _device: navigator).switch_account("toki6913")

    assert result["success"] is True
    assert result["already_active"] is False
    assert navigator.calls == 1


def test_core_workflow_refuses_a_different_android_user_before_reading_tiktok():
    device = _SwitcherDevice(android_user=10)

    result = _switcher(device).list_accounts()

    assert result["success"] is False
    assert result["error_type"] == "android_user_mismatch"
    assert result["android_user_id"] == 0
    assert device.clicked == []


def test_tiktok_4673_selectors_list_all_native_accounts(monkeypatch):
    _use_4673_selectors(monkeypatch)

    result = _switcher(_SwitcherDevice4673()).list_accounts()

    assert result["success"] is True
    assert result["active_username"] == "explainedsummary"
    assert result["accounts"] == ["explainedsummary", "toki6913", "zlatan7405"]


def test_tiktok_4673_exact_row_selector_switches_and_verifies(monkeypatch):
    _use_4673_selectors(monkeypatch)
    device = _SwitcherDevice4673(active="zlatan7405", switch_result="explainedsummary")

    result = _switcher(device).switch_account("explainedsummary")

    assert result["success"] is True
    assert result["already_active"] is False
    assert result["active_username"] == "explainedsummary"
    assert any(":id/lkp" in selector for selector in device.clicked)


def test_tiktok_4673_dismisses_save_login_prompt_before_verifying_profile(monkeypatch):
    _use_4673_selectors(monkeypatch)
    device = _SwitcherDevice4673WithSaveLoginPrompt(
        active="zlatan7405",
        switch_result="explainedsummary",
    )

    result = _switcher(device).switch_account("explainedsummary")

    assert result["success"] is True
    assert result["active_username"] == "explainedsummary"
    assert any("Not now" in selector for selector in device.clicked)


def test_tiktok_4673_navigates_from_home_to_profile_before_verifying(monkeypatch):
    _use_4673_selectors(monkeypatch)
    device = _SwitcherDevice4673LandingOnHome(
        active="toki6913",
        switch_result="explainedsummary",
    )

    class _Navigator:
        calls = 0

        def __init__(self, _device):
            pass

        def navigate_to_profile(self):
            self.calls += 1
            device.state = "profile"
            return True

    navigator = _Navigator(device)
    result = _switcher(
        device,
        navigator_factory=lambda _device: navigator,
    ).switch_account("explainedsummary")

    assert result["success"] is True
    assert result["active_username"] == "explainedsummary"
    assert navigator.calls == 1


def test_switch_account_distinguishes_expired_login_session():
    class _Navigator:
        def navigate_to_profile(self):
            return False

    result = _switcher(
        _LoginDevice(),
        navigator_factory=lambda _device: _Navigator(),
    ).switch_account("toki6913")

    assert result["success"] is False
    assert result["error_type"] == "session_expired"
    assert result["failure_category"] == "login_session_expired"
    assert result["failure_stage"] == "detect_active"
    assert result["relogin_required"] is True


def test_switch_account_reports_relogin_when_target_session_expires_after_selection():
    result = _switcher(
        _LoginAfterSelectionDevice(),
        max_attempts=1,
        transition_timeout=0,
    ).switch_account("toki6913")

    assert result["success"] is False
    assert result["error_type"] == "session_expired"
    assert result["active_username"] is None
    assert result["previous_username"] == "explainedsummary"
    assert result["relogin_required"] is True


def test_switch_account_rejects_duplicate_target_rows_without_tapping():
    device = _DuplicateSwitcherDevice()

    result = _switcher(device).switch_account("toki6913")

    assert result["success"] is False
    assert result["error_type"] == "ambiguous_target"
    assert result["failure_stage"] == "lookup"
    assert result["ambiguous_accounts"] == ["toki6913"]
    assert not any("toki6913" in selector for selector in device.clicked)


def test_switch_account_retries_selector_miss_and_succeeds_on_second_attempt():
    device = _SwitcherDevice(switch_result="toki6913")
    switcher = _switcher(device, max_attempts=2, transition_timeout=0)
    original_click = switcher._click_first
    selection_calls = 0

    def click_with_one_selection_miss(selectors):
        nonlocal selection_calls
        if any("toki6913" in selector for selector in selectors):
            selection_calls += 1
            if selection_calls == 1:
                return False
        return original_click(selectors)

    switcher._click_first = click_with_one_selection_miss

    result = switcher.switch_account("toki6913")

    assert result["success"] is True
    assert result["attempts"] == 2


def test_switch_account_reports_selector_failure_when_all_retries_are_exhausted():
    device = _SwitcherDevice()
    switcher = _switcher(device, max_attempts=2, transition_timeout=0)
    original_click = switcher._click_first

    def never_select_target(selectors):
        if any("toki6913" in selector for selector in selectors):
            return False
        return original_click(selectors)

    switcher._click_first = never_select_target

    result = switcher.switch_account("toki6913")

    assert result["success"] is False
    assert result["error_type"] == "selection_failed"
    assert result["failure_category"] == "selector_not_found"
    assert result["failure_stage"] == "select"
    assert result["attempts"] == 2


def test_switch_account_classifies_missing_switcher_selector_and_preserves_active_account():
    device = _SwitcherDevice()
    device.xpath = lambda selector: _Element(device, selector, False)

    result = _switcher(device, max_attempts=1, transition_timeout=0).switch_account("toki6913")

    assert result["success"] is False
    assert result["error_type"] == "switcher_unavailable"
    assert result["failure_category"] == "selector_not_found"
    assert result["failure_stage"] == "open_switcher"
    assert result["active_username"] == "explainedsummary"
    assert result["state_known"] is True
