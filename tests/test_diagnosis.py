from workagent_rsi.diagnosis import FailureDiagnoser


def test_diagnoser_classifies_observed_failures_and_skips_success():
    results = [
        {"run_id": "r-ok", "state": "SUCCEEDED", "evidence_ref": "a" * 64},
        {"run_id": "r-format", "state": "FAILED", "failure": {"message": "format reopen failed"}, "evidence_ref": "b" * 64},
        {"run_id": "r-semantic", "state": "FAILED", "evaluation": {"critical_failures": ["required marker missing"]}, "evidence_ref": "c" * 64},
        {"run_id": "r-tool", "state": "FAILED", "failure": {"message": "tool not allowlisted"}, "evidence_ref": "d" * 64},
        {"run_id": "r-eval", "state": "FAILED", "failure": {"message": "evaluator unavailable"}, "evidence_ref": "e" * 64},
        {"run_id": "r-safety", "state": "FAILED", "failure": {"message": "unsafe task_id"}, "evidence_ref": "f" * 64},
    ]
    diagnoses = FailureDiagnoser().diagnose(results)
    assert [item.failure_class for item in diagnoses] == ["format", "semantic", "tool", "evaluator", "safety"]
    assert all(item.evidence_refs for item in diagnoses)
    assert all(item.run_ids != ["r-ok"] for item in diagnoses)


def test_diagnoser_is_deterministic():
    results = [{"run_id": "r1", "state": "FAILED", "failure": {"message": "timeout calling tool"}, "evidence_ref": "a" * 64}]
    first = FailureDiagnoser().diagnose(results)
    second = FailureDiagnoser().diagnose(results)
    assert first == second
    assert first[0].recommended_component == "tool_policy"


def test_legacy_failure_metadata_uses_logical_ids_without_exporting_private_paths():
    rows=[{'run_id':'C:/private/hidden/run','state':'FAILED','failure':{'message':'format failed'},
        'evidence_ref':'C:/private/hidden/trace.json'}]
    result=FailureDiagnoser().diagnose(rows)
    assert result and 'C:/private' not in result[0].model_dump_json()
    assert 'unknown' in result[0].causal_hypothesis.lower()
