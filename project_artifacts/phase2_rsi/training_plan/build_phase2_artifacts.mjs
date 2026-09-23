import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const BUILD = path.join(ROOT, ".artifact-build", "phase2");
const PLAN_DIR = path.join(ROOT, "project_artifacts", "phase2_rsi", "training_plan");
const REPORT_DIR = path.join(ROOT, "project_artifacts", "phase2_rsi", "reports");
const EVIDENCE_DIR = path.join(ROOT, "project_artifacts", "phase2_rsi", "evidence");
const RENDER_DIR = path.join(EVIDENCE_DIR, "renders");
const CODEX_HOME = process.env.CODEX_HOME ?? path.join(os.homedir(), ".codex");
const RUNTIME_DEPENDENCIES = process.env.CODEX_RUNTIME_DEPENDENCIES
  ?? path.join(os.homedir(), ".cache", "codex-runtimes", "codex-primary-runtime", "dependencies");
const RUNTIME_NODE_MODULES = process.env.RUNTIME_NODE_MODULES
  ?? path.join(RUNTIME_DEPENDENCIES, "node", "node_modules");
const RUNTIME_PYTHON = process.env.RUNTIME_PYTHON
  ?? path.join(RUNTIME_DEPENDENCIES, "python", process.platform === "win32" ? "python.exe" : "bin/python3");
process.env.RUNTIME_NODE_MODULES = RUNTIME_NODE_MODULES;

async function resolvePresentationsSkill() {
  if (process.env.PRESENTATIONS_SKILL_DIR) return path.resolve(process.env.PRESENTATIONS_SKILL_DIR);
  const cacheRoot = path.join(CODEX_HOME, "plugins", "cache", "openai-primary-runtime", "presentations");
  const versions = (await fs.readdir(cacheRoot, { withFileTypes: true }))
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort((a, b) => b.localeCompare(a, undefined, { numeric: true }));
  for (const version of versions) {
    const candidate = path.join(cacheRoot, version, "skills", "presentations");
    try {
      await fs.access(path.join(candidate, "container_tools", "artifact_tool_utils.mjs"));
      return candidate;
    } catch {
      // Continue to older installed versions.
    }
  }
  throw new Error(`Presentations skill not found under ${cacheRoot}`);
}

const PRES_SKILL = await resolvePresentationsSkill();
const artifactToolPath = path.join(RUNTIME_NODE_MODULES, "@oai", "artifact-tool", "dist", "artifact_tool.mjs");
const { Presentation, PresentationFile, SpreadsheetFile, Workbook } = await import(pathToFileURL(artifactToolPath).href);
await fs.mkdir(BUILD, { recursive: true });
await fs.mkdir(REPORT_DIR, { recursive: true });
await fs.mkdir(RENDER_DIR, { recursive: true });

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/);
  return lines.map((line) => line.split(","));
}

function styleHeader(range, fill = "#1E3A8A") {
  range.format.fill = fill;
  range.format.font = { name: "Microsoft YaHei", size: 10, bold: true, color: "#FFFFFF" };
  range.format.verticalAlignment = "center";
  range.format.borders = { preset: "all", style: "thin", color: "#D9D9D9" };
}

function styleWorkbookSheet(sheet, title) {
  sheet.showGridLines = false;
  sheet.getRange("A2").values = [[title]];
  sheet.getRange("A2:H2").merge();
  sheet.getRange("A2:H2").format.font = { name: "Microsoft YaHei", size: 18, bold: true, color: "#172554" };
  sheet.freezePanes.freezeRows(4);
}

async function buildExperimentMatrix() {
  const rows = parseCsv(await fs.readFile(path.join(PLAN_DIR, "experiment_matrix.csv"), "utf8"));
  const workbook = Workbook.create();
  const summary = workbook.worksheets.add("Summary");
  styleWorkbookSheet(summary, "Experiment Matrix Summary");
  summary.getRange("A4:B8").values = [
    ["Metric", "Value"],
    ["Planned experiments", rows.length - 1],
    ["P0 experiments", rows.slice(1).filter((r) => r[1] === "P0").length],
    ["P1 experiments", rows.slice(1).filter((r) => r[1] === "P1").length],
    ["P2 experiments", rows.slice(1).filter((r) => r[1] === "P2").length],
  ];
  styleHeader(summary.getRange("A4:B4"));
  summary.getRange("A4:B8").format.font = { name: "Microsoft YaHei", size: 11, color: "#1F2937" };
  styleHeader(summary.getRange("A4:B4"));
  summary.getRange("A:A").format.columnWidth = 26;
  summary.getRange("B:B").format.columnWidth = 12;
  const chart = summary.charts.add("bar", summary.getRange("A6:B8"));
  chart.title = "Experiments by priority";
  chart.hasLegend = false;
  chart.setPosition("D4", "H16");
  chart.titleTextStyle.typeface = "Microsoft YaHei";
  chart.xAxis = { axisType: "textAxis", textStyle: { typeface: "Microsoft YaHei", fontSize: 10 } };
  chart.yAxis = { numberFormatCode: "0", numberFormatSourceLinked: false, textStyle: { typeface: "Microsoft YaHei" } };

  const experiments = workbook.worksheets.add("Experiments");
  styleWorkbookSheet(experiments, "Planned Experiments")
  rows[0] = ["Experiment ID", "Priority", "Hypothesis", "Domain", "Method", "Comparator", "Split", "Repeats", "Primary metric", "Status"];
  experiments.getRange(`A4:J${3 + rows.length}`).values = rows;
  styleHeader(experiments.getRange("A4:J4"));
  experiments.getRange(`A5:J${3 + rows.length}`).format.font = { name: "Microsoft YaHei", size: 9, color: "#1F2937" };
  experiments.getRange(`A4:J${3 + rows.length}`).format.borders = { preset: "all", style: "thin", color: "#E5E7EB" };
  experiments.getRange(`A4:J${3 + rows.length}`).format.autofitColumns();
  experiments.getRange("A:A").format.columnWidth = 11;
  experiments.getRange("C:C").format.columnWidth = 12;
  experiments.getRange("D:D").format.columnWidth = 18;
  experiments.getRange("E:F").format.columnWidth = 24;
  experiments.getRange("G:G").format.columnWidth = 20;
  experiments.getRange("I:I").format.columnWidth = 25;
  experiments.getRange("A4:J20").format.wrapText = true;
  workbook.recalculate();
  const qa = path.join(RENDER_DIR, "experiment-matrix");
  await fs.mkdir(qa, { recursive: true });
  for (const sheetName of ["Summary", "Experiments"]) {
    const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1.4, format: "png" });
    await fs.writeFile(path.join(qa, `${sheetName}.png`), new Uint8Array(await preview.arrayBuffer()));
  }
  const out = path.join(PLAN_DIR, "experiment_matrix.xlsx");
  await (await SpreadsheetFile.exportXlsx(workbook)).save(out);
  await fs.rm(`${out}.inspect.ndjson`, { force: true });
  const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 50 }, summary: "formula error scan" });
  await fs.writeFile(path.join(EVIDENCE_DIR, "experiment_matrix_formula_scan.ndjson"), errors.ndjson);
}

async function buildResourceBudget() {
  const rows = parseCsv(await fs.readFile(path.join(PLAN_DIR, "resource_budget.csv"), "utf8"));
  const workbook = Workbook.create();
  const sheet = workbook.worksheets.add("Resource Budget");
  styleWorkbookSheet(sheet, "Resource Budget Planning")
  rows[0] = ["Resource", "Unit", "Quantity", "Unit cost input", "Calculation", "Authorization note"];
  sheet.getRange(`A4:F${3 + rows.length}`).values = rows;
  styleHeader(sheet.getRange("A4:F4"), "#475569");
  sheet.getRange(`A5:F${3 + rows.length}`).format.font = { name: "Microsoft YaHei", size: 10, color: "#1F2937" };
  sheet.getRange(`A4:F${3 + rows.length}`).format.borders = { preset: "all", style: "thin", color: "#D9D9D9" };
  sheet.getRange(`D5:D${3 + rows.length}`).format.fill = "#FFF7CC";
  sheet.getRange(`D5:D${3 + rows.length}`).format.font = { name: "Microsoft YaHei", size: 10, color: "#7C2D12" };
  sheet.getRange("G4").values = [["Calculated total"]];
  styleHeader(sheet.getRange("G4:G4"), "#14532D");
  for (let row = 5; row <= 11; row += 1) {
    if (row < 11) sheet.getRange(`G${row}`).formulas = [[`=IF(D${row}="","",C${row}*D${row})`]];
    else sheet.getRange(`G${row}`).formulas = [[`=IF(D${row}="","",SUM(G5:G10)*C${row}/100)`]];
  }
  sheet.getRange("G5:G11").format.numberFormat = "#,##0.00";
  sheet.getRange("A4:G11").format.autofitColumns();
  sheet.getRange("A:A").format.columnWidth = 30;
  sheet.getRange("E:E").format.columnWidth = 26;
  sheet.getRange("F:F").format.columnWidth = 38;
  sheet.getRange("A4:G11").format.wrapText = true;
  sheet.getRange("A13:F13").merge();
  sheet.getRange("A13").values = [["Local hardware"]];
  styleHeader(sheet.getRange("A13:F13"), "#475569");
  const hardware = [["CPU", "Intel Core i7-14650HX, 16 cores / 24 threads"], ["Memory", "16 GB RAM"], ["GPU", "NVIDIA GeForce RTX 5060 Laptop GPU, 8 GB VRAM"]];
  hardware.forEach((row, index) => {
    const target = 14 + index;
    sheet.getRange(`A${target}`).values = [[row[0]]];
    sheet.getRange(`B${target}:F${target}`).merge();
    sheet.getRange(`B${target}`).values = [[row[1]]];
    sheet.getRange(`A${target}:F${target}`).format.borders = { preset: "all", style: "thin", color: "#D9D9D9" };
    sheet.getRange(`A${target}:F${target}`).format.font = { name: "Microsoft YaHei", size: 10, color: "#1F2937" };
  });
  workbook.recalculate();
  const qa = path.join(RENDER_DIR, "resource-budget");
  await fs.mkdir(qa, { recursive: true });
  const preview = await workbook.render({ sheetName: "Resource Budget", autoCrop: "all", scale: 1.4, format: "png" });
  await fs.writeFile(path.join(qa, "Resource-Budget.png"), new Uint8Array(await preview.arrayBuffer()));
  const out = path.join(PLAN_DIR, "resource_budget.xlsx");
  await (await SpreadsheetFile.exportXlsx(workbook)).save(out);
  await fs.rm(`${out}.inspect.ndjson`, { force: true });
  const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 50 }, summary: "formula error scan" });
  await fs.writeFile(path.join(EVIDENCE_DIR, "resource_budget_formula_scan.ndjson"), errors.ndjson);
}

function addText(slide, text, position, style = {}) {
  const shape = slide.shapes.add({ geometry: "textbox", position, fill: "none", line: { fill: "none", width: 0 } });
  shape.text = text;
  shape.text.style = { typeface: "Microsoft YaHei", fontSize: 23, color: "#334155", autoFit: "shrinkText", ...style };
  return shape;
}

function addBox(slide, text, left, top, width, height, fill) {
  const shape = slide.shapes.add({ geometry: "roundRect", position: { left, top, width, height }, fill, line: { fill: "#CBD5E1", width: 1 } });
  shape.text = text;
  shape.text.style = { typeface: "Microsoft YaHei", fontSize: 17, bold: true, color: "#FFFFFF", horizontalAlignment: "center", verticalAlignment: "middle", autoFit: "shrinkText" };
  return shape;
}

async function buildPresentation() {
  const experimentRows = parseCsv(await fs.readFile(path.join(PLAN_DIR, "experiment_matrix.csv"), "utf8")).slice(1);
  const priorityCounts = Object.fromEntries(
    ["P0", "P1", "P2"].map((priority) => [priority, experimentRows.filter((row) => row[1] === priority).length]),
  );
  const presentation = Presentation.create({ slideSize: { width: 1280, height: 720 } });
  const titleSlide = presentation.slides.add();
  titleSlide.background.fill = "#0F172A";
  addText(titleSlide, "WorkAgent-RSI 整体框架与训练计划", { left: 80, top: 210, width: 1120, height: 110 }, { fontSize: 44, bold: true, color: "#FFFFFF" });
  addText(titleSlide, "Phase 2 设计交付\n2026-09-23", { left: 84, top: 350, width: 600, height: 100 }, { fontSize: 23, color: "#CBD5E1" });

  const scope = presentation.slides.add(); scope.background.fill = "#F8FAFC";
  addText(scope, "RSI 定义与边界", { left: 70, top: 45, width: 1140, height: 70 }, { fontSize: 36, bold: true, color: "#172554" });
  addText(scope, "RSI 指版本化技能和 harness 的持久改进。\n\n当前自动化范围为 L1 和受控 L2。人类保留目标、评估、资源和高风险发布权。\n\n模型权重自训、目标自修改和无限制 evaluator 共演化不在当前范围。", { left: 100, top: 155, width: 1060, height: 420 }, { fontSize: 25 });

  const architecture = presentation.slides.add(); architecture.background.fill = "#F8FAFC";
  addText(architecture, "系统架构", { left: 70, top: 45, width: 1140, height: 70 }, { fontSize: 36, bold: true, color: "#172554" });
  const boxes = [
    ["Benchmark\nRunner", 70, 170, "#1E3A8A"], ["Executor\nOffice", 285, 170, "#0369A1"], ["Trace and\nArtifacts", 500, 170, "#0F766E"],
    ["Candidate\nGenerator", 285, 390, "#7C3AED"], ["Verifier and\nEvaluator", 500, 390, "#B45309"], ["Promotion and\nRegistry", 715, 390, "#166534"],
  ];
  for (const [text, left, top, fill] of boxes) addBox(architecture, text, left, top, 175, 105, fill);
  addText(architecture, "Frozen evaluator and protected tests remain outside candidate control", { left: 920, top: 235, width: 280, height: 180 }, { fontSize: 20, bold: true, color: "#7F1D1D" });

  const regularization = presentation.slides.add(); regularization.background.fill = "#F8FAFC";
  addText(regularization, "RRSI 正则化", { left: 70, top: 45, width: 1140, height: 70 }, { fontSize: 36, bold: true, color: "#172554" });
  addText(regularization, "Proposal side\n退火原子编辑预算\n证据感知归因\n停滞时结构化探索", { left: 105, top: 175, width: 460, height: 300 }, { fontSize: 25, color: "#334155" });
  addText(regularization, "Selection side\n泄漏筛查\n噪声带门槛\n成本感知接受\n无效组件剪枝", { left: 670, top: 175, width: 460, height: 330 }, { fontSize: 25, color: "#334155" });

  const dataFlow = presentation.slides.add(); dataFlow.background.fill = "#F8FAFC";
  addText(dataFlow, "证据与版本数据流", { left: 70, top: 45, width: 1140, height: 70 }, { fontSize: 36, bold: true, color: "#172554" });
  const stages = ["Run manifest", "Trace and artifact", "Diagnosis", "Candidate", "Evaluation", "Decision", "Skill version"];
  stages.forEach((stage, i) => addBox(dataFlow, stage, 45 + i * 175, 270, 145, 90, ["#334155", "#0369A1", "#0F766E", "#7C3AED", "#B45309", "#166534", "#1E3A8A"][i]));
  addText(dataFlow, "每个节点记录 schema、版本、Git commit 和内容 hash", { left: 215, top: 430, width: 850, height: 90 }, { fontSize: 23, color: "#475569", horizontalAlignment: "center" });

  const stagesSlide = presentation.slides.add(); stagesSlide.background.fill = "#F8FAFC";
  addText(stagesSlide, "训练与评估阶段", { left: 70, top: 45, width: 1140, height: 70 }, { fontSize: 36, bold: true, color: "#172554" });
  addText(stagesSlide, "A  30-task pilot：验证环境、schema 和 grader\n\nB  Excel closed loop：先验证客观断言与晋级机制\n\nC  Word/PPT expansion：加入 OOXML、渲染和视觉检查\n\nD  Transfer：冻结技能后测试新模板、跨域和第二 executor", { left: 100, top: 155, width: 1080, height: 440 }, { fontSize: 25 });

  const experiments = presentation.slides.add(); experiments.background.fill = "#F8FAFC";
  addText(experiments, "实验矩阵", { left: 70, top: 45, width: 1140, height: 70 }, { fontSize: 36, bold: true, color: "#172554" });
  addText(experiments, `${experimentRows.length} 个计划实验\n\n${priorityCounts.P0} 个 P0：核心闭环与 RRSI 消融\n${priorityCounts.P1} 个 P1：验证器、artifact evaluator、迁移与泄漏\n${priorityCounts.P2} 个 P2：Word 和 PowerPoint 全量扩展\n\n主要比较：完整 WorkAgent-RSI 对单体 Self-Refine`, { left: 100, top: 155, width: 1080, height: 440 }, { fontSize: 26 });

  const resources = presentation.slides.add(); resources.background.fill = "#F8FAFC";
  addText(resources, "资源与 Go No-Go", { left: 70, top: 45, width: 1140, height: 70 }, { fontSize: 36, bold: true, color: "#172554" });
  addText(resources, "本机：16 核 CPU、16 GB RAM、8 GB VRAM\n用途：编排、Office 处理、渲染和轻量模型\n\nPilot 基线约 540 run units，Excel candidate evaluation 上限约 2160 run units\n\n只有 evaluator 可用、保护边界有效、候选可复现且成本获批，才进入 main study", { left: 100, top: 155, width: 1080, height: 440 }, { fontSize: 25 });

  const risks = presentation.slides.add(); risks.background.fill = "#F8FAFC";
  addText(risks, "风险与 Phase 3 门禁", { left: 70, top: 45, width: 1140, height: 70 }, { fontSize: 36, bold: true, color: "#172554" });
  addText(risks, "主要风险\nprovider 和 Office 引擎差异\n视觉 judge 对字体与渲染敏感\n有限任务上的自适应过拟合\nskill library 检索漂移\n\nPhase 3 需要确认数据许可证、provider、Office engine、预算和隐藏集治理", { left: 100, top: 150, width: 1080, height: 460 }, { fontSize: 25 });

  for (const slide of presentation.slides.items) slide.speakerNotes.textFrame.setText("Source: Phase 2 Markdown design and training plan in this repository.");
  const qa = path.join(RENDER_DIR, "pptx"); await fs.mkdir(qa, { recursive: true });
  for (let i = 0; i < presentation.slides.items.length; i += 1) {
    const preview = await presentation.export({ slide: presentation.slides.items[i], format: "png", scale: 1 });
    await fs.writeFile(path.join(qa, `slide-${i + 1}.png`), new Uint8Array(await preview.arrayBuffer()));
  }
  const staging = path.join(BUILD, "pptx-finalizer"); await fs.mkdir(staging, { recursive: true });
  const candidatePath = path.join(staging, "candidate.pptx");
  const finalPath = path.join(staging, "phase2-final.pptx");
  await fs.rm(finalPath, { force: true });
  await fs.rm(path.join(EVIDENCE_DIR, "pptx_validation.json"), { force: true });
  await (await PresentationFile.exportPptx(presentation)).save(candidatePath);
  const { finalizePresentation } = await import(pathToFileURL(path.join(PRES_SKILL, "container_tools", "artifact_tool_utils.mjs")).href);
  await finalizePresentation({
    explicitTotalSlideCount: 9,
    requiredNativeTableOwnerSlides: [], requiredNativeChartOwnerSlides: [],
    workspaceDir: ROOT, candidatePath, finalPath, pythonExecutable: RUNTIME_PYTHON,
    integrityValidatorPath: path.join(PRES_SKILL, "container_tools", "inspect_presentation_package_integrity.py"),
    layoutValidatorPath: path.join(PRES_SKILL, "container_tools", "inspect_presentation_layout_geometry.py"),
    layoutArgs: ["--expected-slide-size-emu", "12192000,6858000", "--validate-heading-fit"],
    fontPolicy: { basis: "design", families: ["Microsoft YaHei"] }, verifyArtifactToolImport: true,
    receiptPath: path.join(EVIDENCE_DIR, "pptx_validation.json"),
  });
  await fs.copyFile(finalPath, path.join(REPORT_DIR, "RSI整体框架与训练计划.pptx"));
}

await buildExperimentMatrix();
await buildResourceBudget();
await buildPresentation();
console.log("Phase 2 XLSX and PPTX artifacts built");
