# Spreadsheet assessment

Locate observations by logical artifact, sheet and cell/range. Freeze expected values from original inputs or independent labels, including tolerances and input hashes.

`excel.cell` checks a typed value; `excel.formula` checks exact required formula text; `excel.cached_value` checks an existing stored cache only. `excel.recalculated_value` requires an actual engine and remains unavailable until one is configured. Reading formula text or caches with openpyxl is not recalculation. If equivalent calculations are permitted, assess their outputs under the task standard instead of requiring a particular formula string.

`excel.sheets`, `excel.range`, `excel.chart` and `excel.number_format` cover structure, data coverage, chart references and number formats. A chart reference check does not prove visual legibility. Group dependent observations under one scoring requirement when they describe the same error. Weights live only in the task specification.
