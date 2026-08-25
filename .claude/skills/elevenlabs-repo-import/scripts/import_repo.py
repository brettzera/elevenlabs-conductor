#!/usr/bin/env python3
"""Apply an elevenlabs-repo-export zip to this working copy.

Compares every file in the archive against the working copy by sha256 and
reports four categories:
  changed    — exists locally with different content → will be overwritten
  new        — not present locally → will be added
  identical  — already matches → untouched
  local-only — exists locally but not in the archive → NEVER deleted,
               listed so the operator can decide what they are

Default is a dry run (report only). Pass --apply to write the changed and
new files; every write is re-verified against the manifest hash.

NEVER written, even if present in an archive (protected paths):
  clients/ (client workspaces), .git/, .env* (except .env.example),
  .claude/settings.local.json.

Usage:
  python3 import_repo.py ARCHIVE.zip [--root REPO_ROOT] [--apply]
"""

import argparse
import hashlib
import json
import os
import sys
import zipfile

MANIFEST_NAME = "EXPORT-MANIFEST.json"
SUPPORTED_FORMAT = 1
EXCLUDE_DIRS = {".git", "clients", "__pycache__", "node_modules"}
EXCLUDE_BASENAMES = {".DS_Store"}
EXPORT_PREFIX = "elevenlabs-conductor-export-"


def is_protected(rel_path: str) -> bool:
    parts = rel_path.split("/")
    if parts[0] in (".git", "clients"):
        return True
    base = parts[-1]
    if base.startswith(".env") and base != ".env.example":
        return True
    if rel_path == ".claude/settings.local.json":
        return True
    return False


def is_unsafe(rel_path: str) -> bool:
    if not rel_path or rel_path.endswith("/"):
        return True
    if rel_path.startswith(("/", "\\")) or ":" in rel_path.split("/")[0]:
        return True
    return any(p in ("..", "") for p in rel_path.split("/"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def local_files(root: str):
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        rel_dir = "" if rel_dir == "." else rel_dir.replace(os.sep, "/")
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for name in filenames:
            rel = f"{rel_dir}/{name}" if rel_dir else name
            base = rel.split("/")[-1]
            if base in EXCLUDE_BASENAMES or is_protected(rel):
                continue
            if base.startswith(EXPORT_PREFIX) and base.endswith(".zip"):
                continue
            found.append(rel)
    return set(found)


def main() -> int:
    default_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archive", help="export zip produced by elevenlabs-repo-export")
    ap.add_argument("--root", default=default_root, help="working copy to update")
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"ERROR: root not found: {root}", file=sys.stderr)
        return 1
    if not os.path.isfile(args.archive):
        print(f"ERROR: archive not found: {args.archive}", file=sys.stderr)
        return 1

    with zipfile.ZipFile(args.archive) as zf:
        names = set(zf.namelist())
        manifest = None
        if MANIFEST_NAME in names:
            manifest = json.loads(zf.read(MANIFEST_NAME))
            if manifest.get("format_version") != SUPPORTED_FORMAT:
                print(f"ERROR: unsupported manifest format {manifest.get('format_version')}", file=sys.stderr)
                return 1
            entries = {e["path"]: e for e in manifest["files"]}
        else:
            print("WARNING: no EXPORT-MANIFEST.json — deriving file list from the zip itself")
            entries = {n: {"path": n} for n in names if not n.endswith("/")}

        changed, new, identical, skipped = [], [], [], []
        for rel in sorted(entries):
            if is_unsafe(rel):
                skipped.append((rel, "unsafe path"))
                continue
            if is_protected(rel):
                skipped.append((rel, "protected path"))
                continue
            if rel not in names:
                skipped.append((rel, "listed in manifest but missing from zip"))
                continue
            data = zf.read(rel)
            digest = sha256_bytes(data)
            expected = entries[rel].get("sha256")
            if expected and expected != digest:
                skipped.append((rel, "zip content does not match manifest hash"))
                continue
            dest = os.path.join(root, rel)
            if os.path.isfile(dest):
                (identical if sha256_file(dest) == digest else changed).append(rel)
            else:
                new.append(rel)

        print(f"Import report — archive: {os.path.basename(args.archive)}")
        if manifest:
            print(f"  exported_at: {manifest.get('exported_at')}  source_commit: {manifest.get('source_commit')}")
        print(f"  changed: {len(changed)}  new: {len(new)}  identical: {len(identical)}  skipped: {len(skipped)}")
        for rel in changed:
            print(f"  ~ {rel}")
        for rel in new:
            print(f"  + {rel}")
        for rel, why in skipped:
            print(f"  ! {rel} ({why})")
        extra = sorted(local_files(root) - set(entries))
        if extra:
            print(f"  local-only (never deleted): {len(extra)}")
            for rel in extra:
                print(f"  ? {rel}")

        if not args.apply:
            print("\nDry run — nothing written. Re-run with --apply to update the working copy.")
            return 0

        failures = []
        for rel in changed + new:
            dest = os.path.join(root, rel)
            os.makedirs(os.path.dirname(dest) or root, exist_ok=True)
            data = zf.read(rel)
            with open(dest, "wb") as f:
                f.write(data)
            mode = entries[rel].get("mode")
            if mode:
                os.chmod(dest, int(mode, 8))
            if sha256_file(dest) != sha256_bytes(data):
                failures.append(rel)

    if failures:
        print(f"\nERROR: post-write verification failed for {len(failures)} file(s): {failures}", file=sys.stderr)
        return 1
    print(f"\nApplied: {len(changed)} updated, {len(new)} added — all writes verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
