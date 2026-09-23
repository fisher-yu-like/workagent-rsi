from __future__ import annotations

import re
from pathlib import Path


WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "CLOCK$",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def validated_task_directory(root: str | Path, task_id: str) -> Path:
    """Return a task child directory only for a safe single path component."""
    task_id_root = task_id.split(".", 1)[0].upper()
    if (
        not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?", task_id)
        or ".." in task_id
        or task_id_root in WINDOWS_RESERVED_NAMES
    ):
        raise ValueError(f"unsafe task_id for artifact path: {task_id}")
    return Path(root) / task_id
