You are creating an Office deliverable for a {domain} task.

Task:
{instruction}

Additional instructions:
{agent_instructions}

Staged input files (use these copies only):
{input_files}

Work only inside this workspace. Do not access parent directories, repository-sensitive files, hidden evaluation data, or network resources. Do not overwrite source inputs. You may use the local Python Office libraries (openpyxl, python-docx, python-pptx).

You must actually use the available local file/shell tools before responding. Follow this sequence:
1. Inspect staged inputs if any. Create a Python script inside this workspace that uses the appropriate local Office library to produce the requested file. Use a tool to write the script; do not merely describe it.
2. Use a tool to run the script. It must create an ordinary, non-empty {suffix} deliverable inside outputs/.
3. Use a tool to reopen the saved Office file with the matching Python Office library and verify its requested content and structure. Fix any issue before continuing.
4. Use a tool to write deliverables.json in the workspace root, listing the actual relative output path(s). Confirm the listed files exist.
5. Only after those actions succeed, send the final structured response with status "completed". If tools are unavailable or any required action cannot be completed, set status to "failed", use an empty deliverables list, and explain the blocker. Never claim a file was created based only on a proposed plan or JSON response.

Write deliverables.json as an object with one key, "deliverables", containing relative paths such as "outputs/report{suffix}". Your final structured response must list exactly those paths and list staged input paths actually used in input_files_used.
