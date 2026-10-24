# Candidate generation context and response contracts

T06 makes candidate generation depend on the actual exported parent skill.
The API and CLI providers use the same `CandidateContext` and prompt builder.
The normal RSI loop supplies the registry's canonical package hash; compatibility
calls without a registry explicitly record the identity source as `export`.
Both the canonical package hash and exact `skill.json` byte hash are recorded.

`build_candidate_context(workspace, parent_version, edit_budget, ...)` reads the
ordinary exported `skill.json`, checks the registry hash when supplied, and
checks a package's embedded version against the parent. Before transport,
`generate_with_context(context, workspace, record_root)` revalidates nested
containers and rereads the file identity. Missing or changed champion input
fails before any provider starts. Existing `generate` / `generate_with_feedback`
calls adapt to this path; they now require a real exported `skill.json`.

Candidate-visible inputs include normalized develop feedback, logical task and
requirement references, a minimal outcome/issue-count trace summary and public
lessons. Unknown feedback fields and explicitly protected split/visibility
subtrees are excluded. Full evaluator reports, filesystem paths, protected task
conclusions and inherited promotion evidence stay on the evaluation side.
Allowed develop observations are still untrusted data, not instructions.

Public history uses completed rounds' normalized develop feedback. Its saved
hash must match the checkpoint before it can be read on a later round or resume.
The current conservative lesson policy emits a fixed abstract recheck rule with
a develop source hash when prior public feedback contains defects. It does not
copy task answers, locations, raw hints or hidden rejection reasons into lessons.
The next round exports the current registry champion, including an accepted
previous round's updated package.

`max_context_bytes` defaults to 131,072 bytes (maximum configurable 1 MiB).
It bounds the serialized context data, including champion and history; fixed
prompt instructions are separate overhead. Overflow raises an explicit error
with observed and allowed sizes. Nothing is silently truncated or compressed.
Changing this limit changes the multi-round checkpoint identity.

Each provider saves `context.json` (context plus canonical hash) and
`request-redacted.json` (the shared prompt and context hash). These contain no
authorization headers or environment values. The API request record contains
the same context, and the CLI command record redacts its prompt argument.
Treat approved develop data as potentially sensitive when sharing evidence.

The local tests capture API requests with an in-process dummy transport and CLI
commands with an injected runner. Multi-round tests use authored offline
policies. These validate data flow and contract behavior; they do not call a
model, connect to the Apptainer server or establish model improvement.
