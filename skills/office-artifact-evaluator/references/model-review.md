# Task-level model review

Configure either the existing Responses API transport or Codex CLI transport with an explicit model. The provider is disabled by default. API credentials belong in the configured environment variable;the CLI uses its existing login. There is no automatic backend fallback.

Use retries within the approved budget,and repeats=1 at the task-provider layer. Independent repeated task execution belongs to the experiment layer. Old per-criterion semantic/cache settings are retained in configuration for historical compatibility;the current path makes fresh task-level requests. visual_enabled controls default rendering attempts.

The input to both skills is task plus artifacts,not AcceptanceSpec. configured_assessment(config,root) returns the shared task review engine. It accepts an injected renderer,transport or runner for testing and provisioned execution.

TaskJudgement carries task_reasonableness,task_reason,status,completion,observed,evidence_ids and issues. Preserve its decision and score. Validate response syntax and references without recoding the task's acceptance conditions.

See [the current protocol](../../../docs/operations/llm-task-review.md) for the complete request and limitations.
