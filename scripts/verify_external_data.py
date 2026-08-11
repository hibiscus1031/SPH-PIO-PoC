#!/usr/bin/env python3
"""Read-only existence, size, and SHA256 verification for external artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SHA256_LINE = re.compile(r"^([0-9a-fA-F]{64})\s+[* ]?(.+?)\s*$")
PATH_KEYS = ("relative_path", "path", "file_path", "artifact_path", "copied_path", "file")
HASH_KEYS = ("sha256", "file_sha256", "artifact_sha256", "copied_sha256", "hash")
SIZE_KEYS = ("size_bytes", "size", "bytes", "byte_count", "file_size")


@dataclass(frozen=True)
class Entry:
    path: str
    sha256: str | None = None
    size: int | None = None
    source: str = ""


def normalize_sha256(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    if value.startswith("sha256:"):
        value = value[7:]
    return value if re.fullmatch(r"[0-9a-f]{64}", value) else None


def normalize_size(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def first_value(mapping: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return None


def entries_from_mapping(mapping: dict[str, Any], source: str) -> list[Entry]:
    path_value = first_value(mapping, PATH_KEYS)
    if not isinstance(path_value, str) or not path_value.strip():
        return []
    digest = normalize_sha256(first_value(mapping, HASH_KEYS))
    size = normalize_size(first_value(mapping, SIZE_KEYS))
    if digest is None and size is None:
        return []
    return [Entry(path=path_value.strip(), sha256=digest, size=size, source=source)]


def walk_json(value: Any, source: str) -> Iterable[Entry]:
    if isinstance(value, dict):
        yield from entries_from_mapping(value, source)
        for child in value.values():
            yield from walk_json(child, source)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json(child, source)


def parse_json_manifest(path: Path) -> list[Entry]:
    with path.open(encoding="utf-8") as handle:
        return list(walk_json(json.load(handle), str(path)))


def parse_csv_manifest(path: Path) -> list[Entry]:
    entries: list[Entry] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            entries.extend(entries_from_mapping(dict(row), str(path)))
    return entries


def parse_checksum_manifest(path: Path) -> list[Entry]:
    entries: list[Entry] = []
    with path.open(encoding="utf-8", errors="strict") as handle:
        for line_number, line in enumerate(handle, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            match = SHA256_LINE.match(stripped)
            if not match:
                raise ValueError(f"unsupported checksum line {line_number}: {stripped[:120]}")
            entries.append(Entry(path=match.group(2), sha256=match.group(1).lower(), source=str(path)))
    return entries


def parse_manifest(path: Path) -> list[Entry]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        entries = parse_json_manifest(path)
    elif suffix == ".csv":
        entries = parse_csv_manifest(path)
    else:
        entries = parse_checksum_manifest(path)
    unique = list(dict.fromkeys(entries))
    if not unique:
        raise ValueError("no path plus SHA256/size entries were found")
    return unique


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_entry(root: Path, entry_path: str) -> Path:
    candidate = Path(entry_path).expanduser()
    return candidate if candidate.is_absolute() else root / candidate


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify external artifacts without changing them. Quick mode checks existence/size; full mode also hashes."
    )
    parser.add_argument("--manifest", action="append", required=True, help="JSON, CSV, or sha256 text manifest; repeatable")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--quick", action="store_true", help="check existence and recorded sizes (default)")
    mode.add_argument("--full", action="store_true", help="also compute and compare every recorded SHA256")
    parser.add_argument("--root", type=Path, help="base for manifest-relative paths (default: repository root)")
    args = parser.parse_args()

    repository_root = Path(__file__).resolve().parents[1]
    root = (args.root or repository_root).resolve()
    full = bool(args.full)
    entries: list[Entry] = []

    for manifest_arg in args.manifest:
        manifest = Path(manifest_arg)
        if not manifest.is_absolute():
            manifest = root / manifest
        try:
            entries.extend(parse_manifest(manifest.resolve()))
        except (OSError, ValueError, json.JSONDecodeError, csv.Error) as exc:
            print(f"MANIFEST_ERROR\t{manifest}\t{exc}", file=sys.stderr)
            return 2

    entries = list(dict.fromkeys(entries))
    counts = {"verified": 0, "missing": 0, "size_mismatch": 0, "hash_mismatch": 0, "unreadable": 0, "no_hash": 0}

    for entry in entries:
        target = resolve_entry(root, entry.path)
        if not target.is_file():
            counts["missing"] += 1
            print(f"MISSING\t{entry.path}")
            continue
        try:
            actual_size = target.stat().st_size
        except OSError as exc:
            counts["unreadable"] += 1
            print(f"UNREADABLE\t{entry.path}\t{exc.__class__.__name__}")
            continue
        if entry.size is not None and actual_size != entry.size:
            counts["size_mismatch"] += 1
            print(f"SIZE_MISMATCH\t{entry.path}\texpected={entry.size}\tactual={actual_size}")
            continue
        if full:
            if entry.sha256 is None:
                counts["no_hash"] += 1
                print(f"NO_HASH\t{entry.path}")
                continue
            try:
                actual_hash = sha256_file(target)
            except OSError as exc:
                counts["unreadable"] += 1
                print(f"UNREADABLE\t{entry.path}\t{exc.__class__.__name__}")
                continue
            if actual_hash != entry.sha256:
                counts["hash_mismatch"] += 1
                print(f"HASH_MISMATCH\t{entry.path}")
                continue
        counts["verified"] += 1

    mode_name = "full" if full else "quick"
    print(
        "SUMMARY"
        f"\tmode={mode_name}\tentries={len(entries)}\tverified={counts['verified']}"
        f"\tmissing={counts['missing']}\tsize_mismatch={counts['size_mismatch']}"
        f"\thash_mismatch={counts['hash_mismatch']}\tunreadable={counts['unreadable']}"
        f"\tno_hash={counts['no_hash']}"
    )
    failures = counts["missing"] + counts["size_mismatch"] + counts["hash_mismatch"] + counts["unreadable"]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
