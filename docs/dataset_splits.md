# Family splits and final-set storage

The v2 protocol groups tasks by family, source-document identity and source
content hash before generating variants. A group stays in one split. Reusing
an input variant across splits is also rejected. Renaming task IDs or source
files does not remove a shared-content constraint.

The target is 24 base tasks per domain: eight develop, four regression, four
promotion validation, four final test and four OOD transfer. Three input
variants per base give 72 base tasks and 216 instances overall. The 12 OOD
bases account for 36 of those instances. This is a target, not a completed
dataset or permission to run models.

`TaskFamilyManifest` records base, family, source, variants, domain, split,
hashes, provenance and prior exposure. `assign_grouped_splits` requires that
variants have not yet been assigned. It allocates whole connected groups,
uses a fixed seed, and refuses an insufficient inventory. It is a conservative
deterministic allocator, not an optimizer that guarantees a packing solution.
`validate_family_splits` checks the frozen result. `split_quality_report`
reports shortages and requires three distinct input hashes per base.

Legacy `hidden` means `promotion_validation`, a repeatedly used protected
promotion gate. It is not an untouched final test. For the WorkAgent runner,
prefer the modern `promotion_validation` input key. A legacy caller must pass
`legacy_hidden_mapping='promotion_validation'` explicitly. The internal RSI
engine retains its old `hidden` key for compatibility, and `split-roles.json`
records the actual role. Protected task rows are marked hidden. Formal runs
also require a complete family manifest bound to the adaptive task IDs and
domains. The runner rejects `final_test`, including an empty final key, before
creating the run directory. Final content never enters candidate feedback.

`SealedFinalStore` is an evaluator-side interface. It requires an empty private
root outside all declared developer roots, snapshots allowlisted ordinary
input files, and binds task IDs and domains to final families. Exposed content
is rejected. Only counts and a final hash leave through its public descriptor.
The developer view includes develop metadata and protected hashes/counts. It
does not include final instructions, family/source IDs, task IDs or store paths.
The one-use evaluation marker is created before invoking the trusted evaluator;
a failed evaluation consumes the set too. Inputs and the manifest are checked
before and after evaluation, and results stay private with only a result hash
returned. The service must retain the original public hash as its commitment.

This application interface is locally tested. Actual deployment also needs a
private evaluator service account and filesystem/mount isolation. A directory
on the same host cannot isolate data from that host's owner. No such production
service or unseen final corpus was provisioned in T26.

The inventory audit reads the actual T25 corpus and the historical pilot. T25
has 90 exposed calibration cases, 30 distinct input documents and three source
families. Its paired outputs are defect/equivalence/gap controls rather than
three independent input variants per base. The old pilot's three families
already span historical splits. Neither can supply an untouched final set.
The 72/216 dataset target remains blocked; the audit does not pad or relabel it.
The empty final descriptor explicitly says `sealed=false`.

```powershell
& .venv/Scripts/python.exe project_artifacts/phase3_experiments/scripts/audit_family_inventory.py --calibration-manifest <built-corpus/case_manifest.json> --output <new-audit-directory>
& .venv/Scripts/python.exe project_artifacts/phase3_experiments/data/quality_check.py --family-manifest <audit/family-manifest.json> --report <new-report.json>
```

Both commands return exit 1 for this insufficient dataset. Their report records
the expected blocker; the unit test suite can still pass. Historical pilot data
and reports remain unchanged.
