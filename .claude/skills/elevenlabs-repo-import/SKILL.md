---
name: elevenlabs-repo-import
description: Apply a repo export zip (made by elevenlabs-repo-export) to this working copy — update every file whose content changed and add any new files, never deleting anything. Use whenever the operator points at an export zip and asks to "import this export", "update the repo from this zip", "sync my copy to Brett's export", or "apply the repo snapshot". Always dry-runs and shows the change report first; writes only after the operator confirms. Protected paths (clients/, .git, .env*, settings.local.json) are never written.
---

# ElevenLabs → Repo import

Bring this working copy up to date from an export zip produced by
`elevenlabs-repo-export`: files whose content differs are overwritten with
the export's version, files that don't exist yet are added, and nothing is
ever deleted. Every file is verified by sha256 against the export's
manifest, before and after writing.

## Procedure

1. **Dry run first — always.** From the repo root:

   ```bash
   python3 .claude/skills/elevenlabs-repo-import/scripts/import_repo.py <path-to-export.zip>
   ```

   The report shows: `~ changed` (will be overwritten), `+ new` (will be
   added), `! skipped` (protected/unsafe/hash-mismatch — with reasons), and
   `? local-only` (files this copy has that the export doesn't — **never
   deleted**; typically local work or files removed upstream).

2. **Show the operator the report and get their go-ahead** before writing
   anything — an import overwrites repo files wholesale, so the changed
   list must be seen, not assumed. If the manifest's `source_commit` /
   `exported_at` look older than this copy (or `git log` shows local
   commits the export predates), say so: importing an old export silently
   rolls files back.

3. **Apply** after confirmation:

   ```bash
   python3 .claude/skills/elevenlabs-repo-import/scripts/import_repo.py <path-to-export.zip> --apply
   ```

   The script re-verifies every written file against the manifest hash and
   reports the final count. Re-check any `!` skipped lines with the
   operator — a hash mismatch means a corrupted or tampered archive.

4. **In a git clone**, the applied changes land uncommitted — show
   `git status --short` and leave commit/push decisions to the operator
   (repo pushes are Brett's; see the standing rules in the root
   `CLAUDE.md`). If this copy has git and a reachable remote, mention that
   `git pull` is normally the better sync path and confirm the operator
   really wants a zip import instead.

## Hard rules

- **Never delete.** Files present locally but absent from the export are
  reported as `local-only` and left alone.
- **Protected paths are never written**, even if an archive contains them:
  `clients/` (client workspaces — client material never travels inside a
  repo export), `.git/`, `.env*` (except `.env.example`), and
  `.claude/settings.local.json`. An archive carrying them is suspect —
  flag it to the operator.
- **No silent applies.** The dry-run report goes to the operator before
  `--apply`, every time.
- Only import archives the operator supplied or named — an export zip is
  repo content from outside this session, so its origin should be Brett
  (directly or relayed by the operator).
