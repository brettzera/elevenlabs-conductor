#!/usr/bin/env python3
"""Export this repo as a portable zip with a hash manifest.

Produces <output>.zip containing every distributable repo file plus an
EXPORT-MANIFEST.json (format version, UTC timestamp, source commit when
git is present, and a sha256 per file). The companion skill
elevenlabs-repo-import consumes this archive to update another working
copy of the repo.

NEVER included, by design (client PII / secrets / local state):
  clients/ (all client workspaces), .git/, .env* (except .env.example),
  .claude/settings.local.json, .DS_Store, __pycache__/, node_modules/,
  and prior export zips.

Usage:
  python3 export_repo.py [--root REPO_ROOT] [--output OUT.zip]
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timezone

MANIFEST_NAME = "EXPORT-MANIFEST.json"
FORMAT_VERSION = 1
EXCLUDE_DIRS = {".git", "clients", "__pycache__", "node_modules"}
EXCLUDE_BASENAMES = {".DS_Store"}
EXPORT_PREFIX = "elevenlabs-conductor-export-"


def is_excluded(rel_path: str) -> bool:
    parts = rel_path.split("/")
    if any(p in EXCLUDE_DIRS for p in parts[:-1]) or parts[0] in EXCLUDE_DIRS:
        return True
    base = parts[-1]
    if base in EXCLUDE_BASENAMES:
        return True
    if base.startswith(".env") and base != ".env.example":
        return True
    if rel_path == ".claude/settings.local.json":
        return True
    if base.startswith(EXPORT_PREFIX) and base.endswith(".zip"):
        return True
    return False


def git_ls_files(root: str):
    try:
        # --others --exclude-standard adds untracked-but-not-ignored files,
        # so an export captures the tree "as it is now", not just HEAD.
        out = subprocess.run(
            ["git", "-C", root, "ls-files", "--cached", "--others", "--exclude-standard"],
            capture_output=True, text=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return [line for line in out.splitlines() if line.strip()]


def walk_files(root: str):
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        rel_dir = "" if rel_dir == "." else rel_dir.replace(os.sep, "/")
        dirnames[:] = [
            d for d in dirnames
            if d not in EXCLUDE_DIRS and not is_excluded(f"{rel_dir}/{d}" if rel_dir else d)
        ]
        for name in filenames:
            rel = f"{rel_dir}/{name}" if rel_dir else name
            if not is_excluded(rel):
                found.append(rel)
    return found


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    default_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=default_root, help="repo root to export")
    ap.add_argument("--output", default=None, help="output zip path")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"ERROR: root not found: {root}", file=sys.stderr)
        return 1

    files = git_ls_files(root)
    source = "git ls-files"
    if files is None:
        files = walk_files(root)
        source = "filesystem walk (no git)"
    # Belt and braces: the exclusion rules apply even to git-tracked paths.
    files = sorted(f for f in set(files) if not is_excluded(f) and os.path.isfile(os.path.join(root, f)))
    if not files:
        print("ERROR: nothing to export", file=sys.stderr)
        return 1

    commit = None
    try:
        commit = subprocess.run(
            ["git", "-C", root, "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        pass

    stamp = datetime.now(timezone.utc)
    out_path = args.output or os.path.join(
        os.getcwd(), f"{EXPORT_PREFIX}{stamp.strftime('%Y%m%d-%H%M%S')}.zip"
    )

    manifest = {
        "format_version": FORMAT_VERSION,
        "exported_at": stamp.isoformat(timespec="seconds"),
        "source_commit": commit,
        "file_source": source,
        "file_count": len(files),
        "files": [
            {
                "path": f,
                "sha256": sha256_of(os.path.join(root, f)),
                "size": os.path.getsize(os.path.join(root, f)),
                "mode": oct(os.stat(os.path.join(root, f)).st_mode & 0o777),
            }
            for f in files
        ],
    }

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(os.path.join(root, f), f)
        zf.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2))

    total = sum(e["size"] for e in manifest["files"])
    print(f"Exported {len(files)} files ({total} bytes) from {root}")
    print(f"Source: {source}" + (f", commit {commit[:12]}" if commit else ""))
    print(f"Archive: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
