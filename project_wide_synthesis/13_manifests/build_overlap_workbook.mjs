import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = "/Users/xiejinbo/Documents/SPH-PIO-PoC";
const out = `${root}/project_wide_synthesis`;
const payload = JSON.parse(await fs.readFile(`${out}/09_publication_options/cross_paper_overlap_matrix.json`, "utf8"));
const wb = Workbook.create();
const matrix = wb.worksheets.add("Overlap Matrix");
const labels = wb.worksheets.add("Label Definitions");
const guide = wb.worksheets.add("Decision Guide");

const navy = "#17324D", blue = "#DCEAF7", pale = "#F5F7FA", border = "#C9D2DC";
const labelColors = {
  PAPER_1_PRIMARY: "#D9EAF7", PAPER_2_PRIMARY: "#DFF1E5", SHARED_BACKGROUND_ONLY: "#FFF2CC",
  SUPPLEMENT_ONLY: "#EDE7F6", DUPLICATION_RISK: "#FCE4D6", CANNOT_REPEAT: "#F4CCCC",
};

matrix.showGridLines = false;
matrix.getRange("A1:D1").merge();
matrix.getRange("A1").values = [["SPH-PIO-PoC Cross-Paper Overlap Matrix"]];
matrix.getRange("A1:D1").format = { fill: navy, font: { bold: true, color: "#FFFFFF", size: 16 }, rowHeight: 30, verticalAlignment: "center" };
matrix.getRange("A2:D2").merge();
matrix.getRange("A2").values = [["S1只读发表决策档案｜Paper 1 = Stage 00–03 verification-first；Paper 2 = Stage 04 training/performance"]];
matrix.getRange("A2:D2").format = { fill: blue, font: { color: navy, italic: true }, rowHeight: 26, wrapText: true };
matrix.getRange("A4:D4").values = [["Item", "Paper 1 role", "Paper 2 role", "Anti-duplication rule"]];
matrix.getRange("A4:D4").format = { fill: navy, font: { bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", verticalAlignment: "center", rowHeight: 26 };
const rows = payload.rows.map(r => [r.item, r.paper1, r.paper2, r.rule]);
matrix.getRangeByIndexes(4, 0, rows.length, 4).values = rows;
matrix.getRange(`A5:D${4+rows.length}`).format = { wrapText: true, verticalAlignment: "top", borders: { preset: "inside", style: "thin", color: border } };
for (let i=0; i<rows.length; i++) {
  const row = i + 5;
  matrix.getRange(`B${row}`).format.fill = labelColors[rows[i][1]] || pale;
  matrix.getRange(`C${row}`).format.fill = labelColors[rows[i][2]] || pale;
  matrix.getRange(`B${row}:C${row}`).format.font = { bold: true, color: navy };
}
matrix.getRange("A:A").format.columnWidth = 20;
matrix.getRange("B:C").format.columnWidth = 27;
matrix.getRange("D:D").format.columnWidth = 64;
matrix.getRange(`A5:D${4+rows.length}`).format.autofitRows();
matrix.freezePanes.freezeRows(4);

labels.showGridLines = false;
labels.getRange("A1:C1").merge(); labels.getRange("A1").values = [["Role Label Definitions"]];
labels.getRange("A1:C1").format = { fill: navy, font: { bold: true, color: "#FFFFFF", size: 15 }, rowHeight: 30 };
labels.getRange("A3:C3").values = [["Label", "Operational meaning", "Publication constraint"]];
labels.getRange("A3:C3").format = { fill: navy, font: { bold: true, color: "#FFFFFF" } };
const defs = [
 ["PAPER_1_PRIMARY","Paper 1的主要结果/贡献","Paper 2只能最小背景引用"],
 ["PAPER_2_PRIMARY","Paper 2的主要新结果/贡献","Paper 1不得预先声称"],
 ["SHARED_BACKGROUND_ONLY","两篇都可最小化介绍","不得重复完整推导/结果"],
 ["SUPPLEMENT_ONLY","仅补充材料或审计用途","不得作为双稿主贡献"],
 ["DUPLICATION_RISK","高重复风险","投稿前必须人工逐图逐表核对"],
 ["CANNOT_REPEAT","该稿不得出现为结果","仅可明确NOT_EXECUTED或引用"],
];
labels.getRange("A4:C9").values = defs;
labels.getRange("A4:C9").format = { wrapText: true, verticalAlignment: "top", borders: { preset: "inside", style: "thin", color: border } };
for (let i=0;i<defs.length;i++) labels.getRange(`A${i+4}`).format = { fill: labelColors[defs[i][0]], font: { bold: true, color: navy } };
labels.getRange("A:A").format.columnWidth = 29; labels.getRange("B:C").format.columnWidth = 45;
labels.getRange("A4:C9").format.autofitRows(); labels.freezePanes.freezeRows(3);

guide.showGridLines = false;
guide.getRange("A1:D1").merge(); guide.getRange("A1").values = [["Split Decision Control Panel"]];
guide.getRange("A1:D1").format = { fill: navy, font: { bold: true, color: "#FFFFFF", size: 15 }, rowHeight: 30 };
guide.getRange("A3:B9").values = [
 ["Control", "Workbook formula / interpretation"],
 ["Duplication-risk rows", null], ["Cannot-repeat rows", null], ["Paper 1 primary rows", null], ["Paper 2 primary rows", null],
 ["Hard rule", "Same frozen result can be primary in only one paper."],
 ["Decision", "If Paper 2 lacks independent Stage 04 evidence, merge or keep Paper 1 only."],
];
guide.getRange("B4").formulas = [["=COUNTIF('Overlap Matrix'!B5:C17,\"DUPLICATION_RISK\")"]];
guide.getRange("B5").formulas = [["=COUNTIF('Overlap Matrix'!B5:C17,\"CANNOT_REPEAT\")"]];
guide.getRange("B6").formulas = [["=COUNTIF('Overlap Matrix'!B5:C17,\"PAPER_1_PRIMARY\")"]];
guide.getRange("B7").formulas = [["=COUNTIF('Overlap Matrix'!B5:C17,\"PAPER_2_PRIMARY\")"]];
guide.getRange("A3:B3").format = { fill: navy, font: { bold: true, color: "#FFFFFF" } };
guide.getRange("A4:B9").format = { wrapText: true, verticalAlignment: "top", borders: { preset: "inside", style: "thin", color: border } };
guide.getRange("A4:A9").format = { fill: pale, font: { bold: true, color: navy } };
guide.getRange("A:A").format.columnWidth = 30; guide.getRange("B:B").format.columnWidth = 75;
guide.getRange("A4:B9").format.autofitRows(); guide.freezePanes.freezeRows(3);

const buildDir = `${out}/.build/xlsx_preview`;
await fs.mkdir(buildDir, { recursive: true });
for (const name of ["Overlap Matrix", "Label Definitions", "Decision Guide"]) {
  const img = await wb.render({ sheetName: name, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(`${buildDir}/${name.replaceAll(" ", "_")}.png`, new Uint8Array(await img.arrayBuffer()));
}
const inspection = await wb.inspect({ kind: "sheet,formula,region", maxChars: 7000, tableMaxRows: 20, tableMaxCols: 6 });
await fs.writeFile(`${out}/13_manifests/cross_paper_overlap_workbook_inspection.json`, JSON.stringify(inspection, null, 2));
const xlsx = await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(`${out}/09_publication_options/cross_paper_overlap_matrix.xlsx`);
console.log(JSON.stringify({output:`${out}/09_publication_options/cross_paper_overlap_matrix.xlsx`, sheets:3, rows:rows.length}));
