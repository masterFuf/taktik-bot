"""A phone that replays a real capture of a post's likers sheet, for the tests that read or walk it.

The screens are real dumps of a C57 S (Instagram 410 in English, 576x1280), anonymized: the sheet
of a post liked twice (`TWO_LIKERS`) and the sheet of a post with thousands of likes, six rows on
screen (`LONG_LIST`). A drag up moves the sheet's list by its travel when the list `moves`, and the
phone keeps the likers shown after each one; a drag down (the sheet closing) moves nothing. A tap
lands nowhere: the screen stays the sheet.
"""

from uiautomator2.xpath import XPathEntry

from unit.social_media.instagram.services.profile_posts_phone import PKG, scrolled
from taktik.core.shared.device.ui_dump import parse_ui_dump

TWO_LIKERS = "ig410_en_likers_sheet_two_likers_c57s.xml"
LONG_LIST = "ig410_en_likers_sheet_long_list_c57s.xml"
C57S_W, C57S_H = 576, 1280
ROW_NAME_ID = f"{PKG}:id/row_user_primary_name"


class LikersSheetPhone:
    """uiautomator2 behind the proxy and the facade, replaying a likers sheet."""

    wait_timeout = 0.0

    def __init__(self, screen, moves):
        self.screen = screen
        self.moves = moves
        self.offset = 0
        self.likers_after_each_drag_up = []
        self.drags = []
        self.taps = []
        self.xpath = XPathEntry(self)
        self.info = {"displayWidth": C57S_W, "displayHeight": C57S_H}

    def dump_hierarchy(self, *_a, **_k):
        return scrolled(self.screen, self.offset, holding=ROW_NAME_ID)

    def window_size(self):
        return C57S_W, C57S_H

    def app_current(self):
        return {"package": PKG}

    def swipe_points(self, points, _duration):
        (_x0, start_y), (_x1, end_y) = points[0], points[-1]
        self.drags.append((start_y, end_y))
        if end_y >= start_y:
            return  # the sheet closed by a drag down, after the reading
        if self.moves:
            self.offset += start_y - end_y
        self.likers_after_each_drag_up.append(self.likers_shown())

    def likers_shown(self):
        root = parse_ui_dump(self.dump_hierarchy())
        return sorted(n.get("text") for n in root.iter() if n.get("resource-id") == ROW_NAME_ID)

    def click(self, x, y, *_a, **_k):
        self.taps.append((x, y))

    def press(self, *_a, **_k):
        return True
