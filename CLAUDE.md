# elevenlabs-skills — standing rules (every session)

This repo exists for exactly one thing: building and maintaining ElevenLabs
ConvAI voice agents for PHMG clients through its skills and subagents.
Assume any task in this workspace is ElevenLabs work unless it is clearly
about the repo's own files.

## Route ALL ElevenLabs work through the skills — never inline

Anything that touches an ElevenLabs agent — reading it, analyzing it,
configuring it, debugging a call, editing a prompt/workflow/procedure/
tool/KB — goes through the skills, invoked with the Skill tool BEFORE any
ElevenLabs connector tool call:

- **`elevenlabs-architect`** — builds, audits, improvements, "configure/
  improve this agent", building from a meeting transcript.
- **`elevenlabs-engineer`** — post-deployment maintenance: a specific
  conversation went wrong, or a batch of client feedback needs triaging.

The skills dispatch the read-only analyzers and the write configurators in
`.claude/agents/` as subagents — that is the point of the repo, not an
optional flourish. Do NOT call the `mcp__ElevenLabs__*` connector tools
inline from the main thread, do NOT hand-roll `curl` against the ConvAI API
(there is no API key — see below), and do NOT do a configurator's job
inline. A task that feels small enough to do inline is exactly the case
this rule exists for. This is a standing user instruction: for ElevenLabs
work, Brett has already asked, permanently — no session-level default about
waiting to be told to use the Agent/Task tool applies here.

This rule fires even when the prompt never says "ElevenLabs": a client
name, an agent/conversation/branch id, a complaint about a call, or a
feedback file are all ElevenLabs work. (The `UserPromptSubmit` hook in
`hooks/elevenlabs-skill-guard.py` re-injects this reminder whenever a
prompt contains an ElevenLabs id or keyword — but this file is the rule;
the hook is reinforcement.)

If a request genuinely falls outside the skills, say so and get Brett's
agreement first — do not silently go direct.

## House rules that hold even on a one-line change

- Stage every change on a **Sandbox branch** — never write to Main, never
  merge; Brett promotes changes manually.
- **All client memory lives in the client's folder, never in this repo.**
  Every client gets their own folder, `clients/<client-slug>/` (the whole
  `clients/` tree is git-ignored). That folder holds a `CLAUDE.md` — the
  client-journey memory: agent ids, build history, key decisions, current
  state, standing constraints. Read it (and the `feedback-ledger-*.md`)
  before any work on that client — Staged/Reopened ledger rows are
  constraints, and apparent duplication may be a deliberate
  defence-in-depth fix — and update the `CLAUDE.md` at the end of every
  run. Create both files on first contact if they don't exist.
- **The repo's own files are Brett-gated.** House docs (`docs/`), skills,
  subagents, and hooks are binding conventions, and no session, skill, or
  agent edits them (or opens a PR against this repo) on its own. When work
  surfaces a needed repo change — a doc is wrong, a default keeps biting —
  write the proposal (what to change, why, evidence) to
  `<client-folder>/repo-change-proposals.md` and tell the operator to send
  it to Brett; Brett applies and pushes repo changes himself. No answer
  means no.
- **ElevenLabs auth is the connector, not a key.** All ElevenLabs access
  runs through the ElevenLabs connector MCP tools (`mcp__ElevenLabs__*`),
  authorized on the claude.ai account per `docs/authentication.md`. There
  is no `ELEVENLABS_API_KEY` anywhere — never ask for one, never store one,
  never fall back to `curl` against `api.elevenlabs.io`. Every connector
  call's required `context` parameter gets one task-describing line, never
  secrets or client PII.
- **Naming convention (Brett, 2026-08-15): every skill and subagent in this
  repo starts with `elevenlabs-`** — including ones for adjacent tooling in
  the ElevenLabs pipeline (e.g. `elevenlabs-n8n-office-schedule`). Name new
  ones accordingly; rename on sight if one slips through.
