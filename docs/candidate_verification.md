# Independent skill verification and deferred behavior qualification

`CandidateVerifier.verify(candidate, workspace, policy, *, skill_model,
parent_package, parent_version, edit_budget, behavior_probe=None)` owns all
candidate schema and safety validation. RSI and the `Check` facade call the
same implementation. The RSI caller supplies the actual registry parent,
version, model and budget; standalone compatibility calls may infer the known
WorkAgent/Pilot schema from an ordinary exported `skill.json`, with unbound
registry/budget metadata explicitly warned about.

The verifier checks the complete patch before applying it to a private parent
copy. Unknown fields, duplicate edits, wrong types, parent/budget mismatch,
immutable version/domain changes and non-allowlisted targets fail. WorkAgent
skills permit only `instructions`; the authored legacy pilot retains its
registered marker/sales execution fields. The resulting model is validated
strictly. Source packages and workspace files are not modified.

`VerificationPolicy.required_instruction_rules` declares trusted rules that
must remain as standalone instruction lines. The leakage critic additionally
flags protected values/targets, obvious capability additions, explicit task-ID
branches and attempts to override restrictions. These are conservative static
heuristics, not semantic proof; independent behavior checks remain necessary.

Reports separate `schema_status`, `safety_status`, `behavior_status`,
`compile_status`, `behavior_required` and `quality_verified`. A JSON/prompt-only
skill has `compile_status=not_applicable`. Candidate-authored tests are recorded
as supplementary/not_run and are never compiled or executed on the host.
The old runner injection remains accepted for source compatibility but is not
used for JSON verification.

Without a qualified behavior probe, WorkAgent candidates default to required
behavior verification and `passed=false`, while schema/safety may individually
pass. An explicit static-only policy may set `require_behavior=false`; this
still never sets `quality_verified=true`. Legacy authored pilot mechanics keep
their local static pass semantics with behavior=not_run and quality unverified.
Failures or missing required behavior never promote the champion through RSI.

## Fixed sandbox probe protocol

`FixedSandboxBehaviorProbe` accepts an explicit T04 executor, independently
authored program/taskset with expected hashes, and an output directory. It
stages only the fixed program, fixed tasks and parent/candidate JSON packages.
It checks actual Apptainer resource/runtime/cleanup traces, exact task coverage
and package/taskset hashes before admitting a result. A required task failure
or protected behavior regression blocks the candidate. Unit fixtures and
unverified probes cannot establish live quality, even if they return passed.
The program must write `outputs/behavior.json` with parent/candidate canonical
package hashes, exact taskset file hash and one row per fixed task containing
task_id, parent_passed and candidate_passed booleans.

Probe program/taskset hashes, qualification kind and sandbox policy contribute
to checkpoint identity. Verification policy changes also invalidate resume.
There is no implicit host execution or remote connection.

## Actual server acceptance

Local static checks, probe adapter/protocol and fixture tests were delivered
first. Real acceptance uses the following procedure:

1. Freeze independently reviewed fixed behavior tasks and a trusted worker
   program suitable for the real Office skill execution path. Include a
   preserved-rule/protected-regression counterexample and bind all hashes.
2. Recheck the T04 Apptainer runtime and scoped resource/cleanup capability on
   `cluster_vlab_jump`; verify any Office dependencies through the T05 boundary.
3. Run actual parent/candidate behavior probes under that boundary and preserve
   complete task coverage, hashes, policy, command, output and cleanup evidence.
4. Qualify `evidence_kind=isolated_run` only from those actual runs. Verify a bad
   candidate is blocked without changing champion, then update the T08 ledger.

The 2026-10-24 real probe passed. Codex CLI `gpt-6.1-sol` generated one frozen
Office program for each of three instruction packages. The task cases and
arithmetic oracles were authored before generation; models received the generic
task and instruction package, without those oracle cases. The independent fixed
program ran the resulting scripts only inside the frozen no-network Apptainer
worker and opened genuine XLSX artifacts. Package, generated-program, taskset,
artifact, runtime and cleanup evidence is retained.

The preserving candidate passed three tasks. The first-two-entries control
regressed on both protected cases and was rejected. An additional actual
`RSILoop.run_round` invocation reused the real frozen parent results, reran the
bad candidate behavior remotely, rejected it and preserved the registry champion
hash. This establishes verifier/registry integration on authored tasks. It is
not an end-to-end live model RSI benchmark or a general skill-quality claim.

Reproduction uses `run_t08_behavior_probe.py` with explicit frozen sandbox and
approved live-call policies, then `run_t08_rsi_probe.py --behavior-root PATH`.
The latter makes no new model calls. See `hardening_t08_candidate_validation.json`
for exact attempts, failures and portable evidence. Local fixture tests still
make no remote/model calls. The overall G1 gate remains unfinished.
