import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const base = new URL("..", import.meta.url).pathname;
const input = `${base}direct_competitors/direct_competitor_matrix.json`;
const output = `${base}direct_competitors/direct_competitor_matrix.xlsx`;
const previewDir = `${base}direct_competitors/xlsx_preview`;
const records = JSON.parse(await fs.readFile(input, "utf8"));

const fields = [
  "citation_id", "title", "source_record_id", "SPH_baseline",
  "correction_or_replacement", "static_or_dynamic", "local_or_global",
  "architecture", "temporal_memory", "hard_linear_momentum",
  "angular_momentum", "energy", "zero_correction_identity",
  "reference_hierarchy", "MMS", "AD_FD", "multistep_gradient",
  "topology_event_audit", "training", "autonomous_rollout",
  "independent_validation", "equal_error_cost", "negative_result_reporting",
];
const compact = [
  "citation_id", "title", "correction_or_replacement", "architecture",
  "temporal_memory", "hard_linear_momentum", "AD_FD",
  "multistep_gradient", "topology_event_audit", "negative_result_reporting",
];

const wb = Workbook.create();
const overview = wb.worksheets.add("Positioning");
const full = wb.worksheets.add("Full Matrix");
const guide = wb.worksheets.add("Field Guide");

function titleBlock(sheet, title, subtitle, endCol) {
  sheet.getRange(`A1:${endCol}1`).merge();
  sheet.getRange("A1").values = [[title]];
  sheet.getRange("A1").format = {
    fill: "#17365D", font: { bold: true, color: "#FFFFFF", size: 16 },
    horizontalAlignment: "left", verticalAlignment: "center",
  };
  sheet.getRange("A1").format.rowHeight = 30;
  sheet.getRange(`A2:${endCol}2`).merge();
  sheet.getRange("A2").values = [[subtitle]];
  sheet.getRange("A2").format = {
    fill: "#E8EEF5", font: { color: "#344054", italic: true }, wrapText: true,
  };
  sheet.getRange("A2").format.rowHeight = 34;
}

function styleHeader(range) {
  range.format = {
    fill: "#2E74B5", font: { bold: true, color: "#FFFFFF" },
    wrapText: true, verticalAlignment: "center", horizontalAlignment: "center",
    borders: { bottom: { color: "#17365D", style: "thin" } },
  };
  range.format.rowHeight = 42;
}

titleBlock(
  overview,
  "Direct competitor positioning matrix",
  "Verified literature only · cutoff 2026-08-05 · NOT_REPORTED / NOT_VERIFIED are preserved as evidence states",
  "J",
);
overview.getRange("A4:J14").values = [
  compact,
  ...records.map((r) => compact.map((k) => r[k] ?? "NOT_REPORTED")),
];
styleHeader(overview.getRange("A4:J4"));
overview.freezePanes.freezeRows(4);
overview.tables.add("A4:J14", true, "PositioningTable");
overview.getRange("A5:J14").format = { wrapText: true, verticalAlignment: "top" };
overview.getRange("A5:A14").format = { fill: "#E8EEF5", font: { bold: true, color: "#17365D" }, horizontalAlignment: "center" };
overview.getRange("F5:F14").conditionalFormats.addCustom('=F5="YES"', { fill: "#EAF5EF", font: { color: "#166534", bold: true } });
overview.getRange("G5:I14").conditionalFormats.addCustom('=G5="NOT_REPORTED"', { fill: "#F2F4F7", font: { color: "#667085" } });
overview.getRange("A:A").format.columnWidth = 11;
overview.getRange("B:B").format.columnWidth = 42;
overview.getRange("C:C").format.columnWidth = 20;
overview.getRange("D:D").format.columnWidth = 18;
overview.getRange("E:E").format.columnWidth = 19;
overview.getRange("F:F").format.columnWidth = 17;
overview.getRange("G:I").format.columnWidth = 18;
overview.getRange("J:J").format.columnWidth = 24;
overview.getRange("5:14").format.rowHeight = 56;

titleBlock(
  full,
  "Full direct competitor evidence matrix",
  "All required comparison fields; values are bounded to verified reporting and do not infer absence from non-reporting",
  "W",
);
full.getRange("A4:W14").values = [
  fields,
  ...records.map((r) => fields.map((k) => r[k] ?? "NOT_REPORTED")),
];
styleHeader(full.getRange("A4:W4"));
full.freezePanes.freezeRows(4);
full.freezePanes.freezeColumns(3);
full.tables.add("A4:W14", true, "FullEvidenceTable");
full.getRange("A5:W14").format = { wrapText: true, verticalAlignment: "top" };
full.getRange("A5:A14").format = { fill: "#E8EEF5", font: { bold: true, color: "#17365D" }, horizontalAlignment: "center" };
full.getRange("A:A").format.columnWidth = 11;
full.getRange("B:B").format.columnWidth = 44;
full.getRange("C:C").format.columnWidth = 14;
full.getRange("D:W").format.columnWidth = 19;
full.getRange("5:14").format.rowHeight = 72;

const descriptions = {
  SPH_baseline: "Role and form of any SPH baseline or SPH-derived component.",
  correction_or_replacement: "Whether learning corrects a retained solver or replaces its state update.",
  hard_linear_momentum: "Explicit hard linear-momentum structure; non-reporting is not treated as failure.",
  angular_momentum: "Explicit angular-momentum result or NOT_REPORTED / NOT_VERIFIED.",
  zero_correction_identity: "Executable identity against the uncorrected baseline when correction is exactly zero.",
  AD_FD: "Direct automatic-differentiation / finite-difference comparison.",
  multistep_gradient: "Evidence covering temporal unrolling beyond one step.",
  topology_event_audit: "Explicit birth/death or equivalent discrete-neighborhood event audit.",
  equal_error_cost: "Accuracy-cost comparison at equal error or an explicitly comparable operating point.",
  negative_result_reporting: "Visibility of failed, unresolved or adverse outcomes.",
};
const guideRows = fields.map((f) => [f, descriptions[f] ?? "Comparison field retained from the P2 verification protocol."]);
titleBlock(guide, "Field guide and interpretation contract", "Unknown states must remain explicit; do not convert NOT_REPORTED into NO", "B");
guide.getRange(`A4:B${guideRows.length + 4}`).values = [["Field", "Interpretation"], ...guideRows];
styleHeader(guide.getRange("A4:B4"));
guide.tables.add(`A4:B${guideRows.length + 4}`, true, "FieldGuideTable");
guide.freezePanes.freezeRows(4);
guide.getRange(`A5:B${guideRows.length + 4}`).format = { wrapText: true, verticalAlignment: "top" };
guide.getRange("A:A").format.columnWidth = 30;
guide.getRange("B:B").format.columnWidth = 80;
guide.getRange(`5:${guideRows.length + 4}`).format.rowHeight = 38;

await fs.mkdir(previewDir, { recursive: true });
for (const [sheetName, fileName, range, scale] of [
  ["Positioning", "positioning.png", "A1:J14", 1],
  ["Full Matrix", "full_matrix.png", "A1:W14", 0.65],
  ["Field Guide", "field_guide.png", `A1:B${guideRows.length + 4}`, 0.9],
]) {
  const blob = await wb.render({ sheetName, range, scale, format: "png" });
  await fs.writeFile(`${previewDir}/${fileName}`, new Uint8Array(await blob.arrayBuffer()));
}

const xlsx = await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(output);
const inspection = await wb.inspect({ kind: "workbook,sheet,table", maxChars: 5000, tableMaxRows: 4, tableMaxCols: 6 });
console.log(JSON.stringify({ output, sheets: 3, records: records.length, inspection }, null, 2));
