# Repository publication scope

The repository keeps the implementation and the records needed to understand its
results. A successful engineering check does not establish evaluator accuracy,
external benchmark parity or RSI improvement.

## Files kept in Git

- Source code, tests and small test manifests under `src/` and `tests/`.
- Dependency definitions, deployment scripts, skill instructions and reusable
  experiment configurations. Live-call configuration remains disabled by default.
- Maintained documentation, including the canonical hardening plan under
  `docs/superpowers/plans/`.
- Task status, provenance, hashes, approval receipts and selected experimental
  records under `project_artifacts/formal_study/`.

The selected human-review and judge records document exposed development cases.
They retain provisional labels, later adjudications, model decisions and failed
requests separately. They are not an untouched final evaluation cohort. Reviewer
identifiers in the current records are study aliases. Request-scoped approval
receipts describe past authorization; publishing them does not authorize new calls.

## Files kept locally

- `.planning/` and root-level `task_plan.md`, `findings.md` and `progress.md`.
- The original root-level execution plan and Chinese reference notes. The maintained
  project plan is already tracked under `docs/`.
- Environments, caches, build products, Office lock files and temporary test output.
- Runtime logs, generated Office files, render pages and downloaded benchmark
  inputs in the ignored artifact result directories.
- Credentials, account configuration and server images.

Ignoring a file preserves the local copy. It does not remove a file that was
already committed. Review unpublished history as well as the current working
directory before pushing.

## Review on 2026-10-26

Before the first publication of `feat/evaluation-rsi-hardening`, the review covered
51 unpublished commits, 329 changed paths and 654 unpublished blob versions.
Those blob versions contained about 8.8 MB of uncompressed content; the largest
was about 216 KB. A pattern scan found no matches for private keys, common service
tokens, JWTs or likely literal password and API-key assignments. Pattern scanning
does not prove that credentials are absent.

The review retained the implementation and selected evidence listed above.
Local scratch files and the original root reference notes were not staged.
The publication-scope document and ignore-rule update form a separate commit.
