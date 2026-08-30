"""UI selectors for the TikTok inbox (messages, notifications, requests).

Overlay model: the language-neutral selectors (resource-id, class, position) live here
as fields; the language-dependent fragments live in the locales modules and are
injected through ``L("inbox.<field>")`` according to the active locale. A
language-dependent field is therefore exposed as a property: the neutral base plus the
fragments of the active locale. NEVER hardcode a localized text in a workflow or an
action: go through these properties.

Resource-IDs (dumps device réel) :
- Inbox : ehp (add people), j6u (search), jlc (activity status), jla (RecyclerView),
  b8h (titres de section : partagé New followers / Activity / System notifications),
  t5a (item conversation), b5h (avatar), z05 (username), l35 (dernier message),
  l3a (timestamp), fa7/lnb/ydj (badge non-lu), s28 (item de notif), ln_ (sous-titre notif).
- suggested accounts and new followers: follow-back and dismiss buttons.
- new-followers page: the item, the username, the activity text
  "a commencé à te suivre"), nzy (avatar), y6h (Tout voir).
- Page Demandes de messages (dump 145940) : nmh (titre), t5a (item), z05 (username),
    the preview, the date, the badge and the filter entry.
- Demande OUVERTE (dump 152315) : c6b (Accepter), c8q (Supprimer / refuser).
"""

from typing import List
from dataclasses import dataclass, field

from ..locales import L


@dataclass
class InboxSelectors:
    """Selectors for the TikTok inbox and messages."""

    # === Header Inbox ===
    _add_people_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ehp")]',
    ])

    @property
    def add_people_button(self) -> List[str]:
        return self._add_people_button_base + L("inbox.add_people_button")

    @property
    def inbox_title(self) -> List[str]:
        # NOTE: do NOT use '//*[@text="Inbox"]' — it matches the nav tab label on all pages
        return L("inbox.inbox_title")

    _activity_status_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/jlc")]',
    ])

    @property
    def activity_status(self) -> List[str]:
        return self._activity_status_base + L("inbox.activity_status")

    _search_inbox_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/j6u")]',
    ])

    @property
    def search_inbox_button(self) -> List[str]:
        return self._search_inbox_button_base + L("inbox.search_inbox_button")

    # === Message list ===
    message_list: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/jla")]',
        '//androidx.recyclerview.widget.RecyclerView',
    ])

    # === Notification sections (shared title id, so the text is what tells them apart) ===
    section_title: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/b8h")]',
        # A2: the id above is 43.1.4 only. The section titles are a KNOWN, closed set -- the same
        # three the markers vocabularies already list -- so naming them is measurement, not
        # invention. Three hits on a real inbox on BOTH versions.
        '//android.widget.TextView[@text="Nouveaux followers" or @text="Activité" or @text="Notifications système" or @text="New followers" or @text="Activity" or @text="System notifications"]',
    ])

    # === Conversations ===
    conversation_item: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/t5a")]',
        # A2: the row is the nearest clickable ancestor of the READABLE `user_name` id. Three rows
        # on a real inbox, four on the requests page, and nothing on a screen without rows.
        '//*[contains(@resource-id, ":id/user_name")]/ancestor::*[@clickable="true"][1]',
    ])

    conversation_avatar: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/b5h")]',
        # A2: the row's picture. Two of the three rows on the captured inbox carry one; the
        # message-requests row has none, which is why this is a partial anchor and not a
        # replacement for the id above.
        '//*[contains(@resource-id, ":id/user_name")]/../..//android.widget.ImageView',
    ])

    _conversation_username_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/z05")]',
    ])

    @property
    def decline_request_confirm_button(self) -> List[str]:
        """The « Supprimer » of the confirmation TikTok raises over a declined request."""
        return L("inbox.decline_request_confirm_button")

    @property
    def people_suggestions(self) -> List[str]:
        """Marks of the follow-suggestions pane the Messages tab sometimes renders instead."""
        return L("inbox.people_suggestions_markers")

    @property
    def conversation_username(self) -> List[str]:
        return self._conversation_username_base + L("inbox.conversation_username_anchors")

    _conversation_last_message_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/l35")]',
    ])

    @property
    def conversation_last_message(self) -> List[str]:
        return self._conversation_last_message_base + L("inbox.conversation_last_message_anchors")

    _conversation_timestamp_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/l3a")]',
    ])

    @property
    def conversation_timestamp(self) -> List[str]:
        return self._conversation_timestamp_base + L("inbox.conversation_timestamp_anchors")

    unread_badge: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/fa7")]',
        '//*[contains(@resource-id, ":id/lnb")]',
        '//*[contains(@resource-id, ":id/ydj")]',
    ])

    # === Stories row ===
    stories_row: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/tsb")]',
    ])

    story_username: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/tsi")]',
        '//*[contains(@resource-id, ":id/jmw")]',
    ])

    # === Notification sections (items) ===
    #: Rows offering the one-tap wave. TikTok writes the person's name into the line itself --
    #: `Dis bonjour à Enzo Resell` -- which makes the line both the marker and the label.
    #: Both languages in one expression, as everywhere on this surface.
    #:
    #: FRENCH MEASURED, ENGLISH NOT. `Dis bonjour à ` was read off a real inbox on 2026-08-30 and
    #: the wave was sent through it. `Say hi to ` is written from the structure: by the time the
    #: app was switched to English both candidates had been used up -- the rows read `Sent 2m ago`
    #: -- so there was nothing left to match. It needs one row to confirm, and until then a
    #: mismatch would look like "this account has nobody to greet".
    say_hello_rows: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Dis bonjour à ") or contains(@text, "Say hi to ")]',
    ])

    notification_item: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/s28")]',
        # A2: the section row is the title's nearest clickable ancestor.
        '//android.widget.TextView[@text="Nouveaux followers" or @text="Activité" or @text="Notifications système" or @text="New followers" or @text="Activity" or @text="System notifications"]/ancestor::*[@clickable="true"][1]',
    ])

    notification_subtitle: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ln_")]',
        # A2: the section's preview line, reached from its title and excluding the timestamp
        # (which carries the middle dot). Three hits on a real inbox on BOTH versions.
        '//android.widget.TextView[@text="Nouveaux followers" or @text="Activité" or @text="Notifications système" or @text="New followers" or @text="Activity" or @text="System notifications"]/ancestor::*[@clickable="true"][1]//android.widget.TextView[not(@text="Nouveaux followers" or @text="Activité" or @text="Notifications système" or @text="New followers" or @text="Activity" or @text="System notifications")][not(contains(@text, "·"))]',
    ])

    # === Group chat indicators ===
    group_member_count: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ujj")]',
    ])

    # === Follow back (suggested accounts and new followers) ===
    _follow_back_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/rdh")]',
    ])

    # === Page Nouveaux followers (dédiée) ===
    new_followers_page_item: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/o0v")]',
        # A2: the row is the avatar's great-grandparent. Three rows on the captured page.
        '//*[@content-desc="Photo de profil" or @content-desc="Profile photo"]/../../..',
    ])
    new_followers_page_username: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/o0f")]',
        # A2: the username is a BUTTON carrying the handle, not a TextView -- read off the screen.
        '//*[@content-desc="Photo de profil" or @content-desc="Profile photo"]/../../..//android.widget.Button[string-length(@text)>0]',
    ])
    new_followers_page_activity: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/nzo")]',
        # A2: the only TextView with text in a row ("s'est abonne(e) a ton compte").
        '//*[@content-desc="Photo de profil" or @content-desc="Profile photo"]/../../..//android.widget.TextView[string-length(@text)>0]',
    ])
    new_followers_page_avatar: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/nzy")]',
        # A2, measured on the real page (46.6.3, 2026-08-29). All four fields held a single
        # 43.1.4 id, so `_is_on_new_followers_page` found nothing, `get_new_followers`
        # returned an empty list and the new_followers workflow reported zero on that
        # version. The avatar carries a content-desc, which is what the row hangs off.
        '//*[@content-desc="Photo de profil" or @content-desc="Profile photo"]',
    ])
    _see_all_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/y6h")]',
    ])

    # === Message-requests page (dedicated) — list ===
    message_request_item: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/t5a")]',
        # A2: same shape as a conversation row -- the requests page reuses it.
        '//*[contains(@resource-id, ":id/user_name")]/ancestor::*[@clickable="true"][1]',
    ])
    _message_request_username_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/z05")]',
    ])

    @property
    def message_request_username(self) -> List[str]:
        return self._message_request_username_base + L("inbox.conversation_username_anchors")
    _message_request_preview_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/l35")]',
    ])

    @property
    def message_request_preview(self) -> List[str]:
        return self._message_request_preview_base + L("inbox.conversation_last_message_anchors")
    _message_request_timestamp_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/l3a")]',
    ])

    @property
    def message_request_timestamp(self) -> List[str]:
        return self._message_request_timestamp_base + L("inbox.conversation_timestamp_anchors")
    message_request_unread_badge: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ydj")]',
    ])
    _message_requests_page_title_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/nmh")]',
    ])

    # === Demande de messages OUVERTE : accepter / refuser ===
    _accept_request_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/c6b")]',
    ])
    _decline_request_button_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/c8q")]',
    ])

    # ------------------------------------------------------------------
    # Language-aware properties: the neutral base plus the localized fragments
    # ------------------------------------------------------------------

    @property
    def new_followers_section(self) -> List[str]:
        return L("inbox.new_followers_section")

    @property
    def activity_section(self) -> List[str]:
        return L("inbox.activity_section")

    @property
    def system_notifications_section(self) -> List[str]:
        return L("inbox.system_notifications_section")

    @property
    def message_requests_section(self) -> List[str]:
        return L("inbox.message_requests_section")

    @property
    def suggested_accounts_section(self) -> List[str]:
        return L("inbox.suggested_accounts_section")

    @property
    def seen_marker(self) -> List[str]:
        return L("inbox.seen_marker")

    @property
    def follow_back_button(self) -> List[str]:
        return self._follow_back_button_base + L("inbox.follow_back_button")

    @property
    def see_all_button(self) -> List[str]:
        return self._see_all_base + L("inbox.see_all_button")

    @property
    def message_requests_page_title(self) -> List[str]:
        return (self._message_requests_page_title_base
                + L("inbox.message_requests_page_title")
                + L("inbox.message_requests_page_title_anchors"))

    @property
    def accept_request_button(self) -> List[str]:
        return self._accept_request_button_base + L("inbox.accept_request_button")

    @property
    def decline_request_button(self) -> List[str]:
        return self._decline_request_button_base + L("inbox.decline_request_button")

    def section_title_by_text(self, title: str) -> str:
        """Build the notification section title selector for a visible title.

        Prefer the language-aware properties; this helper stays
        for a title already resolved in the right language.
        """
        return f'{self.section_title[0]}[@text="{title}"]'

    @property
    def we_sent_last_markers(self) -> List[str]:
        """Preview prefixes telling that WE spoke last, so the conversation
        considérée comme répondue de notre côté (détection « non-répondu », phase 2).

        Deliberately a union of every language — being a property, it is not filtered — so it
        holds whatever language was detected. Captured on device.
        """
        return ['Envoyé', 'Sent', 'Vu', 'Seen']

    @property
    def activity_title_markers(self) -> List[str]:
        """Lowercase substrings of the activity section title, across languages."""
        return ['activité', 'activity']

    @property
    def system_title_markers(self) -> List[str]:
        """Lowercase substrings of the system-notifications title, across languages."""
        return ['système', 'system']

    @property
    def new_followers_title_markers(self) -> List[str]:
        """Lowercase substrings of the new-followers title, across languages — excluded from
        phase 4 (a sa propre phase 1)."""
        return ['nouveaux followers', 'nouveaux abonnés', 'new followers']

    @property
    def message_requests_row_markers(self) -> List[str]:
        """Lowercase substrings identifying the message-requests row in the conversation
        list, which reuses the conversation item and must be excluded from them.
        phase 3). Capturé : z05="Demandes de messages" / l35="Tu as reçu N demandes"."""
        return ['demande', 'request']

    def conversation_username_by_text(self, name: str) -> str:
        """Build the conversation username selector for an exact visible name."""
        return f'{self.conversation_username[0]}[@text="{name}"]'

    def new_followers_username_by_text(self, name: str) -> str:
        """Build the new-follower username selector for a visible name (page dédiée).

        Containment rather than equality, because usernames are wrapped in invisible bidi
        (LRM/FSI/PDI : ‎⁨…⁩) — un match exact échouerait ; `name` doit être
        marks; the name passed in is cleaned of them beforehand.
        """
        return f'//*[contains(@resource-id, ":id/o0f")][contains(@text, "{name}")]'

    def new_follower_row_for_name(self, name: str) -> List[str]:
        """The tappable row of ONE new follower, addressed by the name the page shows.

        Two things this page decides, both measured on 46.6.3 on 2026-08-30.

        It shows a DISPLAY NAME, never a handle: the row's only name node reads
        `"Allocin(gl)és"`, which is @allocingles' display name with its emoji eaten by the XML
        dump. There is no handle anywhere on the page. So a welcome pass cannot search its way to
        the profile — searching a display name lands on someone else or nowhere — and the only
        route is to OPEN the row and read the handle on the profile it opens. That is why this
        builder exists at all: the pass used to hand the display name to
        `navigate_to_user_profile`, and reported `profile_unreachable` for every follower it had
        just listed.

        And the name is wrapped in directional isolates, exactly like the search results:
        `U+200E U+2068 <name> U+2069`. Containing `⁨name⁩` therefore means "this row's name is
        exactly this", because anything longer puts a character where the closing isolate has to
        be — the same anchor that stopped the search opening `@lena_situations1` for
        `@lena_situations`.
        """
        escaped = str(name or "").replace('"', "")
        isolated = f"⁨{escaped}⁩"
        return [
            f'//*[contains(@resource-id, ":id/q08")][contains(@text, "{isolated}")]',
            f'//*[contains(@resource-id, ":id/o0f")][contains(@text, "{isolated}")]',
            f'//android.widget.Button[contains(@text, "{isolated}")]',
            # Last resort: the name node may not be the tappable one on a version we have not
            # measured, so climb to whatever is.
            f'//*[contains(@text, "{isolated}")]/ancestor::*[@clickable="true"][1]',
        ]

    def message_request_by_username(self, name: str) -> List[str]:
        """Selectors for the message-request row of a visible username, richest first.

        Containment, because the username is wrapped in invisible bidi marks (see
        DMActions._clean_username) ; on remonte à l'item t5a cliquable contenant ce username.
        """
        return [
            '//*[contains(@resource-id, ":id/t5a")]'
            f'[.//*[contains(@resource-id, ":id/z05")][contains(@text, "{name}")]]',
            # Both ids above are dead on 46.6.3, so the row could not be opened there at all.
            # Structural fallback: the clickable ancestor of the row that names this person.
            # `user_name` is a readable id, which is what makes it addressable across versions.
            '//*[@clickable="true"]'
            f'[.//*[contains(@resource-id, ":id/user_name")][contains(@text, "{name}")]]',
        ]

    def follow_back_for_username(self, name: str) -> List[str]:
        """Build the 'Suivre en retour' button scoped to the new-follower item of `name`.

        Dynamic selector built from the centralized resource-ids: the follow-back button
        of the item whose username contains `name`. Containment, because the node text is
        wrapped in invisible bidi marks and the name is cleaned beforehand. This is what stops
        the tap from landing on another follower's button.

        WHEN THERE IS NO BUTTON AT ALL, which is most of the time. Measured on 2026-08-30: a
        new-follower row shows a single button on its right, and once a CONVERSATION exists with
        that person it reads `Message` rather than a follow-back. Unfollowing them does not bring
        the follow-back back -- verified: @allocingles was unfollowed, confirmed unfollowed on
        their profile, and their row still showed `Message`.

        So `can_follow_back=False` on a row we do not follow is not a detection fault; there is
        genuinely nothing to tap. What could not be separated from that one account is whether the
        trigger is the conversation or something else, since every follower on it now has a
        thread. Stated rather than guessed.
        """
        return [
            '//*[contains(@resource-id, ":id/o0v")]'
            f'[.//*[contains(@resource-id, ":id/o0f")][contains(@text, "{name}")]]'
            '//*[contains(@resource-id, ":id/rdh")]',
            # A2. The three ids above are 43.1.4 only, so on 46.6.3 this resolved nothing:
            # `can_follow_back` came back False for every follower and `follow_back` could never
            # find its button -- the follow-back mode was dead on that version, silently.
            #
            # The row is the nearest clickable ancestor of the username BUTTON (the handle is a
            # button here, not a text view). Inside it, the follow affordance is matched by its
            # LABEL and nothing else: measured on device, the very same node carries three
            # states in turn -- "Suivre en retour" when you may follow, "Envoie un message" once
            # you do, "Demande" when the account is private and a request went out. A
            # label-free "the row's other button" anchor was tried first and matched all three,
            # so `can_follow_back` said yes to followers already followed. The state IS the
            # label; the labels come from `follow_back_button`, not respelled here.
            *[
                f'//android.widget.Button[contains(@text, "{name}")]'
                '/ancestor::*[@clickable="true"][1]' + selector
                for selector in self.follow_back_button
            ],
        ]


    def say_hello_button_for_name(self, shown_name: str) -> List[str]:
        """The wave button of ONE named row, and nobody else's.

        Scoped from the row's own text up four levels to the row container -- measured
        2026-08-30, that is exactly where the text and the button meet. Below four the button is
        outside the subtree; above it, the whole list is, and the tap would greet whoever the
        first row happens to be.

        The caller takes the LAST match: the scoped subtree also holds the avatar and the row
        itself, and the button is the deepest of the three. The obfuscated id is listed first so
        the precise form wins where it exists, and the structural one carries builds where it
        does not.

        The name is a DISPLAY NAME, which is what this row shows and all it shows.
        """
        safe = (shown_name or "").replace('"', "")
        if not safe:
            return []
        row = (
            f'//*[contains(@text, "Dis bonjour à {safe}") '
            f'or contains(@text, "Say hi to {safe}")]/ancestor::*[4]'
        )
        return [
            f'{row}//*[contains(@resource-id, ":id/hhq")]',
            f'{row}//*[@clickable="true"]',
        ]

INBOX_SELECTORS = InboxSelectors()
