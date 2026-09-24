from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .hashing import canonical_json_hash
from .rsi_contracts import SkillVersion


class SkillRegistry:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.packages = self.root / "packages"
        self.packages.mkdir(parents=True, exist_ok=True)
        self.database = self.root / "registry.db"
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS versions (
                    skill_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    parent_version TEXT,
                    content_hash TEXT NOT NULL,
                    manifest_hash TEXT NOT NULL,
                    candidate_id TEXT,
                    status TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (skill_id, version)
                );
                CREATE TABLE IF NOT EXISTS aliases (
                    skill_id TEXT PRIMARY KEY,
                    version TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS rollbacks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    skill_id TEXT NOT NULL,
                    from_version TEXT,
                    to_version TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database)

    def register(
        self,
        *,
        skill_id: str,
        version: str,
        package: dict,
        manifest: dict,
        parent_version: str | None,
        candidate_id: str | None,
        status: str,
        evidence_refs: list[str],
    ) -> SkillVersion:
        content_hash = canonical_json_hash(package)
        manifest_hash = canonical_json_hash(manifest)
        created_at = datetime.now(timezone.utc)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT parent_version, content_hash, manifest_hash, candidate_id, status, evidence_json, created_at FROM versions WHERE skill_id=? AND version=?",
                (skill_id, version),
            ).fetchone()
            if row is not None:
                if row[1] != content_hash or row[2] != manifest_hash:
                    raise ValueError("skill version is immutable")
                return self._model(skill_id, version, row)
            package_root = self.packages / content_hash
            package_root.mkdir(parents=True, exist_ok=True)
            (package_root / "skill.json").write_text(json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            (package_root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            conn.execute(
                "INSERT INTO versions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    skill_id,
                    version,
                    parent_version,
                    content_hash,
                    manifest_hash,
                    candidate_id,
                    status,
                    json.dumps(evidence_refs, sort_keys=True),
                    created_at.isoformat(),
                ),
            )
            if status == "champion":
                conn.execute(
                    "INSERT OR REPLACE INTO aliases VALUES (?, ?, ?, ?)",
                    (skill_id, version, json.dumps(evidence_refs), created_at.isoformat()),
                )
        return SkillVersion(
            skill_id=skill_id,
            version=version,
            parent_version=parent_version,
            content_hash=content_hash,
            manifest_hash=manifest_hash,
            candidate_id=candidate_id,
            status=status,
            evidence_refs=evidence_refs,
            created_at=created_at,
        )

    def get(self, skill_id: str, version: str) -> SkillVersion:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT parent_version, content_hash, manifest_hash, candidate_id, status, evidence_json, created_at FROM versions WHERE skill_id=? AND version=?",
                (skill_id, version),
            ).fetchone()
        if row is None:
            raise KeyError((skill_id, version))
        return self._model(skill_id, version, row)

    def set_champion(self, skill_id: str, version: str, evidence_refs: list[str]) -> None:
        record = self.get(skill_id, version)
        if record.status not in {"accepted", "champion", "rolled_back"}:
            raise ValueError("only accepted versions can become champion")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO aliases VALUES (?, ?, ?, ?)",
                (skill_id, version, json.dumps(evidence_refs), now),
            )

    def champion(self, skill_id: str) -> SkillVersion:
        with self._connect() as conn:
            row = conn.execute("SELECT version FROM aliases WHERE skill_id=?", (skill_id,)).fetchone()
        if row is None:
            raise KeyError(skill_id)
        return self.get(skill_id, str(row[0]))

    def lineage(self, skill_id: str, version: str) -> list[SkillVersion]:
        items: list[SkillVersion] = []
        current: str | None = version
        while current is not None:
            item = self.get(skill_id, current)
            items.append(item)
            current = item.parent_version
        return items

    def package(self, record: SkillVersion) -> dict:
        return json.loads((self.packages / record.content_hash / "skill.json").read_text(encoding="utf-8"))

    def record_rollback(self, skill_id: str, from_version: str | None, to_version: str, evidence_refs: list[str]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO rollbacks(skill_id, from_version, to_version, evidence_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (skill_id, from_version, to_version, json.dumps(evidence_refs), datetime.now(timezone.utc).isoformat()),
            )

    @staticmethod
    def _model(skill_id: str, version: str, row: tuple) -> SkillVersion:
        return SkillVersion(
            skill_id=skill_id,
            version=version,
            parent_version=row[0],
            content_hash=row[1],
            manifest_hash=row[2],
            candidate_id=row[3],
            status=row[4],
            evidence_refs=json.loads(row[5]),
            created_at=datetime.fromisoformat(row[6]),
        )


class RollbackManager:
    def __init__(self, registry: SkillRegistry) -> None:
        self.registry = registry

    def rollback(self, skill_id: str, target_version: str, evidence_refs: list[str]) -> SkillVersion:
        try:
            previous = self.registry.champion(skill_id).version
        except KeyError:
            previous = None
        target = self.registry.get(skill_id, target_version)
        self.registry.set_champion(skill_id, target_version, evidence_refs)
        self.registry.record_rollback(skill_id, previous, target_version, evidence_refs)
        return target
