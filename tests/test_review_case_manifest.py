import ast
import json
from pathlib import Path


def test_independent_review_manifest_maps_all_twelve_cases_to_collected_functions():
    tests = Path(__file__).parent
    manifest = json.loads((tests / "fixtures/review_cases/manifest.json").read_text(encoding="utf-8"))
    assert {case["case_id"] for case in manifest["cases"]} == {f"R{i:02}" for i in range(1, 13)}
    assert len(manifest["cases"]) == 12
    assert len({case["test_node"] for case in manifest["cases"]}) == 12
    for case in manifest["cases"]:
        file, name = case["test_node"].split("::")
        module = ast.parse((tests.parent / file).read_text(encoding="utf-8"))
        assert any(isinstance(node, ast.FunctionDef) and node.name == name for node in module.body)
        assert case["truth_source"] and case["minimal_input"] and case["expected"]
        assert case["owner_tasks"] and case["owner_modules"]
