"""Typed contracts for the local Office WorkAgent provider."""

from __future__ import annotations

import json
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .hashing import canonical_json_hash, sha256_file
from .rsi_contracts import ProviderRecord


_RELATIVE_POSIX_PATH_PATTERN = r"^(?!/)(?!.*[:\\])(?!.*(?:^|/)\.{1,2}(?:/|$))[^/]+(?:/[^/]+)*$"


class WorkAgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = "qwen2.5:7b"
    executable: str = "codex"
    backend: Literal["codex-cli", "ollama-native"] = "codex-cli"
    ollama_base_url: str = "http://localhost:11434"
    timeout_seconds: int = Field(default=600, ge=1)
    max_output_files: int = Field(default=8, ge=1)
    max_artifact_bytes: int = Field(default=104857600, ge=1)
    max_tool_turns: int = Field(default=32, ge=1, le=64)
    verify_com: bool = True


class WorkAgentSkill(BaseModel):
    """The only candidate-controlled part of a WorkAgent Office run."""

    model_config = ConfigDict(extra="forbid")
    version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    instructions: str = Field(min_length=1, max_length=20000)


class AgentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "failed"]
    deliverables: list[str] = Field(json_schema_extra={"items": {"type": "string", "pattern": _RELATIVE_POSIX_PATH_PATTERN}})
    summary: str
    input_files_used: list[str] = Field(json_schema_extra={"items": {"type": "string", "pattern": _RELATIVE_POSIX_PATH_PATTERN}})

    @field_validator("deliverables", "input_files_used")
    @classmethod
    def relative_posix_paths(cls, values: list[str]) -> list[str]:
        for value in values:
            if (
                not value
                or value.startswith("/")
                or "\\" in value
                or ":" in value
                or any(part in ("", ".", "..") for part in value.split("/"))
            ):
                raise ValueError("response paths must be relative POSIX paths without empty or traversal components")
        return values


class ProviderOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "failed", "unavailable", "timeout"]
    response: AgentResponse | None = None
    record: ProviderRecord | None = None
    error: str | None = None


def build_agent_response_schema() -> dict[str, object]:
    """Return the structured-output schema supplied to the Codex CLI."""
    return AgentResponse.model_json_schema()


class CodexOfficeProvider:
    def __init__(self, config: WorkAgentConfig) -> None:
        self.config = config
        self.schema_path = (Path(__file__).parent / "schemas" / "agent_response.schema.json").resolve()

    def command(self, workspace: Path, response_path: Path, schema_path: Path) -> list[str]:
        return [
            self.config.executable,
            "exec",
            "--ignore-user-config",
            "--oss",
            "--local-provider",
            "ollama",
            "--model",
            self.config.model,
            "--ephemeral",
            "--sandbox",
            "workspace-write",
            "--json",
            "--output-schema",
            str(schema_path.resolve()),
            "--output-last-message",
            str(response_path.resolve()),
            "--cd",
            str(workspace.resolve()),
            "-",
        ]

    def run(self, prompt: str, workspace: Path, record_root: Path) -> ProviderOutcome:
        workspace = Path(workspace).resolve()
        records = Path(record_root).resolve()
        workspace_hash = canonical_json_hash({
            path.relative_to(workspace).as_posix(): sha256_file(path)
            for path in sorted(workspace.rglob("*"))
            if path.is_file() and ".git" not in path.parts and "provider_records" not in path.parts
        })
        records.mkdir(parents=True, exist_ok=True)
        response_path = workspace / f"agent_response-{uuid4().hex}.json"
        canonical_response_path = workspace / "agent_response.json"
        canonical_response_path.unlink(missing_ok=True)
        if self.config.backend == "ollama-native":
            return self._run_native_ollama(
                prompt, workspace, records, response_path, canonical_response_path, workspace_hash
            )
        command = self.command(workspace, response_path, self.schema_path)
        (records / "prompt.md").write_text(prompt, encoding="utf-8", newline="\n")
        (records / "command.json").write_text(json.dumps(command, indent=2) + "\n", encoding="utf-8", newline="\n")

        started = datetime.now(timezone.utc)
        status = "failed"
        response = None
        error = None
        exit_code = None
        stdout = ""
        stderr = ""
        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                input=prompt,
                timeout=self.config.timeout_seconds,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            exit_code = completed.returncode
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
            if exit_code != 0:
                error = f"provider exited with code {exit_code}"
                if _environment_failure(stdout, stderr, self.config.model):
                    status = "unavailable"
                    error += ": required CLI/provider/model capability unavailable (see stdout/stderr)"
            elif not response_path.exists():
                error = "provider did not write structured output"
            else:
                try:
                    response = AgentResponse.model_validate_json(response_path.read_text(encoding="utf-8"))
                    status = response.status
                    shutil.copyfile(response_path, canonical_response_path)
                    shutil.copyfile(response_path, records / "agent_response.json")
                except ValueError as exc:
                    error = f"invalid provider response: {exc}"
        except subprocess.TimeoutExpired as exc:
            status = "timeout"
            error = f"provider timeout after {exc.timeout} seconds"
            stdout = _decode_process_output(exc.stdout)
            stderr = _decode_process_output(exc.stderr)
        except OSError as exc:
            status = "unavailable"
            error = str(exc)

        (records / "provider.stdout.jsonl").write_text(stdout, encoding="utf-8", newline="\n")
        (records / "provider.stderr.txt").write_text(stderr, encoding="utf-8", newline="\n")
        ended = datetime.now(timezone.utc)
        record = ProviderRecord(
            provider="codex-cli",
            provider_version="local-1",
            model_identity=f"ollama:{self.config.model}",
            command=command,
            prompt_hash=canonical_json_hash({"prompt": prompt}),
            workspace_hash=workspace_hash,
            started_at=started,
            ended_at=ended,
            exit_code=exit_code,
            status=status,
            output_ref=sha256_file(response_path) if response is not None else None,
            error=error,
        )
        (records / "provider_record.json").write_text(
            json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return ProviderOutcome(status=status, response=response, record=record, error=error)

    def _run_native_ollama(
        self,
        prompt: str,
        workspace: Path,
        records: Path,
        response_path: Path,
        canonical_response_path: Path,
        workspace_hash: str,
    ) -> ProviderOutcome:
        """Run a bounded, auditable Ollama tool loop without relying on Codex model metadata."""
        command = ["ollama", "api/chat", "--model", self.config.model, "--base-url", self.config.ollama_base_url]
        office_task = _native_is_office_task(prompt)
        started = datetime.now(timezone.utc)
        status: Literal["completed", "failed", "unavailable", "timeout"] = "failed"
        response: AgentResponse | None = None
        error: str | None = None
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        tool_log = records / "tool_events.jsonl"
        records.mkdir(parents=True, exist_ok=True)
        # Office scripts conventionally save under outputs/. Provision the
        # workspace-owned directory before the first model action so a valid
        # script does not fail solely because its parent directory is absent.
        (workspace / "outputs").mkdir(parents=True, exist_ok=True)
        (records / "prompt.md").write_text(prompt, encoding="utf-8", newline="\n")
        (records / "command.json").write_text(json.dumps(command, indent=2) + "\n", encoding="utf-8", newline="\n")
        system = (
            "You are a local Office WorkAgent. You must use the provided tools to do the work in the isolated workspace. "
            "Issue at most one tool call per response and wait for its result before issuing the next call; never batch independent tool calls. "
            "Save every requested Office deliverable under outputs/ using a workspace-relative path. "
            "Never use ../ or absolute paths; deliverables.json belongs at the workspace root, not inside outputs/. "
            "Create the manifest by calling write_file path exactly deliverables.json, never outputs/deliverables.json. "
            "The write_file content argument must be a STRING containing serialized JSON text, never an object. For example, pass the literal text {\"deliverables\":[\"outputs/report.xlsx\"]} as the content string. "
            "write_file content for a .py file must be raw Python source code, not a JSON object with a script field. Keep JSON serialization only for deliverables.json and the final response. "
            + ("Office tasks do not expose read_file; inspect staged and generated Office files with the matching Python library. "
               if office_task else "Do not use read_file on binary Office documents; reopen them in your Python script with the matching Office library instead. ")
            + "Your script must create outputs/ if needed, save there, reopen and verify contents, then write deliverables.json as JSON object {\"deliverables\":[\"outputs/name.ext\"]}. "
            "Before writing the script, turn the user's task into a checklist. After reopening the saved file, assert every requested sheet, cell, and formula against the exact task values; do the equivalent exact-content and structure assertions for Word and PowerPoint. If any assertion fails, fix the script, rerun it, and verify again before writing the manifest. Never substitute plausible values for requested values. "
            "For every edit task, load the staged source with the matching Office library, preserve every existing sheet and cell or slide unless the task explicitly requests a change, and save a new output file; never create a replacement workbook or deck that drops source content. For PowerPoint verification, search all shapes and paragraphs for each required phrase rather than assuming a fixed shape index, and verify slide count, bounds, and overlap. The input deck may contain blank slides with no title or placeholders; do not use slide.shapes.title and do not use fixed placeholders, iterate over slide.shapes and use slide.shapes.add_textbox(...) when no suitable shape exists. "
            "For Word, every required heading named in the task must use style='Heading 1' or level=1 unless the task explicitly says Heading 2; level=0 is Title and will fail evaluation. "
            "For Excel, preserve source cells and write exact formula text beginning with '='; use a direct quoted formula such as '=SUM(Transactions!B2:B4)' rather than concatenating quote fragments; reopen with data_only=False and compare the formula cell value to the exact formula string. openpyxl does not calculate formulas or populate cached numeric results, so do not assert a cached numeric result from a formula cell. "
            "For PowerPoint, preserve the requested slide count exactly (editing means no add_slide calls), keep each shape inside slide bounds, and avoid shape overlap. "
            "In Python scripts, do not put a literal line break inside a quoted Python string; use an escaped \\n sequence or separate paragraphs/text boxes. "
            "Write one complete, syntactically valid Python script before running it; do not repeatedly rewrite the same broken script. "
            "Use exact requested output filenames and valid double-quoted JSON in deliverables.json. "
            "In the final response, input_files_used must be the exact ordered array of paths in input_manifest.json; when there are no staged inputs, return []. "
            "Never claim completion before the requested file exists, has been reopened and checked, and deliverables.json has been written. "
            "Return only the requested JSON response after all tool work succeeds."
        )
        messages: list[dict[str, object]] = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        deadline = time.monotonic() + self.config.timeout_seconds
        exit_code: int | None = 0
        tools_used = False
        action_required = False
        force_finalize = False
        format_corrections = 0
        max_format_corrections = 2

        try:
            for turn in range(self.config.max_tool_turns):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    status = "timeout"
                    error = f"provider timeout after {self.config.timeout_seconds} seconds"
                    break
                payload = {
                    "model": self.config.model,
                    "stream": False,
                    "messages": messages,
                }
                if not force_finalize:
                    payload["tools"] = _native_tool_definitions(include_read_file=not office_task)
                # Keep the model in action mode until at least one real tool
                # call has happened. Supplying JSON-schema output on turn one
                # makes small local models skip the tools and hallucinate a
                # completion response.
                if tools_used and not action_required:
                    payload["format"] = build_agent_response_schema()
                request_path = records / f"ollama_request_{turn:02d}.json"
                request_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                request = urllib.request.Request(
                    self.config.ollama_base_url.rstrip("/") + "/api/chat",
                    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=max(1, int(remaining))) as http_response:
                    raw = http_response.read()
                response_path_for_turn = records / f"ollama_response_{turn:02d}.json"
                response_path_for_turn.write_bytes(raw)
                parsed = json.loads(raw.decode("utf-8"))
                stdout_lines.append(json.dumps({"turn": turn, "response": parsed}, ensure_ascii=False))
                message = parsed.get("message") if isinstance(parsed, dict) else None
                if not isinstance(message, dict):
                    error = "Ollama response did not contain a message object"
                    break
                tool_calls = message.get("tool_calls") or []
                messages.append(message)
                if tool_calls:
                    tools_used = True
                    action_required = False
                    failed_tools: list[dict[str, object]] = []
                    for index, call in enumerate(tool_calls):
                        if not isinstance(call, dict):
                            result = {"ok": False, "error": "malformed tool call"}
                            name = "unknown"
                            arguments: object = {}
                        else:
                            function = call.get("function")
                            function = function if isinstance(function, dict) else {}
                            name = str(function.get("name") or "unknown")
                            arguments = function.get("arguments", {})
                            if isinstance(arguments, str):
                                try:
                                    arguments = json.loads(arguments)
                                except json.JSONDecodeError:
                                    arguments = {"_raw": arguments}
                            result = _execute_native_tool(
                                name,
                                arguments,
                                workspace,
                                timeout_seconds=max(1, int(remaining)),
                            )
                        event = {"turn": turn, "index": index, "name": name, "arguments": arguments, "result": result}
                        with tool_log.open("a", encoding="utf-8", newline="\n") as handle:
                            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
                        messages.append({"role": "tool", "content": json.dumps(result, ensure_ascii=False)})
                        if result.get("ok") is False:
                            failed_tools.append({"name": name, "result": result})
                    if failed_tools:
                        failure_details = json.dumps(failed_tools, ensure_ascii=False)
                        messages.append({
                            "role": "user",
                            "content": (
                                "The previous tool action failed; do not claim completion or write the manifest yet. "
                                "Read the exact tool error below. For run_python, inspect the reported SyntaxError or "
                                "traceback, rewrite the complete script to fix the specific failing line, then run it "
                                "again. Do not rerun an unchanged broken script. Continue with one tool action at a "
                                "time and only report completed after the Office file is created, reopened, checked, "
                                "and deliverables.json is valid. Tool failure details: "
                                + failure_details
                            ),
                        })
                    if _native_manifest_ready(workspace):
                        force_finalize = True
                        action_required = False
                        messages.append({
                            "role": "user",
                            "content": (
                                "The output file and deliverables.json are now present. Do not call any more tools "
                                "and do not read the binary Office file. Return only the final completed JSON object "
                                "with the exact manifest paths and staged input paths."
                            ),
                        })
                    continue
                content = message.get("content")
                if not isinstance(content, str) or not content.strip():
                    # Some local Ollama models occasionally emit an empty
                    # assistant message while deciding whether to call a
                    # tool. Keep the bounded conversation alive and ask for
                    # the next concrete action instead of discarding the run.
                    action_required = True
                    messages.append({
                        "role": "user",
                        "content": (
                            "The previous assistant message was empty. Continue the Office task now. "
                            "Use exactly one tool call for the next action; after the file is verified and "
                            "deliverables.json is written, return only the completed JSON object."
                        ),
                    })
                    error = "Ollama returned an empty assistant message; requested continuation"
                    continue
                if force_finalize and "<tool_call>" in content:
                    # Some Ollama models emit their internal XML tool syntax
                    # even after tools have been removed for finalization. It
                    # is not a structured AgentResponse; reopen the tool
                    # channel and ask for the JSON response explicitly.
                    force_finalize = False
                    action_required = True
                    messages.append({
                        "role": "user",
                        "content": (
                            "Do not emit XML or a tool call. The files are ready. Return only the final JSON object "
                            "matching the requested response schema, with no markdown or extra keys."
                        ),
                    })
                    continue
                if not tools_used:
                    action_required = True
                    messages.append({
                        "role": "user",
                        "content": (
                            "Do not answer yet. You have not used any tools. "
                            "Use list_files/read_file, then write_file and run_python to create and verify the Office deliverable."
                        ),
                    })
                    continue
                try:
                    response = AgentResponse.model_validate_json(content)
                except ValueError as exc:
                    error = f"invalid provider response: {exc}"
                    if office_task and not _native_manifest_ready(workspace):
                        available_office_outputs = sorted(
                            path.relative_to(workspace).as_posix()
                            for path in (workspace / "outputs").glob("*")
                            if path.is_file() and path.suffix.lower() in {".xlsx", ".docx", ".pptx"}
                        )
                        if available_office_outputs:
                            manifest_content = json.dumps({"deliverables": available_office_outputs})
                            messages.append({
                                "role": "user",
                                "content": (
                                    "Your previous response was not a final response, and the Office deliverable exists "
                                    "but the required workspace-root manifest is missing or invalid. Do not return JSON yet. "
                                    "You MUST call write_file with path exactly deliverables.json. Its content argument "
                                    "must be a STRING whose text is exactly " + manifest_content + "; do not pass a JSON object. "
                                    "Do not use read_file on Office files. Wait for the tool result, then return the completed "
                                    "JSON with these exact deliverables and the staged input paths."
                                ),
                            })
                            response = None
                            status = "failed"
                            action_required = True
                            force_finalize = False
                            continue
                    if format_corrections >= max_format_corrections:
                        break
                    format_corrections += 1
                    try:
                        expected_inputs = _native_staged_input_paths(workspace)
                        expected_inputs_text = json.dumps(expected_inputs, ensure_ascii=False)
                    except ValueError:
                        expected_inputs_text = "unavailable because input_manifest.json is invalid"
                    messages.append({
                        "role": "user",
                        "content": (
                            "Your final response was not valid JSON matching the required schema. "
                            "Return only one JSON object with exactly status, deliverables, summary, and input_files_used. "
                            "input_files_used must exactly equal this ordered staged-path array: "
                            + expected_inputs_text
                            + ". Do not call tools or add markdown."
                        ),
                    })
                    continue
                response_path.write_text(response.model_dump_json(), encoding="utf-8", newline="\n")
                shutil.copyfile(response_path, canonical_response_path)
                shutil.copyfile(response_path, records / "agent_response.json")
                status = response.status
                if response.status == "failed":
                    # A failed structured response is not a terminal provider
                    # failure yet: tool results may have exposed a fixable
                    # issue (for example a malformed manifest). Give the
                    # model another bounded tool turn and keep the final
                    # response untrusted until it reports completion.
                    failure_summary = response.summary or "agent reported failure"
                    messages.append({
                        "role": "user",
                        "content": (
                            "Your previous attempt failed. Continue using the tools to fix the concrete error, "
                            "then verify the Office file and write a valid deliverables.json before answering completed. "
                            f"Previous summary: {failure_summary}"
                        ),
                    })
                    response = None
                    status = "failed"
                    error = failure_summary
                    action_required = True
                    continue
                readiness_errors = _native_completion_errors(workspace, response, require_office=office_task)
                if readiness_errors:
                    error = "; ".join(readiness_errors)
                    if office_task and (
                        "deliverables.json is missing" in readiness_errors
                        or "Office task must report at least one Office deliverable" in readiness_errors
                        or "deliverables.json does not match the structured response" in readiness_errors
                    ):
                        available_office_outputs = sorted(
                            path.relative_to(workspace).as_posix()
                            for path in (workspace / "outputs").glob("*")
                            if path.is_file() and path.suffix.lower() in {".xlsx", ".docx", ".pptx"}
                        )
                        if available_office_outputs:
                            manifest_content = json.dumps({"deliverables": available_office_outputs})
                            messages.append({
                                "role": "user",
                                "content": (
                                    "Do not return a final response yet. The Office deliverable exists but the required "
                                    "workspace-root manifest is not valid. You MUST call write_file with path exactly "
                                "deliverables.json. Its content argument must be a STRING whose text is exactly " + manifest_content + "; do not pass a JSON object. Do not use read_file "
                                    "on Office files. Wait for the tool result, then return the completed JSON with "
                                    "these exact deliverables and the staged input paths."
                                ),
                            })
                            response = None
                            status = "failed"
                            action_required = True
                            force_finalize = False
                            continue
                    if format_corrections >= max_format_corrections:
                        break
                    format_corrections += 1
                    messages.append({
                        "role": "user",
                        "content": (
                            "Do not claim completion yet. The local acceptance checks found: "
                            + error
                            + ". If the output files are already correct, return only the corrected JSON response; "
                            "otherwise use the tools to fix the issues and verify again. "
                            "input_files_used must exactly equal the ordered staged paths in input_manifest.json, "
                            "or [] when there are no staged inputs."
                        ),
                    })
                    response = None
                    status = "failed"
                    action_required = True
                    continue
                break
            else:
                error = f"provider exceeded {self.config.max_tool_turns} tool turns"
        except urllib.error.HTTPError as exc:
            status = "unavailable" if exc.code in (404, 408, 429, 500, 502, 503, 504) else "failed"
            error = f"Ollama HTTP error {exc.code}: {exc.reason}"
            stderr_lines.append(error)
        except urllib.error.URLError as exc:
            status = "unavailable"
            error = f"Ollama connection failed: {exc.reason}"
            stderr_lines.append(error)
        except TimeoutError:
            status = "timeout"
            error = f"provider timeout after {self.config.timeout_seconds} seconds"
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            error = str(exc)
            stderr_lines.append(error)

        if status == "failed" and error is None:
            error = "provider did not produce a completed response"
        (records / "provider.stdout.jsonl").write_text("\n".join(stdout_lines) + ("\n" if stdout_lines else ""), encoding="utf-8", newline="\n")
        (records / "provider.stderr.txt").write_text("\n".join(stderr_lines) + ("\n" if stderr_lines else ""), encoding="utf-8", newline="\n")
        ended = datetime.now(timezone.utc)
        record = ProviderRecord(
            provider="ollama-api",
            provider_version="local-1",
            model_identity=f"ollama:{self.config.model}",
            command=command,
            prompt_hash=canonical_json_hash({"prompt": prompt}),
            workspace_hash=workspace_hash,
            started_at=started,
            ended_at=ended,
            exit_code=exit_code,
            status=status,
            output_ref=sha256_file(response_path) if response is not None else None,
            error=error,
        )
        (records / "provider_record.json").write_text(
            json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return ProviderOutcome(status=status, response=response, record=record, error=error)

def _native_completion_errors(
    workspace: Path,
    response: AgentResponse,
    *,
    require_office: bool = False,
) -> list[str]:
    """Check only cheap local invariants before accepting a model completion."""
    errors: list[str] = []
    try:
        expected_inputs = _native_staged_input_paths(workspace)
    except ValueError:
        errors.append("input_manifest.json is invalid")
        expected_inputs = []
    if response.input_files_used != expected_inputs:
        errors.append(f"input_files_used must exactly match staged inputs: {expected_inputs!r}")
    # The provider unit contract also supports generic text probes. The
    # deliverables manifest is mandatory for Office artifacts, where the
    # adapter's evaluator consumes it as a trust boundary.
    office_extensions = {".xlsx", ".docx", ".pptx"}
    office_completion = require_office or any(Path(value).suffix.lower() in office_extensions for value in response.deliverables)
    if require_office and not any(Path(value).suffix.lower() in office_extensions for value in response.deliverables):
        errors.append("Office task must report at least one Office deliverable")
    if not office_completion:
        for value in response.deliverables:
            try:
                path = _native_tool_path(workspace, value)
            except ValueError:
                errors.append(f"unsafe deliverable path: {value}")
                continue
            if not path.is_file():
                errors.append(f"deliverable is missing: {value}")
        return errors
    manifest_path = workspace / "deliverables.json"
    if not manifest_path.is_file():
        errors.append("deliverables.json is missing")
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            errors.append("deliverables.json is not valid UTF-8 JSON")
        else:
            if not isinstance(manifest, dict) or set(manifest) != {"deliverables"} or manifest["deliverables"] != response.deliverables:
                errors.append("deliverables.json does not match the structured response")
    for value in response.deliverables:
        try:
            path = _native_tool_path(workspace, value)
        except ValueError:
            errors.append(f"unsafe deliverable path: {value}")
            continue
        if not path.is_file():
            errors.append(f"deliverable is missing: {value}")
    return errors


def _native_staged_input_paths(workspace: Path) -> list[str]:
    """Read the ordered, private staged-input paths used by final-response validation."""
    manifest_path = workspace / "input_manifest.json"
    if not manifest_path.exists():
        return []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("input_manifest.json is invalid") from exc
    files = manifest.get("files") if isinstance(manifest, dict) else None
    if not isinstance(files, list) or any(
        not isinstance(item, dict) or not isinstance(item.get("copied"), str)
        for item in files
    ):
        raise ValueError("input_manifest.json is invalid")
    return [item["copied"] for item in files]


def _native_is_office_task(prompt: str) -> bool:
    """Recognize the stable task header emitted by the Office adapter."""
    first_line = prompt.splitlines()[0].strip().lower() if prompt.splitlines() else ""
    return first_line.startswith("you are creating an office deliverable for a ") and first_line.endswith(" task.")


def _native_manifest_ready(workspace: Path) -> bool:
    """Return true only when a complete local deliverables manifest exists."""
    manifest_path = workspace / "deliverables.json"
    if not manifest_path.is_file():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    if not isinstance(manifest, dict) or set(manifest) != {"deliverables"}:
        return False
    values = manifest.get("deliverables")
    if not isinstance(values, list) or not values or not all(isinstance(value, str) for value in values):
        return False
    for value in values:
        try:
            path = _native_tool_path(workspace, value)
        except ValueError:
            return False
        if not path.is_file():
            return False
    return True


def _native_tool_definitions(*, include_read_file: bool = True) -> list[dict[str, object]]:
    """Return the deliberately small tool surface exposed to the local model."""
    tools: list[dict[str, object]] = [
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write UTF-8 text to a relative workspace path. Input files are read-only.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative POSIX path in the workspace"},
                        "content": {"type": "string", "description": "Complete UTF-8 file contents"},
                    },
                    "required": ["path", "content"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a UTF-8 text file from the workspace, including staged inputs.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": "Relative POSIX path"}},
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files below a relative workspace directory.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": "Relative directory, or '.'"}},
                    "required": [],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_python",
                "description": "Run a Python script that already exists inside the workspace (never an input file).",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": "Relative .py script path"}},
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
        },
    ]
    if not include_read_file:
        tools = [tool for tool in tools if tool["function"]["name"] != "read_file"]
    return tools


def _native_tool_path(workspace: Path, value: object, *, write: bool = False) -> Path:
    """Resolve a model-supplied POSIX path without allowing traversal or links."""
    if not isinstance(value, str) or not value or value in (".", "./"):
        if value not in (".", "./"):
            raise ValueError("path must be a non-empty relative POSIX path")
        return workspace
    if value.startswith("/") or "\\" in value or ":" in value:
        raise ValueError("path must be a relative POSIX path")
    # Models commonly write a directory path as ``outputs/``. Treat a
    # trailing separator as presentation syntax while still rejecting empty
    # interior components and traversal.
    value = value.rstrip("/") or "."
    pieces = value.split("/")
    if any(piece in ("", ".", "..") for piece in pieces):
        raise ValueError("path contains an unsafe component")
    candidate = workspace.joinpath(*pieces)
    # Check every existing segment before following it. This catches symlinks and
    # Windows reparse points in both existing files and parent directories.
    relative = candidate.relative_to(workspace)
    segments = [workspace]
    current = workspace
    for part in relative.parts:
        current = current / part
        segments.append(current)
    for segment in segments:
        if segment.exists() or segment.is_symlink():
            info = segment.lstat()
            if segment.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
                raise ValueError("symlink or reparse point is not allowed")
    if write and pieces[0] == "inputs":
        raise ValueError("staged input files are read-only")
    return candidate


def _execute_native_tool(
    name: str,
    arguments: object,
    workspace: Path,
    *,
    timeout_seconds: int = 60,
) -> dict[str, object]:
    """Execute one bounded native tool call and return JSON-serializable evidence."""
    if not isinstance(arguments, dict):
        return {"ok": False, "error": "tool arguments must be an object"}
    try:
        if name == "write_file":
            path = _native_tool_path(workspace, arguments.get("path"), write=True)
            content = arguments.get("content")
            if not isinstance(content, str):
                raise ValueError("content must be a string")
            if len(content.encode("utf-8")) > 10 * 1024 * 1024:
                raise ValueError("content exceeds 10 MiB")
            if path.suffix.lower() in {".xlsx", ".docx", ".pptx"}:
                raise ValueError("binary Office files must be created by run_python, not write_file")
            if path.name == "deliverables.json" and path.parent == workspace:
                try:
                    manifest = json.loads(content)
                except json.JSONDecodeError as exc:
                    raise ValueError("deliverables.json must be valid JSON") from exc
                if (
                    not isinstance(manifest, dict)
                    or set(manifest) != {"deliverables"}
                    or not isinstance(manifest["deliverables"], list)
                    or not all(isinstance(item, str) for item in manifest["deliverables"])
                ):
                    raise ValueError("deliverables.json must be an object with a string-list deliverables key")
                if not manifest["deliverables"]:
                    raise ValueError("deliverables.json must list at least one existing workspace file")
                for value in manifest["deliverables"]:
                    deliverable = _native_tool_path(workspace, value)
                    if not deliverable.is_file():
                        raise ValueError(
                            f"deliverables.json cannot list a missing workspace file: {value}"
                        )
            elif path.name == "deliverables.json":
                raise ValueError("deliverables.json must be written at the workspace root")
            path.parent.mkdir(parents=True, exist_ok=True)
            relative = path.relative_to(workspace)
            segments = [workspace]
            current = workspace
            for part in relative.parts[:-1]:
                current = current / part
                segments.append(current)
            for segment in segments:
                if segment.exists() or segment.is_symlink():
                    info = segment.lstat()
                    if segment.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
                        raise ValueError("symlink or reparse point is not allowed")
            path.write_text(content, encoding="utf-8", newline="\n")
            return {"ok": True, "path": path.relative_to(workspace).as_posix(), "size_bytes": path.stat().st_size}

        if name == "read_file":
            path = _native_tool_path(workspace, arguments.get("path"))
            if path.suffix.lower() in {".xlsx", ".docx", ".pptx"}:
                raise ValueError("binary Office files cannot be read with read_file; reopen and inspect them with Python")
            if not path.is_file():
                raise ValueError("path is not a regular file")
            if path.stat().st_size > 10 * 1024 * 1024:
                raise ValueError("file exceeds 10 MiB")
            return {"ok": True, "path": path.relative_to(workspace).as_posix(), "content": path.read_text(encoding="utf-8")}

        if name == "list_files":
            path = _native_tool_path(workspace, arguments.get("path", "."))
            if not path.is_dir():
                raise ValueError("path is not a directory")
            files: list[str] = []
            for item in sorted(path.rglob("*")):
                if item.is_file() and not item.is_symlink():
                    files.append(item.relative_to(workspace).as_posix())
            return {"ok": True, "files": files[:1000]}

        if name == "run_python":
            script = _native_tool_path(workspace, arguments.get("path"), write=True)
            if script.suffix.lower() != ".py" or not script.is_file():
                raise ValueError("run_python requires an existing .py script")
            before_office = {
                path.name
                for path in workspace.iterdir()
                if path.is_file() and path.suffix.lower() in {".xlsx", ".docx", ".pptx"}
            }
            completed = subprocess.run(
                [sys.executable, str(script)],
                cwd=workspace,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(1, timeout_seconds),
                check=False,
            )
            normalized_outputs: list[str] = []
            if completed.returncode == 0:
                outputs = workspace / "outputs"
                outputs.mkdir(parents=True, exist_ok=True)
                for candidate in sorted(workspace.iterdir()):
                    if (
                        candidate.is_file()
                        and candidate.name not in before_office
                        and candidate.suffix.lower() in {".xlsx", ".docx", ".pptx"}
                    ):
                        destination = outputs / candidate.name
                        if not destination.exists():
                            candidate.replace(destination)
                            normalized_outputs.append(destination.relative_to(workspace).as_posix())
            return {
                "ok": completed.returncode == 0,
                "returncode": completed.returncode,
                "stdout": completed.stdout[-20000:],
                "stderr": completed.stderr[-20000:],
                "normalized_outputs": normalized_outputs,
            }

        return {"ok": False, "error": f"unknown tool: {name}"}
    except subprocess.TimeoutExpired as exc:
        return {"ok": False, "error": f"python tool timeout after {exc.timeout} seconds"}
    except (OSError, UnicodeError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


def _decode_process_output(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def _environment_failure(stdout: str, stderr: str, model: str) -> bool:
    """Recognize explicit environment errors; unknown nonzero exits stay failed."""
    diagnostic = (stderr + "\n" + stdout).lower()
    required_flags = ("--ignore-user-config", "--oss", "--local-provider", "--model", "--ephemeral",
                      "--sandbox", "--json", "--output-schema", "--output-last-message", "--cd")
    for line in diagnostic.splitlines():
        if any(flag in line for flag in required_flags) and re.search(
            r"unexpected argument|unrecognized (?:argument|option)|unknown (?:argument|option)|invalid value|unsupported (?:argument|option)", line
        ):
            return True
        if ("ollama" in line or "localhost:11434" in line or "127.0.0.1:11434" in line) and re.search(
            r"connection refused|could not connect|failed to connect|not running|unavailable", line
        ):
            return True
        if (model.lower() in line or re.search(r"\b(?:model|ollama)\s+['\"]?[^\s'\"]+['\"]?", line)) and re.search(
            r"not found|does not exist|not available|does not support (?:tools|tool calling|json schema|structured output)|unsupported model", line
        ):
            return True
    return False
