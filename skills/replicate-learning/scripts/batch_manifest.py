#!/usr/bin/env python3
"""Small, language-neutral source manifest for resumable teaching batches."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def source_path(root: Path, relative: str) -> Path:
    base = root.resolve()
    path = (base / relative).resolve()
    if not path.is_relative_to(base) or path == base:
        raise ValueError(f"path outside project: {relative}")
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest(root: Path, files: list[str]) -> dict:
    base = root.resolve()
    entries = {}
    for relative in files:
        path = source_path(base, relative)
        key = path.relative_to(base).as_posix()
        entries[key] = {"sha256": digest(path), "bytes": path.stat().st_size}
    if not entries:
        raise ValueError("at least one source file is required")
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=base, text=True, capture_output=True, check=False
    )
    return {
        "schema_version": 1,
        "source_root": str(base),
        "source_revision": revision.stdout.strip() if revision.returncode == 0 else None,
        "files": dict(sorted(entries.items())),
    }


def changed_files(manifest: dict, root: Path) -> list[str]:
    changed = []
    for relative, recorded in manifest["files"].items():
        try:
            actual = digest(source_path(root, relative))
        except (FileNotFoundError, ValueError):
            changed.append(relative)
            continue
        if actual != recorded["sha256"]:
            changed.append(relative)
    return sorted(changed)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or verify a source evidence manifest")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--src", required=True, type=Path)
    prepare.add_argument("--file", action="append", required=True)
    prepare.add_argument("--out", required=True, type=Path)
    check = sub.add_parser("check")
    check.add_argument("--src", required=True, type=Path)
    check.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if args.command == "prepare":
        data = build_manifest(args.src, args.file)
        if args.out.exists():
            raise SystemExit("manifest already exists; choose a new batch path")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"prepared {len(data['files'])} source files: {args.out}")
        return 0
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    if Path(data["source_root"]).resolve() != args.src.resolve():
        print("FAIL: source root differs from manifest")
        return 1
    changed = changed_files(data, args.src)
    if changed:
        print("FAIL: source files changed: " + ", ".join(changed))
        return 1
    print(f"PASS: {len(data['files'])} source files match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
