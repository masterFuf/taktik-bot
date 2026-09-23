"""A follow list rendered as uiautomator XML, and a fake device that answers xpath from it.

Synthetic on purpose: the dumps captured on real phones carry real usernames and never enter
this public repository. The structure (resource ids, button texts, content-desc) follows the
dumps of Instagram 410 and 447 in English and French captured in September 2026; the usernames
are invented.
"""

from typing import Iterable, List, Optional, Tuple

from lxml import etree

PKG = "com.instagram.android"
ROW_HEIGHT = 180
TOP = 600


def follow_list_xml(rows: Iterable[Tuple[Optional[str], str]], extra: str = "") -> str:
    """rows = [(username or None, button text)]; `extra` is appended inside the hierarchy."""
    nodes = []
    for index, (username, button_text) in enumerate(rows):
        top = TOP + index * ROW_HEIGHT
        if username is not None:
            nodes.append(
                f'<node index="0" text="{username}" resource-id="{PKG}:id/follow_list_username" '
                f'class="android.widget.TextView" content-desc="" bounds="[200,{top + 40}][700,{top + 90}]" />'
            )
        nodes.append(
            f'<node index="1" text="{button_text}" resource-id="{PKG}:id/follow_list_row_large_follow_button" '
            f'class="android.widget.TextView" content-desc="" bounds="[760,{top + 30}][1040,{top + 150}]" />'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
        '<node index="0" text="" resource-id="" class="android.widget.FrameLayout" bounds="[0,0][1080,2400]">'
        + "".join(nodes) + extra + "</node></hierarchy>"
    )


def unified_tabs(selected: int, titles=("673 followers", "1 287 suivi(e)s", "0 abonnements", "À vérifier")) -> str:
    """The tab strip of the unified follow list, as Instagram 447 draws it in French: the
    title button of the tab shown carries selected="true". Pass it as `extra`."""
    tabs = "".join(
        f'<node index="{i}" text="{title}" resource-id="{PKG}:id/title" class="android.widget.Button" '
        f'selected="{"true" if i == selected else "false"}" clickable="true" '
        f'bounds="[{i * 270},279][{i * 270 + 260},405]" />'
        for i, title in enumerate(titles)
    )
    return (f'<node index="0" text="" resource-id="{PKG}:id/unified_follow_list_tab_layout" '
            f'class="android.widget.HorizontalScrollView" bounds="[0,279][1080,405]">{tabs}</node>')


class FakeElement:
    def __init__(self, node):
        self._node = node
        self.clicked = 0

    @property
    def text(self) -> str:
        return self._node.get("text", "")

    @property
    def attrib(self):
        return dict(self._node.attrib)

    @property
    def bounds(self):
        raw = self._node.get("bounds", "[0,0][0,0]")
        left_top, right_bottom = raw[1:-1].split("][")
        left, top = (int(v) for v in left_top.split(","))
        right, bottom = (int(v) for v in right_bottom.split(","))
        return left, top, right, bottom

    def click(self):
        self.clicked += 1


class FakeSelector:
    def __init__(self, screen: "FakeScreen", xpath: str):
        self._screen = screen
        self._xpath = xpath

    def all(self) -> List[FakeElement]:
        return [FakeElement(node) for node in self._screen.tree().xpath(self._xpath)]

    @property
    def exists(self) -> bool:
        return bool(self._screen.tree().xpath(self._xpath))

    def click(self):
        self._screen.clicks.append(self._xpath)

    @property
    def bounds(self):
        found = self.all()
        return found[0].bounds if found else None


class FakeScreen:
    """Stands for the raw uiautomator2 device: `xpath()` reads the current XML.

    `screens` is a list of XML strings; `advance()` moves to the next one (the screen after a
    tap), so a test can script what Instagram shows before and after an action.
    """

    def __init__(self, *screens: str):
        self.screens = list(screens)
        self.index = 0
        self.clicks: List[str] = []
        self.taps: List[tuple] = []
        self.presses: List[str] = []

    info = {"displayWidth": 1080, "displayHeight": 2400}

    def window_size(self):
        return 1080, 2400

    def tree(self):
        return etree.fromstring(self.screens[self.index].encode("utf-8"))

    def xpath(self, xpath: str) -> FakeSelector:
        return FakeSelector(self, xpath)

    def advance(self):
        if self.index < len(self.screens) - 1:
            self.index += 1

    # A raw uiautomator2 tap: the screen moves on to what Instagram shows next.
    def click(self, x, y):
        self.taps.append((x, y))
        self.advance()

    def long_click(self, x, y, duration=0.0):
        self.click(x, y)

    # The key names the uiautomator2 server knows. It takes a name or an int code, and ignores
    # anything else WITHOUT an error: "KEYCODE_BACK", which the Instagram facade's press('back')
    # sends, presses nothing (12 back presses out of 12 on the 4 phones of C2, 2026-09-23).
    KEY_NAMES = {"home", "back", "left", "right", "up", "down", "center", "menu", "search", "enter",
                 "delete", "del", "recent", "volume_up", "volume_down", "volume_mute", "camera", "power"}

    def press(self, key):
        # A back press the device obeys moves the script on (the profile closes, the list shows).
        self.presses.append(key)
        if isinstance(key, int) or str(key).lower() in self.KEY_NAMES:
            self.advance()


class FakeFacade:
    """The device facade a business action holds: `.device` is the raw device."""

    def __init__(self, screen: FakeScreen):
        self.device = screen
        self.taps: List[tuple] = []

    def human_tap(self, bounds, quick=False):
        self.taps.append(tuple(bounds))
        self.device.advance()
        return True



def walk_list(business, config=None, names=None):
    """Run the engine's production list walk on the fake screen and return its stats.

    The walk is `UnfollowBusiness._unfollow_in_open_list`, the inner loop of the one engine.
    Mode "all" without verified/business checks: no profile is opened, the rows are acted on
    directly; `names` defaults to every username the first screen shows.
    """
    cfg = {**business.default_config, "unfollow_mode": "all", "skip_verified": False,
           "skip_business": False, **(config or {})}
    targets = names if names is not None else [row["username"] for row in business._visible_follow_rows()]
    stats = business._new_stats()
    business._unfollow_in_open_list(cfg, targets, set(), stats)
    return stats


def profile_xml(username: str, follows_you: bool = False) -> str:
    """A profile screen: its action bar names the account; "Vous suit" when it follows us."""
    badge = ('<node index="3" text="Vous suit" resource-id="" class="android.widget.TextView" '
             'content-desc="" bounds="[40,520][300,560]" />') if follows_you else ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
        '<node index="0" text="" resource-id="" class="android.widget.FrameLayout" bounds="[0,0][1080,2400]">'
        f'<node index="1" text="{username}" resource-id="{PKG}:id/action_bar_title" '
        'class="android.widget.TextView" content-desc="" bounds="[200,100][800,160]" />'
        + badge + "</node></hierarchy>"
    )


class FakeDetection:
    """The detection facade, reading the fake screen: profile, list, and row state."""

    def __init__(self, screen: FakeScreen, business):
        self.screen = screen
        self.business = business

    def _title(self):
        nodes = self.screen.tree().xpath(f'//*[@resource-id="{PKG}:id/action_bar_title"]')
        return nodes[0].get("text") if nodes else None

    def is_on_profile_screen(self):
        return self._title() is not None

    def get_username_from_profile(self):
        return self._title()

    def is_following_list_open(self):
        return bool(self.screen.tree().xpath(f'//*[@resource-id="{PKG}:id/follow_list_username"]'))

    def is_verified_account(self):
        return False

    def is_business_account(self):
        return False

    def get_row_follow_state(self, username):
        for row in self.business._visible_follow_rows():
            if row["username"] == username:
                return row["state"]
        return "unknown"
