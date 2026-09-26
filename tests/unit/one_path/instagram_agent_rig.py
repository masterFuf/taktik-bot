"""A recording phone for the Taktik Agent one-path tests.

The same Agent config goes through the desktop bridge (`taktik_agent_bridge <config.json>`) and
through the CLI (`taktik agent run`, `taktik workflows run instagram.engagement.taktik_agent`). The
device side is the cold DM rig's (connection, app restart, selector overrides); the Agent workflow
itself is a recorder: what matters here is how each path prepares the phone and what it hands the
workflow. Nothing here reaches adb, the network, the AI or the database.
"""
from __future__ import annotations

import io
import json
import sys

from instagram_cold_dm_rig import DEVICE_ID, INSTAGRAM, InstagramColdDmRig

CLONE = "com.instagram.android.clone"


def agent_config(**overrides) -> dict:
    """What the Agent page sends (Electron adds the OpenRouter key)."""
    config = {"deviceId": DEVICE_ID, "max_likes": 5, "max_follows": 0, "session_duration_min": 10,
              "language": "fr", "openrouter_api_key": "sk-or-v1-" + "a" * 48}
    config.update(overrides)
    return config


class InstagramAgentRig(InstagramColdDmRig):
    def __init__(self, monkeypatch, tmp_path):
        self.workflows: list[dict] = []
        self.run_result = {"success": True, "stats": {"likes": 0}}
        super().__init__(monkeypatch, tmp_path)
        self._install_agent()

    def _install_agent(self) -> None:
        rig = self
        mp = self.monkeypatch

        class RecordingAgent:
            def __init__(self, device_manager=None, config=None, ipc=None, ai_service_factory=None, **kwargs):
                if device_manager is None and kwargs.get("device_manager") is None and config is None:
                    raise TypeError("no device manager")
                rig.calls.append("agent_workflow")
                rig.workflows.append({
                    "config": dict(config or {}),
                    "device_is_phone": _unwrap(getattr(device_manager, "device", None)) is rig.phone,
                    "ipc": ipc is not None,
                    "ai_factory": ai_service_factory is not None,
                })
                self.stats = {"likes": 0}

            def run(self):
                rig.calls.append("agent_run")
                return dict(rig.run_result)

            def stop(self):
                rig.calls.append("agent_stop")

        mp.setattr("taktik.core.agent.scenarios.instagram_feed_autopilot.TaktikAgentWorkflow", RecordingAgent)
        mp.setattr("taktik.core.database.configure_db_service", lambda *a, **k: rig.calls.append("configure_db"))
        for module in ("bridges.instagram.agent.runtime.session",):
            try:
                mp.setattr(f"{module}.configure_db_service", lambda *a, **k: rig.calls.append("configure_db"))
            except (ImportError, AttributeError):
                pass
        mp.setattr("bridges.instagram.agent.runtime.bridge.start_agent_stop_listener",
                   lambda: rig.calls.append("stop_listener"))

    # ------------------------------------------------------------------ paths

    def run_agent_bridge(self, config, argv: list[str] | None = None) -> int:
        """The desktop path: `taktik_agent_bridge <config.json>`, to its exit code."""
        if argv is None:
            config_path = self.tmp_path / "agent_config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            argv = ["taktik_agent_bridge", str(config_path)]
        self.monkeypatch.setattr(sys, "argv", argv)

        from bridges.instagram.agent import taktik_agent

        out = io.StringIO()
        self.monkeypatch.setattr(sys, "stdout", out)
        code = 0
        try:
            taktik_agent.main()
        except SystemExit as exit_info:
            code = exit_info.code if isinstance(exit_info.code, int) else (0 if exit_info.code is None else 1)
        finally:
            self.monkeypatch.setattr(sys, "stdout", sys.__stdout__)
        for line in out.getvalue().splitlines():
            line = line.strip()
            if line:
                try:
                    self.stdout_lines.append(json.loads(line))
                except json.JSONDecodeError:
                    self.stdout_lines.append(line)
        return code

    def run_agent_cli(self, params: list[str], env: dict | None = None):
        """The standalone path: `taktik agent run --device <serial> --param k=v ...`."""
        from click.testing import CliRunner

        from taktik.cli.commands import agent_cmds

        rig = self

        class _Manager:
            def __init__(self, *a, **k):
                self.device = rig.phone
                self.device_id = DEVICE_ID

            @staticmethod
            def list_devices():
                return [{"id": DEVICE_ID, "status": "device"}]

            def connect(self, device_id=None):
                return True

            def __getattr__(self, name):
                return getattr(rig.device_manager, name)

        class _Instagram:
            """The hot launch the CLI used to do (`InstagramManager`), recorded."""

            def __init__(self, *a, **k):
                pass

            def is_installed(self):
                return True

            def launch(self, *a, **k):
                rig.calls.append(f"hot_launch {INSTAGRAM}")
                return True

        self.monkeypatch.setattr("taktik.core.shared.device.manager.DeviceManager", _Manager)
        self.monkeypatch.setattr("taktik.core.social_media.instagram.core.manager.InstagramManager", _Instagram)
        args = ["run", "--device", DEVICE_ID]
        for param in params:
            args += ["--param", param]
        return CliRunner().invoke(agent_cmds.agent, args, env=env)

    def reset(self) -> None:
        super().reset()
        self.workflows.clear()


def _unwrap(device):
    """The phone under the facade and the clone-aware proxy, whatever wraps it."""
    for _ in range(4):
        inner = getattr(device, "device", None) or getattr(device, "_device", None)
        if inner is None or inner is device:
            break
        device = inner
    return device


__all__ = ["CLONE", "DEVICE_ID", "INSTAGRAM", "InstagramAgentRig", "agent_config"]
