import json
from pathlib import Path

from workagent_rsi.data import Task
from workagent_rsi.check import Check
from workagent_rsi.harness import Harness
from workagent_rsi.learn import Learn
from workagent_rsi.rsi_contracts import EvaluationContract
from workagent_rsi.store import Store
from workagent_rsi.verifier import VerificationPolicy


def test_harness_runs_one_normal_office_round_in_one_result_folder(tmp_path: Path):
    task = Task(
        task_id="simple-word",
        domain="word",
        instruction="Create a document with SIMPLE-001",
        expected_constraints={"required_text": "SIMPLE-001"},
    )

    result = Harness(tmp_path / "results", execution_provider="local_office").run(task)

    assert result["state"] == "SUCCEEDED"
    assert result["evaluation"]["passed"] is True
    result_file = Path(result["result_path"])
    assert result_file.name == "result.json"
    assert result_file.parent.parent == tmp_path / "results"
    assert json.loads(result_file.read_text(encoding="utf-8"))["state"] == "SUCCEEDED"
    assert (result_file.parent / "trace.db").exists()
    assert (result_file.parent / "artifacts").is_dir()
    assert not (result_file.parent / ".run-data").exists()


def test_harness_accepts_a_smoke_task_with_the_same_simple_api(tmp_path: Path):
    task = Task(
        task_id="simple-smoke",
        domain="smoke",
        instruction="hello",
        expected_constraints={"required_text": "hello"},
    )

    result = Harness(tmp_path / "results").run(task)

    assert result["state"] == "SUCCEEDED"
    assert result["evaluation"]["passed"] is True


def test_short_services_keep_diagnosis_checks_and_storage_available(tmp_path: Path):
    store = Store(tmp_path / "run")
    check = Check()
    diagnoses = Learn().diagnose(
        [{"run_id": "failed-1", "state": "FAILED", "failure": {"message": "required text missing"}}]
    )

    assert store.files.root.is_dir()
    assert check.verifier is not None
    assert diagnoses[0].failure_class == "semantic"


def test_short_services_keep_candidate_checks_evaluation_and_versions(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "skill.json").write_text('{"marker_source":"task_id"}\n', encoding="utf-8")
    workspace = tmp_path / "candidate"

    learn = Learn()
    manifest = learn.export(source, workspace, ["skill.json"], {})
    assert "skill.json" in manifest.file_hashes
    assert "AGENTS.md" in manifest.file_hashes
    diagnosis = learn.diagnose(
        [{"run_id": "failed-1", "state": "FAILED", "failure": {"message": "required text missing"}}]
    )
    candidate, provider_record = learn.propose(
        workspace,
        diagnosis,
        "0.1.0",
        tmp_path / "provider",
    )
    assert candidate is not None
    assert provider_record.status == "completed"

    check = Check()
    verification = check.verify(
        candidate,
        workspace,
        VerificationPolicy(allowed_targets={"skill.json"}),
    )
    assert verification.passed is True
    task = Task(
        task_id="check-smoke",
        domain="smoke",
        instruction="hello",
        expected_constraints={"required_text": "hello"},
    )
    store = Store(tmp_path / "run")
    artifact = store.put_bytes(b"hello", "text/plain")
    report = check.evaluate(task, [artifact], "trace-1")
    assert report.passed is True
    contract = EvaluationContract(
        contract_id="test",
        dataset_hash="a" * 64,
        split_hashes={"develop": "b" * 64},
        evaluator_hash="c" * 64,
        provider_policy="deterministic",
        seeds=[1],
        repeats=1,
        timeout_seconds=60,
        thresholds={
            "develop_gain": 0.0,
            "regression_tolerance": 1.0,
            "hidden_degradation": 1.0,
            "ood_degradation": 1.0,
            "max_cost_delta": 1.0,
        },
        git_commit="test",
    )
    decision = check.promote(
        candidate.candidate_id,
        verification,
        {
            "champion_develop": 1.0,
            "candidate_develop": 1.0,
            "critical_regressions": 0,
            "regression_delta": 0.0,
            "hidden_delta": 0.0,
            "ood_delta": 0.0,
            "unsafe_actions": 0,
            "reproducible": True,
            "cost_delta": 0.0,
        },
        contract,
    )
    assert decision.decision == "accept"
    baseline = store.register(
        skill_id="office.marker",
        version="0.1.0",
        package={"marker_source": "task_id"},
        manifest={"domain": "office"},
        parent_version=None,
        candidate_id=None,
        status="champion",
        evidence_refs=["d" * 64],
    )
    accepted = store.register(
        skill_id="office.marker",
        version="0.2.0",
        package={"marker_source": "required_text"},
        manifest={"domain": "office"},
        parent_version=baseline.version,
        candidate_id=candidate.candidate_id,
        status="accepted",
        evidence_refs=["e" * 64],
    )
    store.set_champion("office.marker", accepted.version, ["f" * 64])
    assert store.champion("office.marker").version == accepted.version
    assert [item.version for item in store.lineage("office.marker", accepted.version)] == ["0.2.0", "0.1.0"]
    assert store.rollback_to("office.marker", baseline.version, ["1" * 64]).version == baseline.version


def test_harness_can_resume_a_saved_run(tmp_path: Path):
    result = Harness(tmp_path / "results").run(
        Task(
            task_id="resume-smoke",
            domain="smoke",
            instruction="hello",
            expected_constraints={"required_text": "hello"},
        )
    )

    resumed = Harness(tmp_path / "results").resume(result["result_dir"])

    assert resumed["run_id"] == result["run_id"]
    assert resumed["state"] == "SUCCEEDED"
    assert resumed["events"]
