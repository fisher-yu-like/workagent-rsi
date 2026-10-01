# Semantic and visual model review

Two transports share fixed prompts, JSON schemas and evidence validation:

- `codex-cli`: locally installed and authenticated Codex, explicit model, noninteractive `exec`; no separate API key. This uses the account's online service, not an offline model.
- `api`: OpenAI Responses protocol at a configurable base URL. The selected service/model must support `text.format` JSON Schema and, for visual checks, `input_image`. This is not a generic adapter for every vendor's API.
- `disabled`: no model calls. Applicable semantic/visual criteria remain `UNAVAILABLE`.

## Configuration and invocation

Save a trusted configuration outside candidate-editable files. API keys belong only in the named environment variable and are never written to model evidence.

```json
{
  "provider": "codex-cli",
  "model": "gpt-6-astra",
  "timeout_seconds": 120,
  "retries": 1,
  "repeats": 1,
  "disagreement_tolerance": 0.25,
  "max_text_chars": 60000,
  "max_text_items": 2000,
  "max_images": 8,
  "cache_enabled": true,
  "semantic_enabled": true,
  "visual_enabled": true
}
```

The model above matches the development machine; set an explicit model supported by your account. To use the API, change `provider` to `api`, set the API-supported `model`, and optionally set `api_base_url` (default `https://api.openai.com/v1`) and `api_key_env` (default `OPENAI_API_KEY`). The endpoint is `<api_base_url>/responses`. Missing credentials never cause an automatic fallback to another backend.

```powershell
.venv\Scripts\python.exe skills/office-artifact-evaluator/scripts/evaluate.py request.json --output project_artifacts/results/review-001 --model-config config.json
.venv\Scripts\python.exe skills/office-artifact-verifier/scripts/verify.py request.json --output project_artifacts/results/review-002 --model-config config.json
```

For one shared invocation use the Python factory:

```python
from workagent_rsi.model_judgement import configured_assessment
from workagent_rsi.check import Check
engine = configured_assessment(config, "project_artifacts/results/model-evidence")
score, issues = Check(artifact_assessment=engine).assess_artifact(spec, artifacts)
# FrozenEvaluator(evaluator_hash, assessment=engine) supports the same channels.
# Freeze engine.identity() and AcceptanceSpec fingerprints into EvaluationContract.
```

The CLI saves model evidence inside the output directory. For cross-run caching, programmatic callers can supply a stable evidence root. Neither CLI backend selection nor provider creation automatically adds semantic/visual requirements to an existing task. Specify them in the frozen AcceptanceSpec; in RSI place that spec in `TaskSpec.expected_constraints.acceptance_spec`.

## Requirements and scoring

```json
{
  "requirement_id": "content-quality",
  "description": "A clear, evidence-grounded sales conclusion",
  "check": "semantic",
  "location": {"artifact": "output"},
  "expected": "East 15, West 10, total 25; a single period cannot establish growth.",
  "options": {
    "rubric": "Full credit: correct interpretation, clear labels and no unsupported causal or growth claims. Deduct for ambiguity, contradictions or unsupported inference."
  },
  "dimension": "content",
  "weight": 1,
  "evidence_source": "Frozen source facts and extracted submission text"
}
```

Use `check: visual` for appearance and `options.pages: [1, 2]` to select actual rendered pages. Excel/Word page numbers refer to PDF pagination; PowerPoint pages map to slide numbers. For a full-document requirement select all pages (omit `pages`) and ensure the image budget covers them. Text-only semantic requirements do not render or attach images. Independently sourced expected facts must be fixed before inspecting the submission; the model cannot validate unprovided external facts by intuition.

Semantic extraction covers Word body paragraphs/tables in document order, Excel nonempty cells/formula strings/chart XML, and PPT slide text/tables/chart data including grouped shapes. Each item has a stable in-request evidence ID and artifact location. Headers, footers, notes, comments and embedded image text are explicitly outside this extraction. Scanned or image-only documents need visual review. Evidence exceeding a budget is marked unavailable, never silently truncated and scored as a whole document.

Fixed completion anchors are 1, .75, .5, .25 and 0; intermediate partial scores are permitted when justified. These feed the existing per-requirement weights and dimension weights. Models cannot change those weights. `PASS=1`, `FAIL=0`, `PARTIAL` lies strictly between them; insufficient evidence uses `NEEDS_REVIEW` with null completion. Numeric/structural critical failures still fail acceptance even when a model awards full quality credit. An incomplete scoring criterion leaves the overall score null.

## Validation, repeat review and evidence

- Semantic observations must cite a supplied evidence ID and an exact nonempty quote; the program attaches the original location.
- Visual observations must cite supplied image IDs, exact page mappings, and every selected image. The model receives actual PNG attachments, not paths alone. Hashes are checked before calls.
- `repeats: 2` or `3` performs independent calls without sharing earlier answers. Status disagreement or a completion spread greater than the configured tolerance yields `NEEDS_REVIEW`. Matching partial reviews are averaged; raw decisions remain available.
- Retries are bounded to 0–2 per independent review. Authentication/configuration HTTP failures are not retried. Timeout/error/malformed/refusal responses cannot receive a passing score.
- Cache identity covers evidence hashes, requirement/rubric, model, prompt, configuration, renderer and image hashes. Cache reuse is recorded as zero new model calls and is not independent agreement evidence.
- Each attempt preserves request/schema, raw response or CLI stdout/stderr, timing and available usage. API authorization is not logged. Unknown monetary cost stays null; token counts are not invented.
- Codex runs outside the repository with user config ignored, project instructions disabled, read-only sandbox, shell/multi-agent/app/plugin/browser tools disabled and web search disabled. Unexpected tool-use events invalidate the review. Do not treat a read-only sandbox as filesystem read isolation; the intended judgment uses only inline evidence and explicit image attachments. Existing system proxy settings are passed only to the child process; no system settings are changed.

Real calls are opt-in. `examples/artifact_assessment/model_smoke.py --model-config config.json --output <fresh-directory> --visual` creates real Word/Excel/PPT samples and runs the configured provider. Results establish integration behavior, not calibrated model accuracy or human agreement.

API schema references: [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) and [Images and vision](https://developers.openai.com/api/docs/guides/images-vision). Local `codex exec --help` is the source of supported CLI flags.
