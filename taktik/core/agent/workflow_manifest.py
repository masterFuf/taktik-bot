"""Workflow manifest access for the agent runtime kernel."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional

WorkflowManifestData = Dict[str, Dict[str, List[str]]]


@dataclass(frozen=True)
class WorkflowManifest:
    """Read-only view over `workflows.manifest.json`."""

    data: WorkflowManifestData

    def canonical_ids(self) -> Iterable[str]:
        for platform in sorted(self.data):
            families = self.data[platform]
            for family in sorted(families):
                for workflow_type in sorted(families[family]):
                    yield canonical_workflow_id(platform, family, workflow_type)

    def contains(self, workflow_id: str) -> bool:
        return workflow_id in set(self.canonical_ids())

    def workflow_types(self, platform: str, family: str) -> List[str]:
        return list(self.data.get(platform, {}).get(family, ()))


def canonical_workflow_id(platform: str, family: str, workflow_type: str) -> str:
    """Return the stable id used by AgentPlan workflow invocations."""
    return f"{platform}.{family}.{workflow_type}"


def load_workflow_manifest(path: Optional[Path] = None) -> WorkflowManifest:
    """Load the Bot workflow manifest from an explicit path or repo root."""
    manifest_path = path or _default_manifest_path()
    with manifest_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return WorkflowManifest(data=_normalize_manifest(raw))


def _default_manifest_path() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "workflows.manifest.json"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("Could not locate workflows.manifest.json")


def _normalize_manifest(raw: Mapping[str, Mapping[str, Iterable[str]]]) -> WorkflowManifestData:
    normalized: WorkflowManifestData = {}
    for platform, families in raw.items():
        normalized[str(platform)] = {}
        for family, workflow_types in families.items():
            normalized[str(platform)][str(family)] = [str(item) for item in workflow_types]
    return normalized
