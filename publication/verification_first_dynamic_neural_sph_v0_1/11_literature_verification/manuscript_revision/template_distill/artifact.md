# P2 DOCX template contract

## Reference

- Retained reference: `/Users/xiejinbo/Documents/SPH-PIO-PoC/publication/verification_first_dynamic_neural_sph_v0_1/03_manuscript_cn/manuscript_cn_v0_1.docx`
- SHA-256: `ec1a14660495b002f6b96c491acd39c2f590c6258a0cd71424a97db6c1531231`
- Pages: 16; sections: 1.
- Render evidence: `reference_render/page-1.png` through `reference_render/page-16.png`.
- Structural evidence: `section_audit.txt`, `style_evidence.json`.

## Page system

- US Letter portrait, 8.5 × 11 in.
- Margins: 1.0 in on all sides; header/footer distance: 0.492 in.
- One section; no distinct first/odd/even header.
- Running header: project and manuscript version, muted 8.5 pt, bottom rule.
- Running footer: track label plus right-aligned PAGE field, muted 9 pt.

## Typography and components

- Visual system: the P1 `narrative_proposal` token map encoded in the retained DOCX.
- Latin font: Calibri. Body: 11 pt, justified, 1.333 lines, 8 pt after.
- Heading 1: 16 pt blue `#2E74B5`, 18 pt before, 10 pt after.
- Heading 2: 13 pt blue `#2E74B5`, 12 pt before, 6 pt after.
- Heading 3: 12 pt dark blue `#1F4D78`, 8 pt before, 4 pt after.
- Cover: centered gold track kicker, navy Chinese title, dark-blue subtitle, muted English line, red qualification warning callout.
- Figure-design callouts: pale-gray fill, blue left border, compact caption.
- Tables: fixed 9360 DXA width, 120 DXA indent, repeated filled header, 80/120/80/120 DXA cell margins; rows must not split.

## Named override

- `CJK_RENDER_REPAIR`: P1 requests `Heiti SC`, but the verified headless render replaces many Chinese glyphs with boxes and ignores both the East Asia slot and macOS system CJK fonts under an isolated LibreOffice profile. P2 therefore writes the open `Source Han Sans CN` family to `ascii`, `hAnsi` and `eastAsia` for all runs/styles and renders with `SAL_FONTPATH=/Users/xiejinbo/.cache/babeldoc/fonts`, while preserving size, color, weight and spacing tokens. This override is required for legible Chinese and must be applied consistently to body, headings, tables, cover, header and footer.

## Content flow and slot map

1. Cover: version changes from P1/v0.1 to P2/v0.2 and title becomes literature-positioned.
2. Static top-level contents page: same component pattern; page values may remain a headless-safe index.
3. Manuscript body: source is `manuscript_cn_v0_2_literature_positioned.md`; all scientific sections are editable, with numerical evidence and qualification states preserved.
4. Introduction and Discussion: replace P1 literature placeholders with verified `[Vxxx]` citations and bounded positioning.
5. References: replace placeholder reference paragraph with the 40-record verified core bibliography.
6. Data/code/author/conflict statements: preserve P1 evidence boundaries; no repository, author or conflict facts may be invented.

Stable locators are the ordered body stream, Word heading styles, table nodes, figure-design paragraph prefix, header/footer parts and PAGE field. No content controls, footnotes, drawings or external relationships are used.

## Package preservation and fidelity gates

- The retained reference remains byte-for-byte unchanged.
- Preserve one-section page geometry, color hierarchy, fixed-width table geometry, header/footer pattern, PAGE field, update-fields setting, title/callout components and body rhythm.
- New DOCX is built from a working copy of the reference and replaces the editable body stream while retaining the reference styles and section properties.
- Required visual gates: every output page rendered; no missing Chinese glyphs, clipping, overlaps, orphaned table headers, broken tables, placeholder `REF-TODO`, or internal `CLAIM` comments.
- Required evidence gates: `288/288`, `540/540`, `216/360`, `144`, topology event, `NOT_QUALIFIED`, `NOT_EXECUTED` and `NOT_TESTED` remain visible where scientifically relevant.
