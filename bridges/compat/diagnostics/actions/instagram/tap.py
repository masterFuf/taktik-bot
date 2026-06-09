"""Human-tap diagnostics for the Cartography Lab.

Validates the P1 "humanise taps" primitive (`shared/behavior/tap.py` +
`shared/device/facade.py::human_tap`): a tap should land on a varied point inside the
target, never the dead centre twice. Run the same action a few times and compare the
before/after screenshots — the touch should move around within the element.
"""

from bridges.compat.diagnostics.actions.instagram import action


@action("tap.human")
def tap_human(a, p):
    """Tap a human-sampled point inside the target (Gaussian toward the centre, never the
    rim, varied finger-down time).

    params (all optional):
      - selector: an XPath; taps that element's real bounds.
      - bounds: 'left,top,right,bottom' to tap an explicit rectangle.
      - no params: a central screen region, so it works with nothing set.
    """
    bounds = None

    raw = p.get("bounds")
    if raw:
        try:
            left, top, right, bottom = (int(v.strip()) for v in str(raw).split(","))
            bounds = (left, top, right, bottom)
        except Exception:
            return {"success": False, "message": f"bounds invalides: {raw!r} (attendu 'l,t,r,b')"}

    selector = p.get("selector")
    if bounds is None and selector:
        try:
            element = a.device._device.xpath(selector).get(timeout=3.0)
            bounds = tuple(element.bounds)
        except Exception as exc:
            return {"success": False, "message": f"selecteur introuvable: {str(exc)[:120]}"}

    if bounds is None:
        width, height = a.device._device.window_size()
        bounds = (int(width * 0.30), int(height * 0.42), int(width * 0.70), int(height * 0.58))

    point = a.device.human_tap(bounds)
    if not point:
        return {"success": False, "message": f"echec tap dans {bounds}"}
    return {"success": True, "message": f"tap humain @ {point} dans bounds {bounds}"}
