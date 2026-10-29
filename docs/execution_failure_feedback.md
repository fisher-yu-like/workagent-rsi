# Execution failures and frozen task denominators

A confirmed agent code, response or deliverable-manifest failure is an observed
task failure even when no artifact exists. Network/authentication failures,
unavailable workers, invalid inputs and unknown failures do not establish task
quality. They stop that real split, while all admitted tasks remain in its cohort.

| Field | Meaning |
|---|---|
| execution_complete | Every admitted task has a known successful or confirmed agent-failure execution outcome. |
| execution_success_rate | Successfully executed tasks divided by the full admitted task count, when execution is complete. |
| task_outcomes_complete | Every task has a confirmed agent execution failure or a complete artifact assessment. |
| task_success_rate | Accepted tasks divided by the same admitted task count; confirmed agent failures contribute zero. |
| assessment_complete | Every admitted task has actual complete artifact assessment. |
| task_denominator | Full frozen admitted count, including failed and unattempted tasks. |
| quality_denominator | Number of tasks with observed complete artifact quality. |
| quality_score | Full-cohort quality when every assessment completes, otherwise null. |

`success_rate` remains a compatible task-success alias. Valid execution failures
can produce status `completed_with_execution_failures`, with complete task
outcomes and incomplete artifact assessment. Missing artifacts do not acquire
visual/semantic zeros or full-cohort dimension averages. Every repeat and its
observed runtime are retained, including failed executions. A failed or unknown
repeat prevents a task from becoming an unqualified success. Independent model
review agreement remains a separate gate.

Providers persist typed failure origins in outcomes and provider records. The
adapter and Orchestrator preserve origin and timeout status. Missing or invalid
deliverables are agent execution failures. A changed original input is an
environment/input-snapshot problem; a changed staged copy with an unchanged
original is an agent execution failure.

Before each native Python tool execution, the trusted provider saves a bounded,
hash-bound source snapshot outside the candidate workspace. Develop diagnosis
reads that snapshot and matching tool-result stderr, rather than a rewritten
final script. Hash/path/size checks and task visibility are required. Missing
evidence leaves the cause unknown. Error messages remain untrusted observations;
absolute paths are removed from candidate-visible messages.

`build_feedback` accepts develop execution_failures alongside scored rows.
Structured mode contains typed execution facts and T19 diagnoses, with quality
null and no invented artifact issues. Score-only and brief modes retain their
restricted detail. Hidden tasks and non-develop traces cannot enter candidate
context. Environment/assessment gaps stop the real RSI attempt. Confirmed code
failures permit candidate generation despite incomplete artifact assessment.

Comparison requires the same frozen split, evaluator, admitted count and private
task IDs. Persisted row counts are checked against the cohort hash, so a version
cannot drop a difficult task. Task success uses the full cohort. Secondary paired
quality uses only identical tasks with observed quality on both sides, with its
own denominator. Missing artifacts do not count as resolved artifact issues.
An incomplete quality cohort cannot claim a global gain from the paired subset.

T20 makes task-success changes measurable and execution failures learnable. The
existing promotion gates still reject incomplete full quality evidence. A
preregistered task-success promotion policy belongs to T29; T20 does not replace
that policy or claim a live RSI improvement.

Local qualification uses genuine OOXML, authored failure traces, injected
transport failures and the actual RSILoop path with a capture-only provider.
It makes no live model, SSH or Office application calls. Exact results and source
hashes are indexed by `hardening_t20_execution_feedback.json`.
