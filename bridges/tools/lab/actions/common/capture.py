"""`app.capture_surface` — keep what is on screen, and name its shape.

Platform-neutral by nature: a screen is a screen. The function lives here once and each platform
registers it under the same id, so the Lab's bot catalogue and the front's `actionCatalog` mirror
each other without a second implementation drifting away from the first.

It calls the PRODUCTION capture (`shared/diagnostics/surface_capture`), which itself calls the
production snapshot — the same one an incident uses. Nothing here is a Lab-only path.
"""

from typing import Any, Dict

from loguru import logger

from taktik.core.shared.diagnostics.surface_capture import capture_surface as _capture_surface


def capture_surface(a, p) -> Dict[str, Any]:
    """Fingerprint the current screen and keep its files when the shape changed.

    Params (all optional): `surface` names the screen for the history, `force` writes the XML and
    the PNG even when the shape is unchanged, `outcome` records the verdict of the action that
    triggered the capture.

    Returns the record without its skeleton — the list of ids can run to a few hundred entries and
    the caller is a UI, not an archive. The full record is on disk either way.
    """
    params: Dict[str, Any] = p or {}
    device = getattr(a, 'device', None)
    raw = getattr(device, '_device', None) or device

    record = _capture_surface(
        raw,
        platform=getattr(a, 'platform', '') or params.get('platform', ''),
        surface=params.get('surface') or 'unknown',
        app_version=params.get('appVersion', ''),
        language=params.get('language', ''),
        device_model=params.get('deviceModel', ''),
        action_outcome=params.get('outcome'),
        run_id=params.get('runId'),
        force_files=bool(params.get('force')),
    )

    if record is None:
        logger.warning("app.capture_surface: screen unreadable")
        return {'captured': False}

    logger.info(
        f"app.capture_surface: {record['surface']} {record['layoutFingerprint']} "
        f"({record['density']['nodes']} nodes, changed={record['layoutChanged']})"
    )
    return {
        'captured': True,
        'layoutFingerprint': record['layoutFingerprint'],
        'layoutChanged': record['layoutChanged'],
        'density': record['density'],
        'skeletonSize': len(record['skeleton']),
        'xmlPath': record['xmlPath'],
        'screenshotPath': record['screenshotPath'],
    }


__all__ = ['capture_surface']
