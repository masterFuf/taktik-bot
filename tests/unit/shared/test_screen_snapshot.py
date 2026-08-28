"""The screen a run ended on.

Kept for EVERY finalisation now, not only for incidents: an operator asking "where did it stop?"
should get an answer rather than a motive to interpret. Two consequences the tests pin — the file
name has to carry the session id, and the folder has to have a ceiling.
"""

import os

from taktik.core.shared.diagnostics import screen_snapshot
from taktik.core.shared.diagnostics.screen_snapshot import capture_screen_snapshot


class _Device:
    """Answers like the real facade: a hierarchy string, and a PIL image on `screenshot_pil`."""

    def __init__(self, image=True):
        self._image = image

    def dump_hierarchy(self):
        return "<hierarchy><node text='Try again later'/></hierarchy>"

    def screenshot_pil(self):
        if not self._image:
            return None

        class _Img:
            def save(self, path, format=None):
                with open(path, "wb") as handle:
                    handle.write(b"\x89PNG")
        return _Img()


def test_the_capture_carries_the_session_it_belongs_to(monkeypatch, tmp_path):
    """Without the id, a capture can only be matched to a session by proximity in time — which
    breaks the moment two devices stop in the same second, and runs launch in waves of four."""
    monkeypatch.setattr(screen_snapshot, "_snapshot_dir", lambda: str(tmp_path))

    base = capture_screen_snapshot(_Device(), "action_blocked", session_id=1163)

    assert base is not None
    assert "s1163_action_blocked" in os.path.basename(base)
    assert os.path.exists(f"{base}.png"), "the image is the artefact that reads at a glance"
    assert os.path.exists(f"{base}.xml"), "the hierarchy answers why a selector missed"


def test_a_device_that_cannot_be_read_is_not_a_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(screen_snapshot, "_snapshot_dir", lambda: str(tmp_path))

    assert capture_screen_snapshot(None, "session_end") is None


def test_the_folder_has_a_ceiling(monkeypatch, tmp_path):
    """Written on every finalisation, it would otherwise pass a gigabyte within months."""
    monkeypatch.setattr(screen_snapshot, "_snapshot_dir", lambda: str(tmp_path))
    monkeypatch.setattr(screen_snapshot, "MAX_SNAPSHOT_FILES", 4)
    for index in range(6):
        (tmp_path / f"old_{index}.png").write_bytes(b"x")

    capture_screen_snapshot(_Device(), "session_end", session_id=1)

    assert len(os.listdir(tmp_path)) <= 4
