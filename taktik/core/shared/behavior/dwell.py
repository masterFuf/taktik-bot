"""Content-aware dwell model — how long a human stays on a piece of content, FROM ITS CONTENT.

Platform-agnostic (Instagram feed, TikTok caption, …): a human GLANCES at an image (~1-3s, "I like
it") but READS a caption in proportion to its real PROSE length, and once in a while lingers. The
prose length excludes hashtags / @mentions / URLs (a wall of `#tags` is not reading) so the count
reflects what is actually read. A future vision / `post_analysis` layer can bypass this with its own
relevance-based dwell. See `internal docs` (iteration #19).
"""

import re
import random

# Tunable seeds (calibrate against measured behaviour on the Lab).
GLANCE_S = (1.2, 3.5)        # look at the media (image/video) — not reading
READ_CPS = (13.0, 22.0)      # chars/second reading speed (skim-ish); sampled per item
READ_CAP_S = 16.0            # nobody fully reads a wall of text — they skim
MIN_DWELL_S = 1.0
LINGER_PROB = 0.12           # occasionally zone out / really into it
LINGER_S = (3.0, 10.0)

_URL_RE = re.compile(r"https?://\S+")
_TAG_RE = re.compile(r"[#@]\S+")
_EXPAND_LABEL_RE = re.compile(r"\b(?:plus|more|moins|less)\s*$", re.IGNORECASE)


def caption_prose_chars(text: str) -> int:
    """Length of the REAL prose in a caption: drop the leading username token, strip URLs, hashtags
    and @mentions, and the trailing expand/collapse label ('plus'/'more'/'moins'/'less'). Returns
    the remaining character count — what a human actually reads, used to size the reading dwell."""
    if not text:
        return 0
    body = text.split(" ", 1)
    body = body[1] if len(body) > 1 else ""     # everything after the username
    body = _URL_RE.sub(" ", body)
    body = _TAG_RE.sub(" ", body)
    body = _EXPAND_LABEL_RE.sub("", body.strip())
    body = re.sub(r"\s+", " ", body).strip()
    return len(body)


def content_dwell(prose_len: int) -> float:
    """Seconds a human dwells on an item given its prose length: an image glance + reading time
    (prose ÷ reading speed, capped because humans skim) + an occasional linger. No more constant,
    content-blind dwell (e.g. 14s on a plain image)."""
    glance = random.uniform(*GLANCE_S)
    reading = 0.0
    if prose_len >= 12:     # below ~12 chars there's nothing to "read"
        reading = min(prose_len / random.uniform(*READ_CPS), READ_CAP_S)
    total = glance + reading
    if random.random() < LINGER_PROB:
        total += random.uniform(*LINGER_S)
    return total
