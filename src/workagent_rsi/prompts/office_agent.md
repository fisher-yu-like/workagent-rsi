You are creating an Office deliverable for a {domain} task.

Task:
{instruction}

Additional instructions:
{agent_instructions}

Staged input files (use these copies only):
{input_files}

Work only inside this workspace. Do not access parent directories, repository-sensitive files, hidden evaluation data, or network resources. Do not overwrite source inputs. You may use the local Python Office libraries (openpyxl, python-docx, python-pptx). Create ordinary, non-empty {suffix} deliverables inside outputs/. Reopen and check each generated Office file.

Write deliverables.json in the workspace root as an object with one key, "deliverables", containing relative paths such as "outputs/report{suffix}". Your final structured response must list exactly those paths, set status to "completed" only when successful, and list staged input paths actually used in input_files_used.
