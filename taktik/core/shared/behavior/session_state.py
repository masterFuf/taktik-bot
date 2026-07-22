"""Ephemeral, per-session memory for coherent humanized behaviour.

The state deliberately lives in RAM.  It is owned by a workflow session and injected into the
action facades that need it; it is never a module singleton and never writes to the database.
This keeps parallel devices isolated while giving successive decisions enough memory to form
short, coherent bursts instead of independent coin flips.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import random
from typing import Any, Deque, Dict, Optional, Sequence

from taktik.core.shared.behavior.grid_entry import row_weights
from taktik.core.shared.telemetry import emit_step


@dataclass(frozen=True)
class _StyleSpec:
    drag_probability_delta: float
    burst_min: int
    burst_max: int
    correction_bias: float


@dataclass(frozen=True)
class _MotorSpec:
    distance: float
    velocity: float
    settle: float
    dwell: float


_STYLES = {
    # Fast run of decisive flicks.
    "brisk": _StyleSpec(-0.10, 4, 8, -0.10),
    # Neutral rhythm, close to the historical 85/15 mix.
    "steady": _StyleSpec(0.00, 3, 7, 0.00),
    # Slower, more deliberate passage with more continuous drags and framing attention.
    "deliberate": _StyleSpec(0.20, 2, 5, 0.12),
}

_CORRECTION_REACTION_S = {
    "brisk": (0.18, 0.48),
    "steady": (0.32, 0.85),
    "deliberate": (0.55, 1.20),
}

_STYLE_MOTOR = {
    "brisk": _MotorSpec(distance=0.96, velocity=1.10, settle=0.86, dwell=0.82),
    "steady": _MotorSpec(distance=1.00, velocity=1.00, settle=1.00, dwell=1.00),
    "deliberate": _MotorSpec(distance=1.04, velocity=0.90, settle=1.15, dwell=1.22),
}

# A new burst depends on the previous one. Adjacent changes remain common, but a direct jump from
# a fast run to a slow deliberate run (or the reverse) is deliberately uncommon. The profile
# weights below still decide the long-run character of the session.
_STYLE_TRANSITION_AFFINITY = {
    "brisk": (1.25, 1.00, 0.25),
    "steady": (0.85, 1.10, 0.85),
    "deliberate": (0.25, 1.00, 1.25),
}

_STYLE_ENERGY_TARGET = {
    "brisk": 0.72,
    "steady": 0.52,
    "deliberate": 0.32,
}

# In the profile-post viewer, interaction selectors can still match the outgoing post when the
# incoming header sits too low. Feed browsing has an additional metadata-reveal safety loop, so its
# generic threshold can remain more permissive; profile interactions need a lower hard boundary.
_CONTEXT_CRITICAL_FRAMING = {
    "profile_post_header": 0.30,
}

_PROFILE_STYLE_WEIGHTS = {
    # Deliberate bursts are shorter, so their selection weight is higher than their eventual
    # share of gestures. The duration-weighted natural mix stays close to the 85/15 baseline.
    "natural": (0.30, 0.45, 0.25),
    "balanced": (0.30, 0.45, 0.25),
    "careful": (0.20, 0.45, 0.35),
    "slow_reader": (0.20, 0.45, 0.35),
    "fast": (0.55, 0.35, 0.10),
    "fast_debug": (0.65, 0.30, 0.05),
    "strict_test": (0.00, 1.00, 0.00),
}


class BehaviorSessionState:
    """Mutable behaviour memory scoped to one running session.

    The public decisions are JSON-friendly dictionaries so callers can return the exact production
    choice through Cartography Lab.  A private ``random.Random`` instance makes seeded regression
    runs reproducible without resetting or contaminating Python's process-global RNG.
    """

    def __init__(
        self,
        *,
        seed: Optional[int] = None,
        strict_regression: bool = False,
        profile_id: str = "natural",
        history_limit: int = 24,
    ) -> None:
        self.seed = seed
        self.strict_regression = bool(strict_regression or profile_id == "strict_test")
        self.profile_id = profile_id if profile_id in _PROFILE_STYLE_WEIGHTS else "natural"
        self._rng = random.Random(0 if self.strict_regression and seed is None else seed)
        self._motor_signature = self._sample_motor_signature()
        self._energy = self._sample_energy()
        self._style: Optional[str] = None
        self._burst_remaining = 0
        self._gesture_index = 0
        self._framing_index = 0
        self.gesture_history: Deque[Dict[str, Any]] = deque(maxlen=max(4, history_limit))
        self.framing_history: Deque[Dict[str, Any]] = deque(maxlen=max(4, history_limit))
        self.grid_entry_history: Deque[Dict[str, Any]] = deque(
            maxlen=max(4, min(8, history_limit))
        )

    def reconfigure(
        self,
        *,
        seed: Optional[int],
        strict_regression: bool,
        profile_id: str,
    ) -> None:
        """Refresh policy metadata without erasing a session already in progress.

        ``SessionManager.update_config`` runs at workflow start and can also run mid-session.  A new
        seed is therefore adopted only before the first decision; changing config later must not
        silently wipe the short-term history that this object exists to preserve.
        """
        requested_strict = bool(strict_regression or profile_id == "strict_test")
        strict_changed = requested_strict != self.strict_regression
        clean = (
            not self.gesture_history
            and not self.framing_history
            and not self.grid_entry_history
        )
        seed_changed = seed != self.seed
        if clean and (seed_changed or strict_changed):
            self.seed = seed
            self._rng = random.Random(0 if requested_strict and seed is None else seed)
        self.strict_regression = requested_strict
        if strict_changed or (clean and seed_changed):
            self._motor_signature = self._sample_motor_signature()
            self._energy = self._sample_energy()
        if strict_changed:
            # Preserve the recorded history, but make the next decisions obey the newly selected
            # execution mode immediately. Leaving strict mode starts a fresh natural burst.
            self._style = "steady" if requested_strict else None
            self._burst_remaining = 10_000 if requested_strict else 0
        self.profile_id = profile_id if profile_id in _PROFILE_STYLE_WEIGHTS else "natural"

    def choose_scroll_mode(
        self,
        *,
        context: str,
        base_drag_probability: float = 0.15,
    ) -> Dict[str, Any]:
        """Choose flick/drag while preserving a short-lived session style."""
        previous_style = self._style
        burst_started = self._style is None or self._burst_remaining <= 0
        style_changed = self._ensure_style()
        self._advance_energy(style_changed=style_changed)
        spec = _STYLES[self._style or "steady"]
        drag_probability = min(
            0.55,
            max(
                0.02,
                float(base_drag_probability)
                + spec.drag_probability_delta
                + (0.52 - self._energy) * 0.10,
            ),
        )
        draw = self._rng.random()
        mode = "drag" if draw < drag_probability else "flick"
        motor = self.motor_modulation(context=context, emit=False)
        self._gesture_index += 1
        self._burst_remaining = max(0, self._burst_remaining - 1)
        decision = {
            "index": self._gesture_index,
            "context": context,
            "mode": mode,
            "style": self._style,
            "style_changed": style_changed,
            "burst_started": burst_started,
            "previous_style": previous_style if burst_started else None,
            "burst_remaining": self._burst_remaining,
            "drag_probability": round(drag_probability, 3),
            **motor,
        }
        self.gesture_history.append(decision)
        emit_step(
            "behavior",
            action="gesture_choice",
            target=context,
            mode=mode,
            style=self._style,
            style_changed=style_changed,
            burst_started=burst_started,
            previous_style=previous_style if burst_started else None,
            burst_remaining=self._burst_remaining,
            energy=round(self._energy, 3),
            drag_probability=round(drag_probability, 3),
            distance_scale=motor["distance_scale"],
            velocity_scale=motor["velocity_scale"],
            settle_scale=motor["settle_scale"],
            dwell_scale=motor["dwell_scale"],
        )
        return dict(decision)

    def plan_directional_gesture(self, *, context: str, gesture: str) -> Dict[str, Any]:
        """Consume one session beat for a gesture whose kind is already known.

        Carousel swipes, story-tray swipes and story advance taps do not choose between flick and
        drag, but they must still participate in the same style burst and gradual energy signal.
        """
        previous_style = self._style
        burst_started = self._style is None or self._burst_remaining <= 0
        style_changed = self._ensure_style()
        self._advance_energy(style_changed=style_changed)
        motor = self.motor_modulation(context=context, emit=False)
        self._gesture_index += 1
        self._burst_remaining = max(0, self._burst_remaining - 1)
        decision = {
            "index": self._gesture_index,
            "context": context,
            "gesture": gesture,
            "mode": gesture,
            "style": self._style,
            "style_changed": style_changed,
            "burst_started": burst_started,
            "previous_style": previous_style if burst_started else None,
            "burst_remaining": self._burst_remaining,
            "drag_probability": None,
            **motor,
        }
        self.gesture_history.append(decision)
        emit_step(
            "behavior",
            action="gesture_plan",
            target=context,
            gesture=gesture,
            style=self._style,
            style_changed=style_changed,
            burst_started=burst_started,
            previous_style=previous_style if burst_started else None,
            burst_remaining=self._burst_remaining,
            energy=decision["energy"],
            distance_scale=motor["distance_scale"],
            velocity_scale=motor["velocity_scale"],
            settle_scale=motor["settle_scale"],
            dwell_scale=motor["dwell_scale"],
        )
        return dict(decision)

    def motor_modulation(
        self, *, context: str, emit: bool = True, jitter: bool = True
    ) -> Dict[str, float]:
        """Return correlated motor scales for the current session style.

        The stable signature represents one session's reach, tempo and attention. Style then moves
        all related parameters together, while a narrow per-action jitter prevents fixed values.
        """
        self._ensure_style(allow_transition=False)
        style = _STYLE_MOTOR[self._style or "steady"]
        signature = self._motor_signature
        if self.strict_regression or not jitter:
            distance_jitter = velocity_jitter = settle_jitter = dwell_jitter = 1.0
        else:
            distance_jitter = self._rng.uniform(0.975, 1.025)
            velocity_jitter = self._rng.uniform(0.97, 1.03)
            settle_jitter = self._rng.uniform(0.94, 1.06)
            dwell_jitter = self._rng.uniform(0.94, 1.06)
        energy_delta = 0.0 if self.strict_regression else self._energy - 0.52
        values = {
            "distance_scale": round(
                signature["reach"] * style.distance * distance_jitter
                * (1.0 - 0.05 * energy_delta), 3
            ),
            "velocity_scale": round(
                signature["tempo"] * style.velocity * velocity_jitter
                * (1.0 + 0.18 * energy_delta), 3
            ),
            "settle_scale": round(
                style.settle * settle_jitter / signature["tempo"]
                * (1.0 - 0.16 * energy_delta), 3
            ),
            "dwell_scale": round(
                signature["attention"] * style.dwell * dwell_jitter
                * (1.0 - 0.22 * energy_delta), 3
            ),
            "energy": round(self._energy, 3),
        }
        if emit:
            emit_step(
                "behavior",
                action="motor_modulation",
                target=context,
                style=self._style,
                **values,
            )
        return values

    def reading_scale(self, *, context: str) -> float:
        """Return and emit the current correlated dwell multiplier."""
        values = self.motor_modulation(context=context, emit=False)
        scale = values["dwell_scale"]
        emit_step(
            "behavior",
            action="reading_scale",
            target=context,
            style=self._style,
            dwell_scale=scale,
        )
        return scale

    def choose_grid_entry_index(
        self, *, context: str, candidate_keys: Sequence[str], avoid_recent: int = 2
    ) -> int:
        """Choose a weighted grid cell while avoiding recent cells on the same profile.

        Selection does not record success: callers remember the cell only after the post viewer
        actually opens, so a failed tap never poisons the short-term memory.
        """
        keys = [str(key) for key in candidate_keys]
        if len(keys) <= 1:
            return 0
        recent = []
        for item in reversed(self.grid_entry_history):
            if item.get("context") == context:
                recent.append(item.get("key"))
                if len(recent) >= max(0, int(avoid_recent)):
                    break
        eligible = [index for index, key in enumerate(keys) if key not in recent]
        if not eligible:
            eligible = list(range(len(keys)))
        weights = row_weights(len(keys))
        return int(self._rng.choices(eligible, weights=[weights[i] for i in eligible], k=1)[0])

    def remember_grid_entry(self, *, context: str, key: str, index: int) -> None:
        """Record a successfully opened grid cell in the bounded session memory."""
        item = {"context": str(context), "key": str(key), "index": int(index)}
        self.grid_entry_history.append(item)
        emit_step(
            "behavior",
            action="grid_entry_choice",
            target=item["context"],
            key=item["key"],
            index=item["index"],
        )

    def decide_post_framing(
        self,
        *,
        land_ratio: Optional[float],
        confidence: float,
        context: str,
        good_threshold: float,
        critical_threshold: float = 0.62,
    ) -> Dict[str, Any]:
        """Decide whether an imperfect landing deserves an immediate correction.

        Small framing errors are sometimes accepted.  Larger, confidently measured errors are
        increasingly likely to be corrected, while a severely half-shown post is always repaired
        for functional safety.  Recent corrections lower the probability modestly so the engine
        does not settle into a mechanical scroll/dump/correct loop.
        """
        self._framing_index += 1
        confidence = min(1.0, max(0.0, float(confidence)))
        if land_ratio is None:
            return self._record_framing(
                context=context,
                land_ratio=None,
                confidence=confidence,
                needed=False,
                correct=False,
                probability=0.0,
                reason="unobserved",
                reaction_delay_s=0.0,
                target_ratio=None,
            )

        land_ratio = float(land_ratio)
        critical_threshold = min(
            float(critical_threshold),
            _CONTEXT_CRITICAL_FRAMING.get(context, float(critical_threshold)),
        )
        if land_ratio <= good_threshold:
            return self._record_framing(
                context=context,
                land_ratio=land_ratio,
                confidence=confidence,
                needed=False,
                correct=False,
                probability=0.0,
                reason="already_framed",
                reaction_delay_s=0.0,
                target_ratio=None,
            )

        self._ensure_style(allow_transition=False)
        if self.strict_regression:
            probability = 1.0
            correct = True
            reason = "strict_regression"
        elif land_ratio >= critical_threshold:
            probability = 1.0
            correct = True
            reason = "critical_misalignment"
        else:
            span = max(0.01, critical_threshold - good_threshold)
            severity = min(1.0, max(0.0, (land_ratio - good_threshold) / span))
            probability = 0.30 + 0.60 * severity
            probability *= 0.55 + 0.45 * confidence
            probability += _STYLES[self._style or "steady"].correction_bias

            recent_needed = [item for item in reversed(self.framing_history) if item["needed"]][:2]
            if recent_needed and recent_needed[0]["correct"]:
                probability -= 0.12
            if len(recent_needed) == 2 and all(item["correct"] for item in recent_needed):
                probability -= 0.08

            probability = min(0.97, max(0.12, probability))
            correct = self._rng.random() < probability
            reason = "selected" if correct else "deferred"

        if correct:
            if self.strict_regression:
                reaction_delay_s = 0.0
                target_ratio = min(good_threshold * 0.42, good_threshold - 0.01)
            else:
                reaction_delay_s = self._rng.uniform(
                    *_CORRECTION_REACTION_S[self._style or "steady"]
                )
                # Do not land on one exact ratio after every correction. The range stays safely
                # inside the framed zone while allowing a small under/overshoot around the old
                # fixed target (~0.05h).
                target_ratio = good_threshold * self._rng.uniform(0.28, 0.72)
        else:
            reaction_delay_s = 0.0
            target_ratio = None

        return self._record_framing(
            context=context,
            land_ratio=land_ratio,
            confidence=confidence,
            needed=True,
            correct=correct,
            probability=probability,
            reason=reason,
            reaction_delay_s=reaction_delay_s,
            target_ratio=target_ratio,
        )

    def snapshot(self, recent: int = 8) -> Dict[str, Any]:
        """Return a compact, telemetry-safe view of the current in-memory state."""
        limit = max(0, int(recent))
        recent_gestures = list(self.gesture_history)[-limit:] if limit else []
        recent_framing = list(self.framing_history)[-limit:] if limit else []
        recent_grid_entries = list(self.grid_entry_history)[-limit:] if limit else []
        return {
            "profile_id": self.profile_id,
            "strict_regression": self.strict_regression,
            "style": self._style,
            "burst_remaining": self._burst_remaining,
            "energy": round(self._energy, 3),
            "gesture_count": self._gesture_index,
            "framing_count": self._framing_index,
            "motor_signature": dict(self._motor_signature),
            "recent_gestures": [dict(item) for item in recent_gestures],
            "recent_framing": [dict(item) for item in recent_framing],
            "recent_grid_entries": [dict(item) for item in recent_grid_entries],
        }

    def _ensure_style(self, *, allow_transition: bool = True) -> bool:
        if (self._style is not None
                and (self._burst_remaining > 0 or not allow_transition)):
            return False
        previous = self._style
        if self.strict_regression:
            self._style = "steady"
            self._burst_remaining = 10_000
        else:
            names = tuple(_STYLES)
            weights = self._transition_weights(previous)
            self._style = self._rng.choices(names, weights=weights, k=1)[0]
            spec = _STYLES[self._style]
            self._burst_remaining = self._rng.randint(spec.burst_min, spec.burst_max)
        return self._style != previous

    def _sample_motor_signature(self) -> Dict[str, float]:
        if self.strict_regression:
            return {"reach": 1.0, "tempo": 1.0, "attention": 1.0}
        return {
            "reach": round(self._rng.uniform(0.96, 1.04), 3),
            "tempo": round(self._rng.uniform(0.94, 1.06), 3),
            "attention": round(self._rng.uniform(0.94, 1.08), 3),
        }

    def _sample_energy(self) -> float:
        if self.strict_regression:
            return 0.52
        return self._rng.uniform(0.40, 0.66)

    def _transition_weights(self, previous: Optional[str]) -> tuple:
        base = _PROFILE_STYLE_WEIGHTS[self.profile_id]
        affinity = _STYLE_TRANSITION_AFFINITY.get(previous, (1.0, 1.0, 1.0))
        return tuple(weight * factor for weight, factor in zip(base, affinity))

    def _advance_energy(self, *, style_changed: bool) -> None:
        """Move a hidden energy signal gradually toward the current style's target."""
        if self.strict_regression:
            self._energy = 0.52
            return
        target = _STYLE_ENERGY_TARGET[self._style or "steady"]
        attraction = 0.16 if style_changed else 0.08
        noise = self._rng.uniform(-0.018, 0.018)
        self._energy = min(
            0.82,
            max(0.20, self._energy + attraction * (target - self._energy) + noise),
        )

    def _record_framing(
        self,
        *,
        context: str,
        land_ratio: Optional[float],
        confidence: float,
        needed: bool,
        correct: bool,
        probability: float,
        reason: str,
        reaction_delay_s: float,
        target_ratio: Optional[float],
    ) -> Dict[str, Any]:
        decision = {
            "index": self._framing_index,
            "context": context,
            "style": self._style,
            "land_ratio": round(land_ratio, 3) if land_ratio is not None else None,
            "confidence": round(confidence, 3),
            "needed": bool(needed),
            "correct": bool(correct),
            "probability": round(float(probability), 3),
            "reason": reason,
            "reaction_delay_s": round(float(reaction_delay_s), 3),
            "target_ratio": round(float(target_ratio), 3) if target_ratio is not None else None,
        }
        self.framing_history.append(decision)
        emit_step(
            "behavior",
            action="framing_decision",
            target=context,
            style=self._style,
            land_ratio=decision["land_ratio"],
            confidence=decision["confidence"],
            needed=decision["needed"],
            correct=decision["correct"],
            probability=decision["probability"],
            reason=reason,
            reaction_delay_s=decision["reaction_delay_s"],
            target_ratio=decision["target_ratio"],
        )
        return dict(decision)


__all__ = ["BehaviorSessionState"]
