"""How long to watch a TikTok video, from what is on screen rather than from a coin flip.

Every TikTok workflow drew its dwell from `random.uniform(min_watch_time, max_watch_time)`: a
flat distribution, identical for a three-word clip and for a caption nobody could read in ten
seconds, and with no memory from one video to the next. Instagram stopped doing that months ago —
it reads the caption and multiplies by the session's attention scale — and the primitive it uses
is already shared. TikTok simply never called it.

Two things decide the time here:

- **the content**, through `content_dwell(prose_len)`: a glance, plus reading time proportional
  to the caption, plus the occasional linger;
- **the session**, through the attention scale carried by `BehaviorSessionState`: the same run
  reads faster when it is in a burst and slower when it is not, and that correlation is what a
  flat draw cannot produce.

The operator's `min_watch_time` / `max_watch_time` keep their meaning: they are the BOUNDS. The
content decides where inside them the dwell lands. Ignoring them would silently overrule a
setting the front exposes; obeying them alone is what made the behaviour flat.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from taktik.core.shared.behavior.dwell import caption_prose_text, content_dwell


def video_prose_length(video_info: Optional[Mapping[str, Any]]) -> int:
    """How much readable prose a video carries, from its description and its sound title.

    The sound line is part of what a viewer reads before deciding to stay, so it counts; the
    counters do not, because a number is taken in at a glance.

    `caption_prose_text`, not `caption_prose_chars`: the latter drops the first word, because an
    Instagram caption opens with the poster's username. A TikTok description does not, so that
    strip would silently eat a real word of every video.
    """
    if not video_info:
        return 0
    parts = (str(video_info.get("description") or ""), str(video_info.get("sound") or ""))
    return sum(len(caption_prose_text(part)) for part in parts if part)


def video_watch_seconds(
    video_info: Optional[Mapping[str, Any]],
    *,
    minimum: float,
    maximum: float,
    reading_scale: float = 1.0,
) -> float:
    """Seconds to stay on a video: content-driven, session-scaled, bounded by the config.

    `reading_scale` comes from the run's `BehaviorSessionState`; 1.0 means "no session memory",
    which is what a caller without one gets, and it still beats a flat draw because the content
    is read.
    """
    low, high = (minimum, maximum) if minimum <= maximum else (maximum, minimum)
    seconds = content_dwell(video_prose_length(video_info)) * max(0.1, float(reading_scale))
    return max(low, min(high, seconds))


__all__ = ["video_prose_length", "video_watch_seconds"]
