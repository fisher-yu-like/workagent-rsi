# Trace-grounded failure diagnosis

`diagnose_failure(issue, execution, trace)` reads evidence supplied by the trusted
run owner. It never opens files, executes scripts, calls a model or edits an
artifact. An output mismatch alone produces an unknown cause with strength0.
Legacy prose classification also leaves the cause unknown.

The trace must declare `split=develop` and no hidden-test flag. Each evidence
item declares kind, text, exact UTF-8 SHA-256, `authorized=true`, `split=develop`
and `feedback_visibility=develop`. Invalid hashes, private items, unsupported
kinds and oversized text cannot establish a cause. These flags are assertions
by the trusted run owner, not permissions a candidate may grant itself.
Supported kinds are script, stderr, input_manifest and file_events. At most16
items of100,000 characters are inspected; quoted evidence is limited to4000
characters. Unsupported or missing evidence yields an unknown hypothesis.

SyntaxError, AttributeError and KeyError rules require an actual agent-execution
failure, matching stderr traceback filename/line and source text. References
identify the script hash and exact line, and the captured exception message.
No exception is inferred from a comment or artifact text.

An aggregation-boundary hypothesis requires a successful artifact-producing
execution, an observed artifact defect, an additive range loop and an independent
input manifest for the affected sheet. The manifest declares exactly sheet,
first_data_row, last_data_row, row_count and max_row, with consistent integers.
An exclusive max_row loop may omit the final row; the diagnosis asks for a last
row and appended-row experiment to falsify this hypothesis. Other sheets and
stale artifacts after failed execution do not establish that cause.

An overwrite hypothesis requires distinct ordered write hashes for a delivered
artifact plus matching repeated save calls. It asks whether the final writer
replaced the intended artifact; it does not assume every repeated save is wrong.
Without trusted write receipts, the cause stays unknown.

Every new diagnosis records exact evidence details, confidence_basis,
recommended_action and falsification_check. Numeric confidence is an uncalibrated
rule strength, not a measured probability. Private environment/transport diagnoses
remain evaluation-only. Candidate context projects only develop diagnoses and
revalidates mutable containers; private diagnoses cannot be appended later.
Legacy run/evidence paths become logical hashes before entering feedback.

The T19 local probe runs five small fixed trusted authored programs, never
model-produced code: real syntax/API/sheet exceptions, an omitted-last-row sum,
and two actual distinct writes to one workbook. It retains stderr, script/input/
output hashes and trace-linked hypotheses. This qualifies local diagnosis rules,
not the execution sandbox or a live agent. See `hardening_t19_trace_diagnosis.json`.
