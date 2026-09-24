from pathlib import Path

import pytest

from workagent_rsi.registry import RollbackManager, SkillRegistry


def test_registry_versions_are_immutable_and_alias_rolls_back(tmp_path: Path):
    registry = SkillRegistry(tmp_path / "registry")
    baseline = registry.register(
        skill_id="office.marker",
        version="0.1.0",
        package={"marker_source": "task_id"},
        manifest={"domain": "office"},
        parent_version=None,
        candidate_id=None,
        status="champion",
        evidence_refs=["a" * 64],
    )
    candidate = registry.register(
        skill_id="office.marker",
        version="0.2.0",
        package={"marker_source": "required_text"},
        manifest={"domain": "office"},
        parent_version="0.1.0",
        candidate_id="c1",
        status="accepted",
        evidence_refs=["b" * 64],
    )
    registry.set_champion("office.marker", "0.2.0", ["c" * 64])
    assert registry.champion("office.marker").version == "0.2.0"
    assert [item.version for item in registry.lineage("office.marker", "0.2.0")] == ["0.2.0", "0.1.0"]

    RollbackManager(registry).rollback("office.marker", "0.1.0", ["d" * 64])
    assert registry.champion("office.marker").version == baseline.version
    assert candidate.content_hash != baseline.content_hash

    with pytest.raises(ValueError, match="immutable"):
        registry.register(
            skill_id="office.marker",
            version="0.2.0",
            package={"marker_source": "other"},
            manifest={"domain": "office"},
            parent_version="0.1.0",
            candidate_id="c2",
            status="accepted",
            evidence_refs=["e" * 64],
        )
