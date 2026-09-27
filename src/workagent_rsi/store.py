"""One simple home for files, run logs and skill versions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .contracts import ArtifactRef
from .registry import RollbackManager, SkillRegistry
from .rsi_contracts import SkillVersion
from .storage import ArtifactStore, TraceStore


class Store:
    """Keep every output for one run below one directory."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.files = ArtifactStore(self.root / "artifacts")
        self.logs = TraceStore(self.root / "trace.db")
        self.skills = SkillRegistry(self.root / "skills")
        self.rollback = RollbackManager(self.skills)
        self.artifacts = self.files
        self.trace = self.logs
        self.versions = self.skills

    def put_bytes(self, content: bytes, media_type: str) -> ArtifactRef:
        return self.files.put_bytes(content, media_type)

    def put_file(self, source: str | Path, media_type: str) -> ArtifactRef:
        return self.files.put_file(source, media_type)

    def events(self, run_id: str) -> list[dict[str, Any]]:
        return self.logs.events(run_id)

    def state(self, run_id: str) -> str:
        return self.logs.get_state(run_id)

    def register(self, **kwargs: Any) -> SkillVersion:
        return self.skills.register(**kwargs)

    def get(self, skill_id: str, version: str) -> SkillVersion:
        return self.skills.get(skill_id, version)

    def package(self, version: SkillVersion) -> dict:
        return self.skills.package(version)

    def champion(self, skill_id: str) -> SkillVersion:
        return self.skills.champion(skill_id)

    def lineage(self, skill_id: str, version: str) -> list[SkillVersion]:
        return self.skills.lineage(skill_id, version)

    def set_champion(self, skill_id: str, version: str, evidence_refs: list[str]) -> None:
        self.skills.set_champion(skill_id, version, evidence_refs)

    def rollback_to(self, skill_id: str, version: str, evidence_refs: list[str]) -> SkillVersion:
        return self.rollback.rollback(skill_id, version, evidence_refs)


# Short names for callers that only need one store service.
Files = ArtifactStore
Logs = TraceStore
Skills = SkillRegistry

__all__ = ["Files", "Logs", "RollbackManager", "Skills", "Store"]
