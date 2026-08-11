#!/usr/bin/env python3
"""Collect reproducible raw candidates for P2 from Crossref REST."""

from __future__ import annotations

import csv
import json
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path


P2 = Path(__file__).resolve().parents[1]
OUT = P2 / "raw_candidates"
LOG_DIR = P2 / "search_protocol"
SEARCH_DATE = "2026-08-05"
ROWS = 15

QUERIES = {
    "T1": [
        "smoothed particle hydrodynamics neural correction",
        "machine learning enhanced SPH solver",
        "differentiable smoothed particle hydrodynamics",
        "graph neural network SPH fluid",
        "data driven smoothed particle hydrodynamics",
    ],
    "T2": [
        "learned particle simulator graph network",
        "Lagrangian fluid simulation graph neural network",
        "message passing particle fluid simulator",
        "particle based neural operator fluid dynamics",
        "long horizon particle rollout simulator",
    ],
    "T3": [
        "momentum conserving neural network particle dynamics",
        "antisymmetric message passing conservation",
        "equivariant graph neural network particle dynamics",
        "Hamiltonian graph neural network dynamics",
        "pairwise conservative force learning",
    ],
    "T4": [
        "differentiable physics solver gradient verification finite difference",
        "differentiable CFD automatic differentiation verification",
        "solver in the loop differentiable physics",
        "adjoint tangent linear gradient verification",
        "multistep automatic differentiation physics solver",
    ],
    "T5": [
        "differentiable neighbor search particles",
        "dynamic graph differentiation topology",
        "cutoff discontinuity particle simulation",
        "piecewise differentiable simulation topology events",
        "differentiable contact simulation discontinuity",
    ],
    "T6": [
        "verification validation trustworthy scientific machine learning",
        "credibility assessment scientific machine learning",
        "code verification ML augmented solver",
        "manufactured solutions learned PDE solver",
        "reporting standards machine learning based science",
    ],
    "T7": [
        "SPH verification manufactured solutions",
        "smoothed particle hydrodynamics convergence consistency",
        "weakly compressible SPH Taylor Green verification",
        "SPH numerical validation reference hierarchy",
        "grand challenges smoothed particle hydrodynamics schemes",
    ],
}


def get_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "SPH-PIO-PoC-P2/1.0 (literature verification; Crossref REST)"},
    )
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response)


def first_date(item: dict) -> str:
    for key in ("published-print", "published-online", "published", "issued"):
        parts = item.get(key, {}).get("date-parts", [])
        if parts and parts[0]:
            vals = list(parts[0]) + [1, 1]
            return f"{vals[0]:04d}-{vals[1]:02d}-{vals[2]:02d}"
    return ""


def author_text(item: dict) -> str:
    names = []
    for author in item.get("author", []):
        full = " ".join(x for x in [author.get("given", ""), author.get("family", "")] if x).strip()
        if full:
            names.append(full)
    return "; ".join(names)


def normalize(item: dict, theme: str, query: str, rank: int) -> dict:
    title = " ".join(item.get("title") or []).strip()
    container = " ".join(item.get("container-title") or []).strip()
    doi = (item.get("DOI") or "").lower()
    return {
        "candidate_id": "",
        "themes": theme,
        "discovery_queries": query,
        "best_rank": rank,
        "title": title,
        "authors": author_text(item),
        "published_date": first_date(item),
        "year": (first_date(item) or "")[:4],
        "venue": container,
        "volume": item.get("volume", ""),
        "issue": item.get("issue", ""),
        "pages_or_article": item.get("page") or item.get("article-number") or "",
        "doi": doi,
        "crossref_type": item.get("type", ""),
        "publisher": item.get("publisher", ""),
        "crossref_url": f"https://api.crossref.org/works/{urllib.parse.quote(doi)}" if doi else "",
        "publisher_url": item.get("URL", ""),
        "discovery_source": "Crossref REST",
        "metadata_status": "RAW_CANDIDATE",
    }


def merge(existing: dict, incoming: dict) -> None:
    existing["themes"] = ";".join(sorted(set(existing["themes"].split(";")) | set(incoming["themes"].split(";"))))
    qs = existing["discovery_queries"].split(" || ")
    if incoming["discovery_queries"] not in qs:
        qs.append(incoming["discovery_queries"])
    existing["discovery_queries"] = " || ".join(qs)
    existing["best_rank"] = min(int(existing["best_rank"]), int(incoming["best_rank"]))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    records: dict[str, dict] = {}
    logs: list[dict] = []
    query_hits: dict[tuple[str, str], list[str]] = defaultdict(list)
    for theme, queries in QUERIES.items():
        for query in queries:
            params = urllib.parse.urlencode({
                "query.bibliographic": query,
                "rows": ROWS,
                "filter": "until-pub-date:2026-08-05",
                "select": "DOI,title,author,published,published-print,published-online,issued,container-title,volume,issue,page,article-number,type,publisher,URL",
            })
            url = "https://api.crossref.org/works?" + params
            try:
                payload = get_json(url)["message"]
                items = payload.get("items", [])
                total = payload.get("total-results", 0)
                error = ""
            except Exception as exc:
                items, total, error = [], 0, f"{type(exc).__name__}: {exc}"
            retained_this_query = 0
            for rank, item in enumerate(items, 1):
                row = normalize(item, theme, query, rank)
                key = row["doi"] or (row["title"].casefold() + "|" + row["year"])
                if not key.strip("|"):
                    continue
                if key in records:
                    merge(records[key], row)
                else:
                    records[key] = row
                query_hits[(theme, query)].append(key)
                retained_this_query += 1
            logs.append({
                "search_date": SEARCH_DATE,
                "database_source": "Crossref REST API",
                "theme": theme,
                "exact_query": query,
                "endpoint": url,
                "reported_result_count": total,
                "screened_count": len(items),
                "retained_raw_count": retained_this_query,
                "rejection_reasons": "none at discovery stage; deduplication tracked globally",
                "error": error,
            })
            time.sleep(0.12)

    ordered = sorted(records.values(), key=lambda r: (int(r["best_rank"]), r["title"].casefold()))
    for idx, row in enumerate(ordered, 1):
        row["candidate_id"] = f"RAW{idx:03d}"
    fields = list(ordered[0].keys()) if ordered else []
    with (OUT / "raw_candidate_bibliography.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(ordered)
    (OUT / "raw_candidate_bibliography.json").write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (LOG_DIR / "search_query_log.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(logs[0].keys()))
        writer.writeheader()
        writer.writerows(logs)
    print(json.dumps({"query_count": len(logs), "raw_unique_candidates": len(ordered), "errors": [x for x in logs if x["error"]]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
