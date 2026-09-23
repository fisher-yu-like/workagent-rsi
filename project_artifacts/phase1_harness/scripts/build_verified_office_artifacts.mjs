import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import {
  Presentation,
  PresentationFile,
  SpreadsheetFile,
  Workbook,
} from "@oai/artifact-tool";

const ROOT = process.cwd();
const BUILD = path.join(ROOT, ".artifact-build");
const REPORTS = path.join(ROOT, "project_artifacts", "phase1_harness", "reports");
const RESULTS = path.join(ROOT, "project_artifacts", "phase1_harness", "results", "run_summary.json");
const PRES_SKILL = "C:/Users/sy/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations";
const RUNTIME_PYTHON = "C:/Users/sy/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe";
await fs.mkdir(BUILD, { recursive: true });
await fs.mkdir(REPORTS, { recursive: true });
const results = JSON.parse(await fs.readFile(RESULTS, "utf8"));

function styleRange(range, fill, color = "#FFFFFF") {
  range.format.fill = fill;
  range.format.font = { name: "Microsoft YaHei", bold: true, color, size: 11 };
  range.format.verticalAlignment = "center";
  range.format.borders = { preset: "all", style: "thin", color: "#D9D9D9" };
}

async function buildWorkbook() {
  const workbook = Workbook.create();
  const sheetNames = ["Run Summary", "Task Details", "Timing", "Errors", "Metrics", "Environment", "Artifact Index"];
  const sheets = Object.fromEntries(sheetNames.map((name) => [name, workbook.worksheets.add(name)]));
  for (const sheet of Object.values(sheets)) {
    sheet.showGridLines = false;
    sheet.freezePanes.freezeRows(3);
    sheet.getRange("A2").values = [[sheet.name]];
    sheet.getRange("A2:G2").merge();
    sheet.getRange("A2:G2").format.font = { name: "Microsoft YaHei", size: 18, bold: true, color: "#172554" };
  }

  const summaryRows = [["Case", "Run ID", "State", "Sec", "Git Commit"], ...results.map((r) => [r.case_id, r.run_id, r.state, r.duration_seconds, r.git_commit.slice(0, 12)])];
  sheets["Run Summary"].getRange(`A4:E${3 + summaryRows.length}`).values = summaryRows;
  styleRange(sheets["Run Summary"].getRange("A4:E4"), "#1E3A8A");
  sheets["Run Summary"].getRange("D5:D7").format.numberFormat = "0.000";

  const taskRows = [["Case", "Task ID", "Domain", "Adapter"], ...results.map((r) => [r.case_id, r.case_id, "smoke", "MockWorkAgentAdapter"])];
  sheets["Task Details"].getRange(`A4:D${3 + taskRows.length}`).values = taskRows;
  styleRange(sheets["Task Details"].getRange("A4:D4"), "#1E3A8A");

  const timingRows = [["Case", "Started At", "Ended At", "Sec"], ...results.map((r) => [r.case_id, `UTC ${r.started_at.replace("T", " ").slice(0, 19)}`, `UTC ${r.ended_at.replace("T", " ").slice(0, 19)}`, r.duration_seconds])];
  sheets.Timing.getRange(`A4:D${3 + timingRows.length}`).values = timingRows;
  styleRange(sheets.Timing.getRange("A4:D4"), "#1E3A8A");
  sheets.Timing.getRange("D5:D7").format.numberFormat = "0.000";

  const errorRows = [["Case", "State", "Failure", "Tries"], ...results.map((r) => [r.case_id, r.state, r.failure?.message ?? "", r.failure?.attempts ?? 0])];
  sheets.Errors.getRange(`A4:D${3 + errorRows.length}`).values = errorRows;
  styleRange(sheets.Errors.getRange("A4:D4"), "#7F1D1D");

  const metricRows = [["Case", "Score", "Passed", "Critical Failures"], ...results.map((r) => [r.case_id, r.evaluation?.score ?? "", r.evaluation?.passed ?? false, (r.evaluation?.critical_failures ?? []).join("; ")])];
  sheets.Metrics.getRange(`A4:D${3 + metricRows.length}`).values = metricRows;
  styleRange(sheets.Metrics.getRange("A4:D4"), "#14532D");

  const envRows = [["Key", "Value"], ["Python", results[0].python], ["Platform", results[0].platform], ["Adapter", "MockWorkAgentAdapter"], ["External WorkAgent", "Not configured"]];
  sheets.Environment.getRange(`A4:B${3 + envRows.length}`).values = envRows;
  styleRange(sheets.Environment.getRange("A4:B4"), "#475569");

  const artifactRows = [["Case", "Artifact", "Type", "Bytes", "Relative path"]];
  for (const result of results) {
    for (const artifact of result.artifacts ?? []) {
      const normalized = artifact.path.replaceAll("\\", "/");
      artifactRows.push([result.case_id, artifact.artifact_id.slice(0, 16), artifact.media_type, artifact.size_bytes, `results/${result.case_id}/artifacts/${artifact.artifact_id.slice(0, 16)}`]);
    }
  }
  sheets["Artifact Index"].getRange(`A4:E${3 + artifactRows.length}`).values = artifactRows;
  styleRange(sheets["Artifact Index"].getRange("A4:E4"), "#475569");
  sheets["Run Summary"].getRange("A:A").format.columnWidth = 20;
  sheets["Run Summary"].getRange("B:B").format.columnWidth = 20;
  sheets["Run Summary"].getRange("C:C").format.columnWidth = 14;
  sheets["Run Summary"].getRange("D:D").format.columnWidth = 14;
  sheets["Run Summary"].getRange("E:E").format.columnWidth = 18;
  sheets.Timing.getRange("A:A").format.columnWidth = 20;
  sheets.Timing.getRange("B:C").format.columnWidth = 25;
  sheets.Timing.getRange("D:D").format.columnWidth = 14;
  sheets.Errors.getRange("A:A").format.columnWidth = 20;
  sheets.Errors.getRange("B:B").format.columnWidth = 14;
  sheets.Errors.getRange("C:C").format.columnWidth = 24;
  sheets.Errors.getRange("D:D").format.columnWidth = 12;
  sheets["Artifact Index"].getRange("A:A").format.columnWidth = 20;
  sheets["Artifact Index"].getRange("B:B").format.columnWidth = 24;
  sheets["Artifact Index"].getRange("C:C").format.columnWidth = 14;
  sheets["Artifact Index"].getRange("D:D").format.columnWidth = 14;
  sheets["Artifact Index"].getRange("E:E").format.columnWidth = 45;
  sheets["Artifact Index"].getRange("B5:E20").format.wrapText = true;

  for (const sheet of Object.values(sheets)) {
    const used = sheet.getUsedRange();
    used.format.font = { name: "Microsoft YaHei", size: 10, color: "#1F2937" };
    sheet.getRange("A2:G2").format.font = { name: "Microsoft YaHei", size: 18, bold: true, color: "#172554" };
    used.format.autofitColumns();
    used.format.autofitRows();
    for (let col = 0; col < 7; col += 1) {
      const range = sheet.getRangeByIndexes(0, col, Math.max(used.rowCount, 1), 1);
      if (range.format.columnWidth > 45) range.format.columnWidth = 45;
    }
  }
  styleRange(sheets["Run Summary"].getRange("A4:E4"), "#1E3A8A");
  styleRange(sheets["Task Details"].getRange("A4:D4"), "#1E3A8A");
  styleRange(sheets.Timing.getRange("A4:D4"), "#1E3A8A");
  styleRange(sheets.Errors.getRange("A4:D4"), "#7F1D1D");
  styleRange(sheets.Metrics.getRange("A4:D4"), "#14532D");
  styleRange(sheets.Environment.getRange("A4:B4"), "#475569");
  styleRange(sheets["Artifact Index"].getRange("A4:E4"), "#475569");
  workbook.recalculate();
  const qaDir = path.join(BUILD, "xlsx-qa");
  await fs.mkdir(qaDir, { recursive: true });
  for (const sheetName of sheetNames) {
    const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1.5, format: "png" });
    await fs.writeFile(path.join(qaDir, `${sheetName.replaceAll(" ", "-")}.png`), new Uint8Array(await preview.arrayBuffer()));
  }
  const out = path.join(REPORTS, "Harness运行数据.xlsx");
  await (await SpreadsheetFile.exportXlsx(workbook)).save(out);
  const inspect = await workbook.inspect({ kind: "table", range: "Run Summary!A2:E7", include: "values,formulas", tableMaxRows: 10, tableMaxCols: 8 });
  await fs.writeFile(path.join(BUILD, "xlsx-inspect.ndjson"), inspect.ndjson);
  const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 50 }, summary: "formula error scan" });
  await fs.writeFile(path.join(BUILD, "xlsx-errors.ndjson"), errors.ndjson);
}

function addText(slide, text, position, style = {}) {
  const shape = slide.shapes.add({ geometry: "textbox", position, fill: "none", line: { fill: "none", width: 0 } });
  shape.text = text;
  shape.text.style = { typeface: "Microsoft YaHei", fontSize: 23, color: "#334155", autoFit: "shrinkText", ...style };
  return shape;
}

async function buildPresentation() {
  const presentation = Presentation.create({ slideSize: { width: 1280, height: 720 } });
  const slideData = [
    ["Harness 与 WorkAgent 运行报告", "Phase 1B 本地 Mock Pipeline\n2026-09-23"],
    ["目标与边界", "本轮验证 Harness 契约、状态机、trace、artifact 和 evaluator 闭环。\n\n外部 WorkAgent provider 尚未配置。Office 文件来自已记录的 mock 运行证据。"],
    ["系统架构", "1  TaskSpec 校验任务输入\n2  Orchestrator 管理状态与重试\n3  MockWorkAgentAdapter 产生确定性事件\n4  ArtifactStore 和 TraceStore 保存证据\n5  BasicEvaluator 执行关键断言"],
    ["Pipeline 流程", "VALIDATING\nRUNNING\nEVALUATING\nSUCCEEDED 或 FAILED\n\n可控失败保留 run ID、失败原因和尝试次数。"],
    ["运行结果", results.map((r) => `${r.case_id}    ${r.state}    ${r.duration_seconds.toFixed(3)} s`).join("\n")],
    ["问题与下一步", "已验证本地 mock 闭环。\n\n下一步接入真实 WorkAgent adapter，并在可用的 Office 引擎中执行公式重算和渲染验证。完成真实 Pipeline 后再进入 RSI 框架阶段。"],
  ];
  for (let i = 0; i < slideData.length; i += 1) {
    const [title, body] = slideData[i];
    const slide = presentation.slides.add();
    slide.background.fill = i === 0 ? "#0F172A" : "#F8FAFC";
    if (i === 0) {
      addText(slide, title, { left: 90, top: 210, width: 1100, height: 100 }, { fontSize: 46, bold: true, color: "#FFFFFF" });
      addText(slide, body, { left: 94, top: 340, width: 900, height: 120 }, { fontSize: 24, color: "#CBD5E1" });
    } else {
      addText(slide, title, { left: 72, top: 48, width: 1136, height: 72 }, { fontSize: 36, bold: true, color: "#172554" });
      addText(slide, body, { left: 100, top: 160, width: 1080, height: 440 }, { fontSize: i === 4 ? 26 : 25, color: "#334155" });
      addText(slide, `${i + 1}`, { left: 1170, top: 650, width: 50, height: 30 }, { fontSize: 15, color: "#64748B" });
    }
    slide.speakerNotes.textFrame.setText("Source: project_artifacts/phase1_harness/results/run_summary.json");
  }
  const previewDir = path.join(BUILD, "pptx-qa");
  await fs.mkdir(previewDir, { recursive: true });
  for (let i = 0; i < presentation.slides.items.length; i += 1) {
    const slide = presentation.slides.items[i];
    const preview = await presentation.export({ slide, format: "png", scale: 1 });
    await fs.writeFile(path.join(previewDir, `slide-${i + 1}.png`), new Uint8Array(await preview.arrayBuffer()));
  }
  const { finalizePresentation } = await import(pathToFileURL(path.join(PRES_SKILL, "container_tools", "artifact_tool_utils.mjs")).href);
  const stagingDir = path.join(BUILD, "pptx-finalizer");
  const candidatePath = path.join(stagingDir, "candidate.pptx");
  const finalPath = path.join(stagingDir, "phase1-report-final.pptx");
  await fs.mkdir(stagingDir, { recursive: true });
  await (await PresentationFile.exportPptx(presentation)).save(candidatePath);
  await finalizePresentation({
    explicitTotalSlideCount: 6,
    requiredNativeTableOwnerSlides: [],
    requiredNativeChartOwnerSlides: [],
    workspaceDir: ROOT,
    candidatePath,
    finalPath,
    pythonExecutable: RUNTIME_PYTHON,
    integrityValidatorPath: path.join(PRES_SKILL, "container_tools", "inspect_presentation_package_integrity.py"),
    layoutValidatorPath: path.join(PRES_SKILL, "container_tools", "inspect_presentation_layout_geometry.py"),
    layoutArgs: ["--expected-slide-size-emu", "12192000,6858000", "--validate-heading-fit"],
    fontPolicy: { basis: "design", families: ["Microsoft YaHei"] },
    verifyArtifactToolImport: true,
    receiptPath: path.join(BUILD, "pptx-validation.json"),
  });
  await fs.copyFile(finalPath, path.join(REPORTS, "Harness与WorkAgent运行报告.pptx"));
}

await buildWorkbook();
await buildPresentation();
console.log("verified Office artifacts built");
