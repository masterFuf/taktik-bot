"""The sound of a video, and the page it opens.

TikTok has no Instagram equivalent for this. Every video carries the sound it uses, that sound has
a page, and that page lists every video made with it -- which makes a sound a targeting source in
its own right, like a hashtag but tied to a trend rather than to a word.

Measured on 46.6.3 on 2026-08-30:

    video screen   :id/pgx   content-desc "Son : Umbrella par Rihanna"
    sound page     title     content-desc "Umbrella Rihanna <bidi>3,3 M publications"
    sound page     :id/cover x13, clickable, content-desc "Vidéo" -- and nothing else

That last line is the constraint the whole design turns on: a sound-page cell says "Vidéo" and
names nobody. The person behind it is only reachable by opening the cell, reading the author off
the video, and opening THAT -- the same three-step road the comment sheet and the hashtag grid
both forced, for the same reason.

MEASURED GAP, stated rather than papered over: reaching a sound page BY NAME from the search
Sounds tab does not work here. The tab is found and tapped, and the list stays empty past twelve
seconds. So a sound is reached from a video that uses it, never from a search box.
"""

from typing import List
from dataclasses import dataclass, field

from ...locales import L


@dataclass
class VideoSoundSelectors:
    """The sound entry on a video, and the sound page it leads to."""

    #: The sound row on a video screen. `pgx` is obfuscated and will move; the description is
    #: readable and survives, which is why the language-carrying anchor comes FIRST here -- the
    #: opposite of the usual order, because `pgx` alone cannot be told from any other row.
    _sound_entry_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/pgx")]',
    ])

    @property
    def sound_entry(self) -> List[str]:
        return L("video_sound.sound_entry") + self._sound_entry_base

    @property
    def sound_page_indicator(self) -> List[str]:
        """What says we are ON a sound page rather than anywhere else.

        The post count is the only thing unique to this screen. Reading it is also how a caller
        decides whether a sound is worth harvesting at all: three posts is our own original audio,
        3.3 million is a trend.
        """
        return L("video_sound.sound_page_indicator")

    #: The Sounds tab on a search results page. Its label is a TextView, so the CLICKABLE is its
    #: ancestor -- tapping the label itself does nothing.
    sounds_tab_entry: List[str] = field(default_factory=lambda: [
        '//*[@text="Sons" or @text="Sounds"]/ancestor::*[@clickable="true"][1]',
        '//*[@text="Sons" or @text="Sounds"]',
    ])

    #: The sound rows on the search "Sounds" tab.
    #:
    #: Anchored on the create-with-this-sound button, because the rows carry NO TEXT AT ALL --
    #: measured 2026-08-30, nine rows and not one readable title among them. That is why a sound
    #: cannot be picked from this list by name: the list does not say which row is which. What it
    #: allows is opening one and READING the page that comes up, which does say.
    search_sound_rows: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Créer une publication avec ce son"]/../..',
        '//*[@content-desc="Create a post with this sound"]/../..',
    ])

    #: The sound's own name, on its page. TWO layouts, both measured: an original sound titles
    #: itself `Son original <author> <n> publications`, a music track describes itself
    #: `Contient : <title> <artist>`. Neither is optional -- a caller that asked for one sound and
    #: got another has no other way to find out.
    sound_title: List[str] = field(default_factory=lambda: [
        '//*[starts-with(@content-desc, "Contient") or starts-with(@content-desc, "Contains")]',
        '//*[contains(@resource-id, ":id/title")]',
    ])

    #: One video cell of a sound page. No language at all: the cells carry `content-desc="Vidéo"`
    #: on a French phone, and the cover id is what actually addresses them.
    sound_video_cell: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/cover")]',
    ])


VIDEO_SOUND_SELECTORS = VideoSoundSelectors()

__all__ = ["VIDEO_SOUND_SELECTORS", "VideoSoundSelectors"]
