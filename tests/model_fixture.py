"""Offline model doubles for pipeline tests,never production task graders."""

from workagent_rsi.artifact_assessment import SharedAssessment
from test_llm_task_review import Provider, judgement


class MarkerFixtureAssessment(SharedAssessment):
    def __init__(self):
        super().__init__(provider=Provider())

    def inspect(self, spec, artifacts):
        from workagent_rsi.office_observations import read_file
        import json

        if artifacts:
            text = json.dumps(read_file(next(iter(artifacts.values())), "output"))
            good = "REQUIRED" in text
            self.provider.decision = judgement(
                "PASS" if good else "FAIL", 1 if good else 0
            )
        return super().inspect(spec, artifacts)
