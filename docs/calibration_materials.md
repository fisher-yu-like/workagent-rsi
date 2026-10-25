# Development calibration materials

T25 supplies 90 project-generated, readable Office files: 30 per domain.
Each domain has 10 correct outputs, 10 outputs with one authored defect,
five explicitly permitted equivalent solutions, and five spec/capability gaps.
Gaps have `INCOMPLETE` truth and structurally valid artifacts. They are not
counted as defective artifacts. Equivalent solutions include their permission
in the task instruction.

The checked-in `tests/fixtures/calibration/case_manifest.json` contains literal
truth, task scope, source references, recipes and raw XML claims. The generator
does not run or import the production evaluator to assign truth. Integrity tests
read OOXML directly, reopen every output through its Office library, verify
hashes and rebuild the corpus to check byte reproducibility. ZIP timestamps and
core-property dates are fixed. The seed is 20261025.

The 90 cases share three source families and six input documents. These are
development calibration materials, not 90 independent task families, an external
benchmark, or an untouched final set. There are no human agreement or model
accuracy results. T27 will measure evaluator behavior on these materials; a
T25 integrity pass does not imply the production evaluator passes every case.
The obstruction control uses known opaque overlapping PowerPoint geometry.
No rendering service or model was called to qualify its visual appearance.

Build a separate, empty output directory with:

```powershell
& .venv/Scripts/python.exe project_artifacts/phase3_experiments/scripts/build_calibration_cases.py --output <empty-directory>
```

The build stores hashes, a separate `oracle-truth.json` and
`oracle-provenance.json` beside the files. Loading a built corpus checks the
truth binding and both input/output hashes. Four grouped integrity tests share
one module-scoped corpus. Only the reproducibility control builds a second
copy; no test generates 90 files once per assertion or per case.
