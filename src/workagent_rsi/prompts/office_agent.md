You are creating an Office deliverable for a {domain} task.

Task:
{instruction}

Additional instructions:
{agent_instructions}

Staged input files (use these copies only):
{input_files}

Work only inside this workspace. Do not access parent directories, repository-sensitive files, hidden evaluation data, or network resources. Do not use `../` or absolute paths. Do not overwrite source inputs. You may use the local Python Office libraries (openpyxl, python-docx, python-pptx).

You must actually use the available local file/shell tools before responding. Follow this sequence:
1. Inspect staged inputs if any. Create a Python script inside this workspace that uses the appropriate local Office library to produce the requested file. Use a tool to write the script; do not merely describe it.
2. Use a tool to run the script. It must create an ordinary, non-empty {suffix} deliverable inside outputs/.
3. Use a tool to reopen the saved Office file with the matching Python Office library and verify its requested content and structure. Fix any issue before continuing.
4. Use a tool to write `deliverables.json` in the workspace root (not inside outputs/), listing the actual relative output path(s). The JSON object must contain exactly one key, `deliverables`; do not put `input_files_used` in this manifest. Confirm the listed files exist.
5. Only after those actions succeed, send the final structured response with status "completed". If tools are unavailable or any required action cannot be completed, set status to "failed", use an empty deliverables list, and explain the blocker. Never claim a file was created based only on a proposed plan or JSON response.

Tool calls must be sequential: do not call run_python until write_file confirms the script was written. If a tool call fails, fix the script and run it again; do not continue with stale or missing outputs. Verify the script after its final edit, and do not write the manifest until the script runs successfully and the saved Office file has been reopened and checked.

The first tool call must be write_file for the complete Python script. Never write deliverables.json before the script has run successfully. Do not call run_python until that script write has returned success. If run_python fails, fix or rewrite the script and run it again; do not move on to a manifest or a completed response.

Write deliverables.json as an object with one key, "deliverables", containing relative paths such as "outputs/report{suffix}". Your final structured response must list exactly those paths and list staged input paths actually used in input_files_used.
The final structured response has its own input_files_used field; do not copy that field into deliverables.json.

The `write_file` tool's `content` argument must be a string, not a JSON object. Pass the JSON manifest as text, for example content `{"deliverables":["outputs/report.xlsx"]}`. Keep the argument JSON-escaped as required by the tool call.

Format-specific acceptance rules:
{format_rules}
