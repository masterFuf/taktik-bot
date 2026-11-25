"""The account's excluded terms where a gesture is decided: on a profile, and on a post before its like
or its comment.

The two lists come with the run and the run's session holds them (`SessionManager.excluded_terms`;
`taktik/core/shared/filtering/excluded_terms.py` for the rule on data). Three doors read them:

- the profile pipeline, right after the profile is read (`ProfileProcessingMixin`): a profile term in
  its handle, its name or its bio and the profile is filtered, before any AI call or gesture;
- the interaction engine (`InteractionEngineMixin`), for the callers that act on a profile without the
  pipeline (the Feed's visit of a post author): the same check, no gesture;
- the like and the comment of a post (`LikeOrchestration`, `CommentAction`): the framed post is read
  (`PostReadingMixin.read_framed_caption`: the caption expanded and read whole) and judged by
  `post_verdict`; a post left out gets neither like nor comment.

Each profile or post left out is said in the log and on the `term_exclusion` line, with its reason, the
term and where (`taktik/core/contract/shared.py`). Like a Symfony voter, stateless: it reads
what the host (the business action) holds, says yes or no, and the caller does nothing on a no. A host
without a run's session (the Lab, a test) has no terms, and nothing is read for them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple

from loguru import logger

from taktik.core.contract.shared import (
    CAPTION,
    EXCLUDED_TERM,
    POST_CAPTION_UNREAD,
    POST_EXCLUDED_TERM,
    USERNAME,
)
from taktik.core.shared.filtering.excluded_terms import ExcludedTerms, profile_term_found
from taktik.core.shared.text import term_in_handle, term_starting_a_word
from taktik.core.social_media.instagram.actions.base.ipc.emitter import IPCEmitter
from taktik.core.social_media.instagram.ui.caption_hygiene import clean_post_caption


@dataclass(frozen=True)
class PostVerdict:
    """What the excluded terms say of the framed post.

    reason    None: the post may be liked and commented; else a code of `ExcludedTermReason`
    term      the term found, as the frame declares it (None for a caption not read)
    place     where it was found (`username`: the author's handle, `caption`)
    author    the post's author as read on its header, else the caller's
    identity  the framed post the reading was made on (its header's description): the gesture that
              follows acts only on this same post; None when no post was read
    """

    reason: Optional[str] = None
    term: Optional[str] = None
    place: Optional[str] = None
    author: Optional[str] = None
    identity: Optional[str] = None

    @property
    def allowed(self) -> bool:
        return self.reason is None


def _log_of(host: Any):
    return getattr(host, "logger", None) or logger


def excluded_terms_of(host: Any) -> ExcludedTerms:
    """The run's lists, from the session of a business action; none on a host without a run's session."""
    terms = getattr(getattr(host, "session_manager", None), "excluded_terms", None)
    return terms if isinstance(terms, ExcludedTerms) else ExcludedTerms()


def excluded_profile_term(host: Any, username: str, profile_data: Optional[Mapping[str, Any]]
                          ) -> Optional[Tuple[str, str]]:
    """The profile term found in the profile read (its handle, name, bio) and where; None when none is.
    Nothing is said (`profile_left_out_for_term` says it): the AI hook asks it before it pays for a
    profile."""
    terms = excluded_terms_of(host).profile_terms
    if not terms:
        return None
    profile = dict(profile_data or {})
    if not profile.get("username"):
        profile["username"] = username
    return profile_term_found(profile, terms)


def profile_left_out_for_term(host: Any, username: str, profile_data: Optional[Mapping[str, Any]]) -> bool:
    """True, said in the log and on the `term_exclusion` line, when a profile term leaves the profile out."""
    found = excluded_profile_term(host, username, profile_data)
    if found is None:
        return False
    term, place = found
    _log_of(host).info(f"🚫 @{username} left out: excluded term \"{term}\" in its {place}")
    IPCEmitter.emit_term_exclusion(EXCLUDED_TERM, username, term, place)
    return True


def post_verdict(
    context: Optional[Mapping[str, Any]], terms: ExcludedTerms, author_hint: Optional[str] = None
) -> PostVerdict:
    """The verdict on the framed post, from its reading (`read_framed_caption`; `framed_post_context`
    when only profile terms are set). Pure: no device.

    A profile term in the author's handle leaves the post out (the author is a profile left out). With
    post terms, the caption must have been read whole, or the post is left out (`post_caption_unread`):
    no post framed, a reading that moved the post away, a caption still truncated, or no caption in the
    post's window while the post runs under the bottom of the screen (its caption may be there). An
    empty caption of a post shown whole is no caption: nothing to find in it.
    """
    author = (context or {}).get("author") or author_hint or None
    identity = (context or {}).get("header_desc") or None
    if terms.profile_terms:
        term = term_in_handle(author, terms.profile_terms)
        if term is not None:
            return PostVerdict(EXCLUDED_TERM, term, USERNAME, author, identity)
    if not terms.post_terms:
        return PostVerdict(author=author, identity=identity)
    if context is None or context.get("reframed") is False:
        return PostVerdict(POST_CAPTION_UNREAD, author=author)
    raw = context.get("caption_text") or ""
    cleaned = clean_post_caption(raw, author_hint=author)
    if cleaned.truncated or (not raw and not context.get("post_ends_on_screen")):
        return PostVerdict(POST_CAPTION_UNREAD, author=author, identity=identity)
    term = term_starting_a_word(cleaned.text, terms.post_terms)
    if term is not None:
        return PostVerdict(POST_EXCLUDED_TERM, term, CAPTION, author, identity)
    return PostVerdict(author=author, identity=identity)


def judge_post(host: Any, context: Optional[Mapping[str, Any]], terms: ExcludedTerms,
               author_hint: Optional[str] = None) -> PostVerdict:
    """The verdict on a framed post already read (`post_verdict`), a post left out said in the log and on
    the `term_exclusion` line. The AI comment hook judges its own reading of the caption with it, before
    it pays for a comment."""
    verdict = post_verdict(context, terms, author_hint)
    reason = verdict.reason
    if reason is None:
        return verdict
    who = f"@{verdict.author}" if verdict.author else "a post"
    if reason == POST_CAPTION_UNREAD:
        _log_of(host).warning(f"🚫 Post of {who} left out: its caption could not be read, and the account has post terms")
    else:
        _log_of(host).info(f"🚫 Post of {who} left out: excluded term \"{verdict.term}\" in its {verdict.place}")
    IPCEmitter.emit_term_exclusion(reason, verdict.author, verdict.term, verdict.place)
    return verdict


def check_post_terms(host: Any, author_hint: Optional[str] = None,
                     terms: Optional[ExcludedTerms] = None) -> PostVerdict:
    """Read the framed post as the run's terms (or `terms`, the Lab's) need it, and judge it.

    Nothing is read without terms. With post terms the caption is read whole
    (`read_framed_caption`, which expands it: a tap a human makes); with profile terms only, one dump of
    the framed post gives its author. A reading that fails is said, and judged as no reading."""
    terms = terms if terms is not None else excluded_terms_of(host)
    if not terms.profile_terms and not terms.post_terms:
        return PostVerdict(author=author_hint)
    context = None
    try:
        if terms.post_terms:
            context = host.scroll_actions.read_framed_caption()
        else:
            context = host.scroll_actions.framed_post_context()
    except Exception as exc:
        _log_of(host).warning(f"Framed post unreadable for the excluded terms: {exc}")
    return judge_post(host, context, terms, author_hint)


def still_the_post_checked(host: Any, verdict: PostVerdict, identity: Optional[str], what: str) -> bool:
    """The post about to get `what` is the one the terms were checked on. A verdict on no post (no terms,
    or profile terms with no post framed) binds nothing."""
    if verdict.identity is None or identity == verdict.identity:
        return True
    _log_of(host).warning(
        f"Framed post changed after its caption was read ({verdict.identity} -> {identity}): no {what}"
    )
    return False


__all__ = [
    "PostVerdict",
    "check_post_terms",
    "excluded_profile_term",
    "excluded_terms_of",
    "judge_post",
    "post_verdict",
    "profile_left_out_for_term",
    "still_the_post_checked",
]
