from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from .contracts import ArtifactRef


class ArtifactStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put_bytes(self, content: bytes, media_type: str) -> ArtifactRef:
        digest = hashlib.sha256(content).hexdigest()
        path = self.root / digest
        if not path.exists():
            path.write_bytes(content)
        return ArtifactRef(
            artifact_id=digest,
            path=str(path),
            sha256=digest,
            media_type=media_type,
            size_bytes=len(content),
        )

    def put_file(self, source: str | Path, media_type: str) -> ArtifactRef:
        return self.put_bytes(Path(source).read_bytes(), media_type)


class TraceStore:
    def __init__(self, database: str | Path) -> None:
        self.database = str(database)
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database)

    def create_run(self, run_id: str, task_id: str) -> None:
        with self._connect() as conn:
            conn.execute("INSERT INTO runs(run_id, task_id, state) VALUES (?, ?, ?)", (run_id, task_id, "VALIDATING"))

    def set_state(self, run_id: str, state: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE runs SET state = ? WHERE run_id = ?", (state, run_id))

    def get_state(self, run_id: str) -> str:
        with self._connect() as conn:
            row = conn.execute("SELECT state FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return str(row[0])

    def append_event(self, run_id: str, kind: str, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute("INSERT INTO events(run_id, kind, payload) VALUES (?, ?, ?)", (run_id, kind, json.dumps(payload, sort_keys=True)))

    def events(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT kind, payload, created_at FROM events WHERE run_id = ? ORDER BY id", (run_id,)).fetchall()
        return [{"kind": kind, "payload": json.loads(payload), "created_at": created_at} for kind, payload, created_at in rows]
