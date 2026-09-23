from pathlib import Path

import pytest

from workagent_rsi.path_safety import validated_task_directory


def test_validated_task_directory_returns_direct_child(tmp_path: Path):
    assert validated_task_directory(tmp_path, "p3-task-001") == tmp_path / "p3-task-001"


@pytest.mark.parametrize("task_id", ["../escape", "..\\escape", "CON", "report."])
def test_validated_task_directory_rejects_unsafe_component(tmp_path: Path, task_id: str):
    with pytest.raises(ValueError, match="unsafe task_id"):
        validated_task_directory(tmp_path, task_id)
