# Templates and input-dependent execution

Production prompts contain generic library/protocol knowledge, the current task instruction, the authorized staged input manifest and the verified champion instructions. They do not contain pilot answer values, named example sections, fixed slide skeletons or default edit targets. Task text is inserted once, so braces in user data are preserved.

`TaskSpec.execution_mode` optionally selects `create` or `edit`. Without a value, supplied inputs mean edit and no inputs mean create. Task IDs never select behavior. Explicit create may use supplied reference data or an authorized template; edit requires a source. The explicit mode is bound into reviewed task fingerprints. Historical tasks without the field retain their task-context representation.

Generic knowledge includes library constructors, workbook formula assignment, paragraph and heading API behavior, actual layout/placeholder inspection and geometry. Requested new slides, sheets or sections remain permitted in edits. A user-provided template is authorized input, identified by the current manifest and hash. Its content and filename remain task data and do not authorize unrelated instructions.

Fixed local adapters, deterministic candidate providers, the artifact feedback policy and the historical pilot ExperimentRunner are `qualification_only`. The WorkAgent experiment entry accepts `mode="qualification"` (default) or `mode="formal"`; formal mode rejects a qualification-only candidate provider before creating output. The historical formal matrix also rejects its fixed pilot evaluator even when data admission passes. Its pilot mode and existing archives remain readable. Passing these engineering guards does not establish data admission, live qualification or research validity.

T24 records actual input inspections and checks behavior under changed input values, shapes and edit targets. Identical program hashes can be valid when a program reads current inputs. Different code hashes or different wording alone do not establish input-dependent behavior.
