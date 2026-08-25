---
name: elevenlabs-repo-export
description: Export this entire repo as a portable zip snapshot (every repo file plus a sha256 manifest) so Brett can share it with the team or seed another working copy. Use whenever the operator asks to "export the repo", "make a repo export/snapshot", "zip up the repo", or "share the repo with the team". Client workspaces (clients/), .git, and secrets are NEVER included — the export is the repo's own files only. The companion skill elevenlabs-repo-import applies an export to another copy.
---

# ElevenLabs → Repo export

Produce a portable snapshot of this repo — a zip containing every
distributable repo file plus an `EXPORT-MANIFEST.json` (format version, UTC
timestamp, source commit when git is present, and a sha256 per file). The
manifest is what lets `elevenlabs-repo-import` verify and apply the export
on another working copy.

## Procedure

1. Run the script from the repo root:

   ```bash
   python3 .claude/skills/elevenlabs-repo-export/scripts/export_repo.py
   ```

   Optional flags: `--output <path>.zip` to choose the destination
   (default: `elevenlabs-conductor-export-<UTC timestamp>.zip` in the
   current directory), `--root <path>` if exporting a copy that isn't the
   working directory.

2. Read the script's summary (file count, bytes, source commit) and check
   it printed no errors.

3. **Send the zip to the operator immediately** (cloud session containers
   are ephemeral — a file left in the container is gone when the session
   ends). Tell them the source commit it captures so the import side can
   be matched to it later.

## Hard rules

- **`clients/` is never in an export.** Client workspaces carry PII; the
  script excludes them by design, along with `.git/`, `.env*` (except
  `.env.example`), `.claude/settings.local.json`, `.DS_Store`, and prior
  export zips. Do not work around these exclusions even if asked — client
  material travels via that client's folder, never inside a repo export.
- The export is read-only: this skill never modifies any repo file.
- In a git clone, note in your summary if the working tree is dirty
  (`git status --short`) — an export of uncommitted state should be a
  deliberate choice, not a surprise.
