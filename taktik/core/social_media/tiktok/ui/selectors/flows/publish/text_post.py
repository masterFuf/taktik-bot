"""Selectors for TikTok's TEXT post, a format the bot could not reach at all.

The creation screen offers four modes -- CRÉER, PHOTO, TEXTE, LIVE -- beside the gallery upload the
existing workflow uses. This catalogue covers the TEXTE one, measured end to end on 46.6.3 on
2026-08-30 by publishing a real post:

    Créer -> TEXTE -> type into the field -> Terminé -> "Publi. dans le fil" -> published

Everything on that road is readable, which is unusual enough on this app to be worth saying: the
mode tabs carry their labels as text, the composer has a real resource-id (`hnq`) and a placeholder,
and the destination is a labelled button. No obfuscated id is load-bearing here.

Re-measured in English on 2026-08-30, same device, same build, and two things moved. The composer
placeholder is `Type something...`, not the `Say something…` a translation would suggest -- that
one is only a fallback behind the id, so it cost nothing, but it is the fourth English label this
catalogue guessed wrong. The second one did matter: the share sheet that closed the French run
never appeared, TikTok going straight to the published post instead. What holds in both languages
is the DESTINATION SHEET GOING AWAY, so that is what publication is now measured against.

The one trap, and it cost an hour: the field is a genuine `EditText` that focuses on tap, but
`set_text` fails on this device -- `NoSuchMethodException: android.hardware.input.InputManager
.getInstance`, so uia2 cannot inject keys. Typing goes through the TAKTIK keyboard, like every
other field in this codebase.
"""

from dataclasses import dataclass, field
from typing import List

from ...locales import L
from ._shared import resource_ids


@dataclass
class PublishTextPostSelectors:
    """The TEXT mode of the creation screen, and the road out of it."""

    #: The composer itself. `hnq` is a readable-enough id and the placeholder is the fallback --
    #: an EditText on this screen is the only one, so the class alone would nearly do.
    _text_field_base: List[str] = field(default_factory=lambda: resource_ids("hnq"))

    #: The destination sheet, by id rather than by label. What proves a text post left is that
    #: this sheet is GONE -- see `destination_sheet` below.
    _destination_sheet: List[str] = field(default_factory=lambda: resource_ids("tdf", "tv_quick_publish"))

    @property
    def mode_text_tab(self) -> List[str]:
        """The TEXTE tab of the creation screen. Sits beside CRÉER, PHOTO and LIVE."""
        return L("publish_text.mode_text_tab")

    @property
    def text_field(self) -> List[str]:
        return self._text_field_base + L("publish_text.text_field") + [
            "//android.widget.EditText",
        ]

    @property
    def done_button(self) -> List[str]:
        """`Terminé` / `Done` -- leaves the composer for the destination screen, not for publication.

        `tv_sure` is a named id rather than one of this app's three-letter ones, and named ids are
        the ones that tend to survive a version bump; the label follows it.
        """
        return resource_ids("tv_sure") + L("publish_text.done_button")

    @property
    def post_to_feed(self) -> List[str]:
        """`Publi. dans le fil` / `Post to feed`.

        The button carries its own label AND its own `clickable="true"`, so the ancestor form in
        the locale entry is a belt-and-braces first try. `tdf` is the id behind it.
        """
        return L("publish_text.post_to_feed") + resource_ids("tdf")

    @property
    def post_to_story(self) -> List[str]:
        """`Ta Story` / `Your Story`.

        MEASURED AND NOT EXERCISED: the label is there, and unlike the feed one it reports
        `clickable="false"` on its own node, so its real target is an ancestor -- `tdi`, the row
        that holds it. Nothing has been published through it, and it is listed so the surface is
        described rather than implied.
        """
        return L("publish_text.post_to_story") + resource_ids("tdi")

    @property
    def destination_sheet(self) -> List[str]:
        """The sheet the Done button leads to, matched by id so it holds in any language.

        This is what a publication is measured against. It answers in both directions, which is
        the whole point: it is there while the sheet is up -- a destination tap that did nothing
        leaves it there -- and gone once the post is out.
        """
        return self._destination_sheet

    @property
    def published_indicator(self) -> List[str]:
        """The share sheet TikTok SOMETIMES raises straight after publishing.

        A fast yes, never the only one. Measured in French, it came up carrying our own handle and
        `· Il y a 2 s`; measured in English on the same device and the same build, the app went
        straight to the published post instead and no sheet appeared at all. Waiting on this alone
        would have reported a failure on a post that is online -- on a publish surface, that means
        an operator re-posting content they already published.
        """
        return L("publish_text.published_indicator")


PUBLISH_TEXT_POST_SELECTORS = PublishTextPostSelectors()

__all__ = ["PUBLISH_TEXT_POST_SELECTORS", "PublishTextPostSelectors"]
