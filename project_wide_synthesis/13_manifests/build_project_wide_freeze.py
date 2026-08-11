#!/usr/bin/env python3
"""Create a read-only, project-wide historical-input freeze manifest."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT_ROOT = ROOT / "project_wide_synthesis"
OUT = OUT_ROOT / "00_freeze" / "project_wide_input_freeze_manifest.json"

EXCLUDED_PARTS = {
    ".git", ".pytest_cache", "__pycache__", ".mypy_cache", ".ruff_cache",
    ".tox", ".venv", "venv", "node_modules", ".DS_Store",
}
EXCLUDED_PREFIXES = ("rendered", "renders", "render_", ".tmp", "tmp", "temp")
BACKUP_RE = re.compile(r"(^|[._-])(backup|bak|copy|old)([._-]|$)", re.I)
MACHINE_SUFFIXES = {
    ".json", ".jsonl", ".csv", ".tsv", ".yaml", ".yml", ".toml", ".xml",
    ".npy", ".npz", ".pt", ".pth", ".ckpt", ".parquet", ".pkl", ".pickle",
}
TEXT_SUFFIXES = {
    ".md", ".txt", ".rst", ".py", ".sh", ".zsh", ".yaml", ".yml", ".toml",
    ".json", ".jsonl", ".csv", ".tsv", ".xml", ".tex", ".bib", ".ris", ".enw",
}


def run(*args: str) -> str:
    return subprocess.run(args, cwd=ROOT, check=True, text=True, capture_output=True).stdout.strip()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_ref(value: str, manifest_parent: Path) -> str | None:
    value = value.strip().replace("\\", "/")
    if not value or "\n" in value or len(value) > 1000:
        return None
    candidates: list[Path] = []
    p = Path(value)
    if p.is_absolute():
        candidates.append(p)
    else:
        candidates.extend((ROOT / p, manifest_parent / p))
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            rel = resolved.relative_to(ROOT.resolve()).as_posix()
            if resolved.is_file():
                return rel
        except (OSError, ValueError):
            pass
    return None


def walk_values(obj: Any):
    if isinstance(obj, dict):
        for value in obj.values():
            yield from walk_values(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk_values(value)
    elif isinstance(obj, str):
        yield obj


def manifest_refs(manifests: list[Path]) -> tuple[dict[str, list[str]], list[dict[str, str]]]:
    reverse: dict[str, list[str]] = {}
    parse_failures: list[dict[str, str]] = []
    for path in manifests:
        rel_manifest = path.relative_to(ROOT).as_posix()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            parse_failures.append({"path": rel_manifest, "error": type(exc).__name__})
            continue
        for value in walk_values(data):
            ref = normalize_ref(value, path.parent)
            if ref:
                reverse.setdefault(ref, []).append(rel_manifest)
    for refs in reverse.values():
        refs.sort()
    return reverse, parse_failures


def excluded(rel: Path, referenced: set[str]) -> bool:
    rels = rel.as_posix()
    # S1 audits the historical chain only through Stage 03D-S.  Stage 04 is a
    # future decision-input boundary and is represented solely by the new,
    # schema-only interface under project_wide_synthesis/11_stage04_update_interface.
    if rel.parts and rel.parts[0].startswith("stage_04"):
        return True
    if rels in referenced:
        return False
    parts = rel.parts
    if any(part in EXCLUDED_PARTS for part in parts):
        return True
    if parts and parts[0] == "project_wide_synthesis":
        return True
    if any(part.lower().startswith(EXCLUDED_PREFIXES) for part in parts):
        return True
    if BACKUP_RE.search(rel.name):
        return True
    if rel.name.startswith(".~lock.") or rel.name.endswith(("~", ".swp", ".tmp")):
        return True
    return False


def stage_of(rel: str) -> str:
    p = rel.lower()
    if p.startswith("publication/"):
        return "PUBLICATION"
    if p.startswith("stage_01") or "stage_01" in p:
        return "STAGE_01"
    if p.startswith("stage_02") or "stage_02" in p:
        return "STAGE_02"
    if p.startswith("stage_03") or "stage_03" in p:
        return "STAGE_03"
    if p.startswith("stage_04") or "stage_04" in p:
        return "STAGE_04_INTERFACE_INPUT"
    if p.startswith("00_environment"):
        return "STAGE_00"
    if p.startswith(("01_solver/", "02_data/", "03_models/", "04_training/", "05_metrics/", "06_experiments/", "07_reports/", "tests/")):
        return "SHARED_OR_STAGE_00_01"
    return "PROJECT_SHARED"


def role_of(rel: str) -> str:
    p = rel.lower()
    suffix = Path(rel).suffix.lower()
    if "manifest" in p or "checksum" in p or "hash" in p:
        return "manifest_or_integrity_record"
    if "report" in p or suffix in {".md", ".docx", ".pdf"}:
        return "human_readable_report_or_document"
    if "test" in p or p.startswith("tests/"):
        return "test_or_verification_code"
    if suffix in {".py", ".sh", ".zsh"}:
        return "source_or_execution_code"
    if suffix in {".png", ".jpg", ".jpeg", ".svg", ".tif", ".tiff", ".pdf"}:
        return "figure_or_visual_asset"
    if suffix in {".pt", ".pth", ".ckpt"}:
        return "checkpoint_binary_metadata_only"
    if suffix in MACHINE_SUFFIXES:
        return "machine_readable_evidence"
    return "supporting_artifact"


def is_final_evidence(rel: str) -> bool:
    p = rel.lower()
    keys = ("final", "qualification", "adjudication", "closure", "readiness", "decision", "summary", "manifest", "audit")
    return any(key in p for key in keys) and Path(rel).suffix.lower() in TEXT_SUFFIXES | {".docx", ".pdf", ".xlsx"}


def git_status_excluding_outputs() -> list[str]:
    lines = run("git", "status", "--short", "--untracked-files=all").splitlines()
    return [line for line in lines if "project_wide_synthesis/" not in line]


def main() -> None:
    all_paths = [p for p in ROOT.rglob("*") if p.is_file()]
    manifest_paths = [
        p for p in all_paths
        if p.suffix.lower() == ".json" and "manifest" in p.name.lower()
        and "project_wide_synthesis" not in p.parts
        and ".git" not in p.parts
        and not p.relative_to(ROOT).parts[0].startswith("stage_04")
    ]
    reverse_refs, parse_failures = manifest_refs(manifest_paths)
    referenced = set(reverse_refs)
    selected: list[Path] = []
    exclusions: dict[str, int] = {}
    for path in all_paths:
        rel = path.relative_to(ROOT)
        if excluded(rel, referenced):
            reason = "cache_temp_backup_or_output"
            exclusions[reason] = exclusions.get(reason, 0) + 1
            continue
        selected.append(path)
    selected.sort(key=lambda p: p.relative_to(ROOT).as_posix())

    files = []
    total_bytes = 0
    for path in selected:
        rel = path.relative_to(ROOT).as_posix()
        stat = path.stat()
        total_bytes += stat.st_size
        try:
            digest = sha256(path)
            hash_state = "HASHED"
        except (PermissionError, OSError) as exc:
            digest = None
            hash_state = f"UNREADABLE:{type(exc).__name__}"
        files.append({
            "path": rel,
            "sha256": digest,
            "hash_state": hash_state,
            "size_bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "stage": stage_of(rel),
            "role": role_of(rel),
            "manifest_membership": reverse_refs.get(rel, []),
            "machine_readable": path.suffix.lower() in MACHINE_SUFFIXES,
            "final_evidence_candidate": is_final_evidence(rel),
            "superseded": False,
            "immutable_historical_input": True,
        })

    try:
        import torch  # type: ignore
        torch_version = torch.__version__
    except Exception as exc:
        torch_version = f"UNAVAILABLE:{type(exc).__name__}"

    by_stage: dict[str, int] = {}
    by_role: dict[str, int] = {}
    for item in files:
        by_stage[item["stage"]] = by_stage.get(item["stage"], 0) + 1
        by_role[item["role"]] = by_role.get(item["role"], 0) + 1

    payload = {
        "schema": "SPH-PIO-PoC.project-wide-freeze.v1",
        "workflow": "Cross-Stage Synthesis S1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "root": str(ROOT),
        "scope_rule": "read-only historical inputs through Stage 03D-S plus publication; Stage 04 historical tree and new outputs excluded",
        "git": {
            "head": run("git", "rev-parse", "HEAD"),
            "branch": run("git", "branch", "--show-current"),
            "tags_at_head": run("git", "tag", "--points-at", "HEAD").splitlines(),
            "status_before_freeze_excluding_new_output_tree": git_status_excluding_outputs(),
        },
        "environment": {
            "python": sys.version,
            "python_executable": sys.executable,
            "torch": torch_version,
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "selection": {
            "included_file_count": len(files),
            "included_total_bytes": total_bytes,
            "excluded_counts": exclusions,
            "manifest_files_scanned": len(manifest_paths),
            "manifest_parse_failures": parse_failures,
            "checkpoint_handling": "binary never loaded; only filesystem metadata and streaming SHA-256 read",
        },
        "counts_by_stage": dict(sorted(by_stage.items())),
        "counts_by_role": dict(sorted(by_role.items())),
        "files": files,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "files": len(files), "bytes": total_bytes, "git_head": payload["git"]["head"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
