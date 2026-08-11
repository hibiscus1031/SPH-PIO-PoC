#!/usr/bin/env python3
"""Cache open core-paper PDFs and extract auditable text for evidence notes."""

from __future__ import annotations

import concurrent.futures
import json
import urllib.request
from pathlib import Path

from pypdf import PdfReader


P2 = Path(__file__).resolve().parents[1]
CACHE = P2 / "evidence_notes/fulltext_cache"

SOURCES = {
    "M001": "https://raw.githubusercontent.com/mlresearch/v235/main/assets/toshev24a/toshev24a.pdf",
    "M002": "https://arxiv.org/pdf/2403.04750",
    "M003": "https://arxiv.org/pdf/2110.13311",
    "M004": "https://proceedings.neurips.cc/paper_files/paper/2023/file/ccac3b120c7dc86d45f56830732b62be-Paper-Datasets_and_Benchmarks.pdf",
    "M005": "https://proceedings.mlr.press/v119/sanchez-gonzalez20a/sanchez-gonzalez20a.pdf",
    "M006": "https://arxiv.org/pdf/1910.14324",
    "M007": "https://arxiv.org/pdf/1810.01566",
    "M008": "https://arxiv.org/pdf/2010.03409",
    "M009": "https://proceedings.neurips.cc/paper_files/paper/2020/file/43e4e6a6f341e00671e123714de019a8-Paper.pdf",
    "M010": "https://proceedings.mlr.press/v119/qiao20a/qiao20a.pdf",
    "M011": "https://proceedings.neurips.cc/paper_files/paper/2019/file/26cd8ecadce0d4efd6cc8a8725cbd1f8-Paper.pdf",
    "M012": "https://arxiv.org/pdf/2003.04630",
    "M013": "https://proceedings.mlr.press/v139/satorras21a/satorras21a.pdf",
    "M014": "https://arxiv.org/pdf/2110.02905",
    "M015": "https://arxiv.org/pdf/2308.07832",
    "RAW004": "https://www.nature.com/articles/s41467-025-67802-5.pdf",
    "RAW031": "https://arxiv.org/pdf/2502.15496",
    "RAW044": "https://proceedings.neurips.cc/paper_files/paper/2022/file/2dd7f33ffbb59b4ff987be5442a13016-Paper-Conference.pdf",
    "RAW077": "https://arxiv.org/pdf/2507.21684",
    "RAW114": "https://arxiv.org/pdf/2208.10848",
}


def download(item: tuple[str, str]) -> dict:
    sid, url = item
    pdf = CACHE / f"{sid}.pdf"
    txt = CACHE / f"{sid}.txt"
    try:
        if pdf.exists() and txt.exists():
            return {"source_record_id": sid, "url": url, "status": "PASS", "cached": True, "bytes": pdf.stat().st_size, "text_chars": txt.stat().st_size}
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 SPH-PIO-P2"})
        with urllib.request.urlopen(request, timeout=120) as response:
            data = response.read()
        if not data.startswith(b"%PDF"):
            raise ValueError(f"response is not PDF ({data[:20]!r})")
        pdf.write_bytes(data)
        reader = PdfReader(pdf)
        pages = [(page.extract_text() or "") for page in reader.pages]
        txt.write_text("\n\n".join(f"--- PAGE {i+1} ---\n{text}" for i, text in enumerate(pages)), encoding="utf-8")
        return {"source_record_id": sid, "url": url, "status": "PASS", "bytes": len(data), "pages": len(pages), "text_chars": sum(map(len, pages))}
    except Exception as exc:
        return {"source_record_id": sid, "url": url, "status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        audit = list(pool.map(download, SOURCES.items()))
    (CACHE / "fulltext_cache_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": sum(x["status"] == "PASS" for x in audit), "fail": [x for x in audit if x["status"] == "FAIL"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
