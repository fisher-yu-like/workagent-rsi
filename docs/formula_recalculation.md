# Formula evidence and isolated recalculation

`excel.formula_exact` compares exact formula text. The old `excel.formula` name
retains exact behavior unless its frozen options explicitly select equivalent.
`excel.formula_present` checks expression versus literal only. `excel.cached_value`
observes an existing cache; it does not prove this run recalculated anything.
`excel.recalculated_value` consumes a fresh engine observation, never old caches.

Equivalent policy needs an independent numeric `oracle_value` and 1 to 20 input
variants. Each variant has name, explicit `sheet!cell` numeric/null inputs and
independent expected_value. Variants cannot overwrite the answer cell. Tasks
choose applicable negative/null/zero/reordering/last-row-addition cases; the
implementation never derives expected values from the submitted output. Formula
text plus original source hash is retained. Missing engine or unsupported oracle
configuration is a visible capability/spec gap, not string mismatch.

`RecalculationEngine.recalculate(source, new_output)` preserves source bytes,
stages a checked copy and a fixed trusted program, and runs only through an
explicit no-network Apptainer boundary. The UNO program uses ReadOnly=True,
MacroExecutionMode=0 and UpdateDocMode=0, calls calculateAll and exports to a new
XLSX. It closes only owned Office state. Source/copy/output hashes, worker hash,
engine version/binary identity and cleanup are checked. There is no host Office
fallback. Existing output paths are rejected. External workbook links and
dynamic/external formula sources remain unavailable. Bounds are100 MiB input,
50,000 populated cells and at most1000 changed inputs per variant.

Available unit-fixture/unverified output never qualifies a quality check.
`isolated_run` additionally requires T04 resource/image/cleanup trace evidence;
the configuration must only be qualified after an independent real-engine probe.
Trusted injected engines are test seams, not a substitute for that probe.
Local tests copy genuine XLSX bytes and explicitly do not invent formula caches.

## Deferred server acceptance

1. Restore the existing T04/T05 Apptainer Office worker and verify runtime identity
   and remaining disk space. Do not install or download a new runtime by default.
2. Run the fixed recalculation program on authored exact/equivalent formulas with
   independent original and variant oracles. Include applicable last-row addition,
   negative, null, zero and order-change cases and a hardcoded-answer control.
3. Retain fresh XLSX output, version/binary/worker/input/output hashes, full logs,
   actual cgroup/resource observations and owned-cleanup traces. Recheck originals.
4. Qualify the actual engine only after those probes pass, then run the equivalent
   formula acceptance cases. Until then T13 is partial/local complete, real engine
   qualification is deferred and no general formula-equivalence claim is made.
