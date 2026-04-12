"""
Workflow Watchdog — detects when the bot is stuck and attempts auto-recovery.

Runs as a daemon thread alongside the workflow. Monitors progress via
a heartbeat mechanism: every meaningful action resets the timer. If the
timer exceeds a threshold, the watchdog performs a UI dump, analyses the
current screen state, and attempts recovery actions.

Usage:
    watchdog = WorkflowWatchdog(device, ipc=ipc, stuck_timeout=90)
    watchdog.start()

    # In the workflow code, call heartbeat() on progress:
    watchdog.heartbeat("liked post @user")

    # When workflow ends:
    watchdog.stop()
"""

import re
import threading
import time
from typing import Optional, Dict, Any, List, Callable
from loguru import logger

log = logger.bind(module="workflow-watchdog")


# ──────────────────────────────────────────────────────────────
# Known overlay / popup signatures in UI XML
# ──────────────────────────────────────────────────────────────

_OVERLAY_SIGNATURES = [
    {
        "name": "comments_popup",
        "label": "Comments popup",
        "indicators": [
            'id/sticky_header_list"',
            'text="Comments"',
            'content-desc="Add a comment"',
        ],
        "min_matches": 1,
        "recovery": ["back"],
    },
    {
        "name": "follow_options_bottom_sheet",
        "label": "Follow options bottom sheet",
        "indicators": [
            'id/bottom_sheet_container"',
            'id/background_dimmer"',
        ],
        "min_matches": 2,
        "recovery": ["back", "tap_outside"],
    },
    {
        "name": "share_bottom_sheet",
        "label": "Share bottom sheet",
        "indicators": [
            'id/bottom_sheet_container"',
            'text="Share"',
        ],
        "min_matches": 2,
        "recovery": ["back"],
    },
    {
        "name": "dialog_popup",
        "label": "Dialog / alert popup",
        "indicators": [
            'resource-id="android:id/alertTitle"',
            'resource-id="android:id/button1"',
        ],
        "min_matches": 1,
        "recovery": ["back"],
    },
    {
        "name": "rate_limit_popup",
        "label": "Rate limit warning",
        "indicators": [
            'text="Try Again Later"',
            'text="Réessayer plus tard"',
            'text="Action Blocked"',
        ],
        "min_matches": 1,
        "recovery": ["ok_button", "back"],
    },
    {
        "name": "login_required",
        "label": "Login screen detected",
        "indicators": [
            'text="Log in"',
            'text="Se connecter"',
            'content-desc="Instagram from Meta"',
        ],
        "min_matches": 2,
        "recovery": [],  # Can't auto-recover from this
    },
    {
        "name": "generic_bottom_sheet",
        "label": "Bottom sheet overlay",
        "indicators": [
            'id/bottom_sheet_container"',
        ],
        "min_matches": 1,
        "recovery": ["back", "swipe_down"],
    },
]


class WorkflowWatchdog:
    """
    Daemon thread that monitors workflow progress and auto-recovers from stuck states.
    """

    def __init__(
        self,
        device,
        ipc=None,
        stuck_timeout: int = 90,
        check_interval: int = 15,
        max_recoveries: int = 5,
    ):
        """
        Args:
            device: DeviceFacade instance
            ipc: IPC instance for sending events to frontend (optional)
            stuck_timeout: Seconds without progress before triggering stuck detection
            check_interval: How often (seconds) the watchdog checks
            max_recoveries: Max number of auto-recovery attempts before giving up
        """
        self.device = device
        self.ipc = ipc
        self.stuck_timeout = stuck_timeout
        self.check_interval = check_interval
        self.max_recoveries = max_recoveries

        self._last_heartbeat = time.time()
        self._last_heartbeat_msg = "started"
        self._recovery_count = 0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Stats
        self.stats = {
            "stuck_detected": 0,
            "recoveries_attempted": 0,
            "recoveries_succeeded": 0,
            "overlays_found": [],
        }

    def heartbeat(self, message: str = "progress"):
        """Call this whenever meaningful progress happens."""
        with self._lock:
            self._last_heartbeat = time.time()
            self._last_heartbeat_msg = message

    def start(self):
        """Start the watchdog daemon thread."""
        self._running = True
        self._last_heartbeat = time.time()
        self._thread = threading.Thread(target=self._run, daemon=True, name="workflow-watchdog")
        self._thread.start()
        log.info(f"🐕 Watchdog started (timeout={self.stuck_timeout}s, interval={self.check_interval}s)")

    def stop(self):
        """Stop the watchdog."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        log.info(f"🐕 Watchdog stopped (stats: {self.stats})")

    def _run(self):
        """Main watchdog loop."""
        while self._running:
            try:
                time.sleep(self.check_interval)
                if not self._running:
                    break

                with self._lock:
                    elapsed = time.time() - self._last_heartbeat
                    last_msg = self._last_heartbeat_msg

                if elapsed < self.stuck_timeout:
                    continue

                # ── Stuck detected ──
                self.stats["stuck_detected"] += 1
                log.warning(
                    f"🐕 STUCK DETECTED: no progress for {elapsed:.0f}s "
                    f"(last: {last_msg})"
                )

                self._send_ipc("action_event", action="stuck_detected",
                               username="", success=False,
                               data={"elapsed_seconds": round(elapsed),
                                     "last_heartbeat": last_msg})

                if self._recovery_count >= self.max_recoveries:
                    log.error(f"🐕 Max recoveries ({self.max_recoveries}) reached — giving up")
                    self._send_ipc("action_event", action="watchdog_exhausted",
                                   username="", success=False,
                                   data={"recoveries": self._recovery_count})
                    continue

                # ── Perform UI dump & analysis ──
                analysis = self._analyze_current_screen()
                if analysis:
                    self._send_ipc("action_event", action="ui_analysis",
                                   username="", success=True, data=analysis)

                    # ── Attempt recovery ──
                    if analysis.get("overlay"):
                        recovered = self._attempt_recovery(analysis)
                        if recovered:
                            self.heartbeat("watchdog-recovery")

            except Exception as e:
                log.error(f"🐕 Watchdog error: {e}")

    def _analyze_current_screen(self) -> Optional[Dict[str, Any]]:
        """Dump UI hierarchy and analyze what's on screen."""
        try:
            xml = None
            if hasattr(self.device, 'get_xml_dump'):
                xml = self.device.get_xml_dump()
            elif hasattr(self.device, 'dump_hierarchy'):
                xml = self.device.dump_hierarchy()
            elif hasattr(self.device, 'device') and hasattr(self.device.device, 'dump_hierarchy'):
                xml = self.device.device.dump_hierarchy()

            if not xml:
                log.warning("🐕 Cannot get UI dump for analysis")
                return None

            result = {
                "overlay": None,
                "overlay_label": None,
                "recovery_actions": [],
                "visible_texts": [],
                "clickable_buttons": [],
                "screen_summary": "",
            }

            # ── Check for known overlays ──
            for sig in _OVERLAY_SIGNATURES:
                matches = sum(1 for ind in sig["indicators"] if ind in xml)
                if matches >= sig["min_matches"]:
                    result["overlay"] = sig["name"]
                    result["overlay_label"] = sig["label"]
                    result["recovery_actions"] = sig["recovery"]
                    self.stats["overlays_found"].append(sig["name"])
                    log.warning(f"🐕 Overlay detected: {sig['label']} ({matches}/{len(sig['indicators'])} indicators)")
                    break

            # ── Extract visible text elements for context ──
            texts = re.findall(r'text="([^"]{2,80})"', xml)
            # Deduplicate and limit
            seen = set()
            for t in texts:
                if t not in seen and len(seen) < 20:
                    seen.add(t)
            result["visible_texts"] = list(seen)

            # ── Extract clickable buttons ──
            buttons = re.findall(
                r'<[^>]*(?:Button|button)[^>]*text="([^"]+)"[^>]*clickable="true"',
                xml
            )
            buttons += re.findall(
                r'<[^>]*clickable="true"[^>]*(?:Button|button)[^>]*text="([^"]+)"',
                xml
            )
            result["clickable_buttons"] = list(set(buttons))[:10]

            # ── Build summary ──
            if result["overlay"]:
                result["screen_summary"] = f"Overlay: {result['overlay_label']}"
            else:
                # Try to identify the current page
                if 'text="Comments"' in xml or 'text="Commentaires"' in xml:
                    result["screen_summary"] = "Comments page"
                elif 'text="Followers"' in xml or 'text="Abonnés"' in xml:
                    result["screen_summary"] = "Followers list"
                elif 'text="Following"' in xml or 'text="Abonnements"' in xml:
                    result["screen_summary"] = "Following list"
                elif 'content-desc="Home"' in xml or 'content-desc="Accueil"' in xml:
                    result["screen_summary"] = "Home feed"
                else:
                    result["screen_summary"] = "Unknown page"

            log.info(f"🐕 Screen analysis: {result['screen_summary']} | "
                     f"texts={len(result['visible_texts'])} | "
                     f"buttons={result['clickable_buttons']}")

            return result

        except Exception as e:
            log.error(f"🐕 UI analysis failed: {e}")
            return None

    def _attempt_recovery(self, analysis: Dict[str, Any]) -> bool:
        """Attempt to recover from a stuck state based on analysis."""
        recovery_actions = analysis.get("recovery_actions", [])
        overlay_name = analysis.get("overlay", "unknown")

        self._recovery_count += 1
        self.stats["recoveries_attempted"] += 1

        log.info(f"🐕 Recovery attempt #{self._recovery_count} for {overlay_name}: {recovery_actions}")

        for action in recovery_actions:
            try:
                if action == "back":
                    log.info("🐕 Recovery: pressing BACK")
                    self.device.press("back")
                    time.sleep(1.5)

                elif action == "tap_outside":
                    log.info("🐕 Recovery: tapping outside overlay")
                    try:
                        info = self.device.info if hasattr(self.device, 'info') else self.device.device.info
                        w = info.get('displayWidth', 540)
                        h = info.get('displayHeight', 960)
                        # Tap upper quarter of screen (above bottom sheet)
                        self.device.click(w // 2, h // 4)
                    except Exception:
                        if hasattr(self.device, 'device'):
                            info = self.device.device.info
                            self.device.device.click(info['displayWidth'] // 2, info['displayHeight'] // 4)
                    time.sleep(1.5)

                elif action == "swipe_down":
                    log.info("🐕 Recovery: swiping bottom sheet down")
                    try:
                        info = self.device.info if hasattr(self.device, 'info') else self.device.device.info
                        w = info.get('displayWidth', 540)
                        h = info.get('displayHeight', 960)
                        sx, sy = w // 2, int(h * 0.6)
                        ex, ey = w // 2, int(h * 0.95)
                        self.device.swipe(sx, sy, ex, ey, duration=0.3)
                    except Exception:
                        if hasattr(self.device, 'device'):
                            info = self.device.device.info
                            w, h = info['displayWidth'], info['displayHeight']
                            self.device.device.swipe(w // 2, int(h * 0.6), w // 2, int(h * 0.95), 0.3)
                    time.sleep(1.5)

                elif action == "ok_button":
                    log.info("🐕 Recovery: clicking OK/dismiss button")
                    ok_found = False
                    for text in ["OK", "Ok", "Dismiss", "Fermer", "Got it"]:
                        try:
                            el = self.device.xpath(f'//*[@text="{text}" and @clickable="true"]')
                            if hasattr(el, 'exists') and el.exists:
                                el.click()
                                ok_found = True
                                break
                        except Exception:
                            continue
                    if not ok_found:
                        # Fallback to back
                        self.device.press("back")
                    time.sleep(1.5)

                # ── Verify recovery worked ──
                post_xml = None
                if hasattr(self.device, 'get_xml_dump'):
                    post_xml = self.device.get_xml_dump()
                elif hasattr(self.device, 'dump_hierarchy'):
                    post_xml = self.device.dump_hierarchy()

                if post_xml:
                    # Check if the overlay is gone
                    sig = next((s for s in _OVERLAY_SIGNATURES if s["name"] == overlay_name), None)
                    if sig:
                        matches = sum(1 for ind in sig["indicators"] if ind in post_xml)
                        if matches < sig["min_matches"]:
                            log.success(f"🐕 Recovery SUCCESS: {overlay_name} dismissed via {action}")
                            self.stats["recoveries_succeeded"] += 1
                            self._send_ipc("action_event", action="recovery_success",
                                           username="", success=True,
                                           data={"overlay": overlay_name, "method": action,
                                                  "attempt": self._recovery_count})
                            return True

                log.warning(f"🐕 Recovery action '{action}' did not dismiss overlay")

            except Exception as e:
                log.error(f"🐕 Recovery action '{action}' failed: {e}")

        log.error(f"🐕 All recovery actions failed for {overlay_name}")
        self._send_ipc("action_event", action="recovery_failed",
                       username="", success=False,
                       data={"overlay": overlay_name, "attempt": self._recovery_count})
        return False

    def _send_ipc(self, msg_type: str, **kwargs):
        """Send an IPC message if ipc is available."""
        if self.ipc:
            try:
                self.ipc.send(msg_type, **kwargs)
            except Exception:
                pass
