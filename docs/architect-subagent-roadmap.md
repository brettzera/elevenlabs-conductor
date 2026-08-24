# ElevenLabs Architect — Subagent Roadmap

The **architect skill** runs in the main thread, interviews the user
feature by feature, and orchestrates the subagents below. Subagents do the heavy,
read-only analysis and the write configuration; the skill owns the conversation.
A second skill, the **engineer**, drives the post-deployment feedback loop —
turning a referenced call or a bulk feedback dump into fixes, reusing the same
configurators.

**Target: 14–15 subagents + 2 orchestrating skills.** (15 built — 12 build-side +
2 read-only maintenance agents + the `elevenlabs-test-runner`. Skills: `architect`
and `engineer` both built.)

## Guardrail (every write configurator)

Every write-capable configurator carries the same hard rule proven out on the
dictionary-agent:

> Creating/editing a draft config is always allowed. **Applying it to a live
> ElevenLabs agent is NOT — unless the instruction explicitly says to
> attach/apply/update that agent.** Read-only inspection is always allowed.

Read-only agents carry read/list connector tools only (no `agents_update`, no create/delete tools in their rosters) and never mutate anything.

**Write scope (every writer, no exceptions):** the ElevenLabs connector
can reach every agent in the workspace, so scope is enforced by behavior,
not by auth. A write may only ever target (a) the exact agent id given in
the dispatch, and (b) a Sandbox branch that is **not taking live traffic** —
verified before writing; if no Sandbox exists, create one first. The sole
exception is the first build of a brand-new agent, which lays its initial
version down on Main — and that exception expires the moment the first
version exists.

## House rule: ElevenLabs auth is the connector, never a key

All ElevenLabs access runs through the **ElevenLabs connector MCP tools**
(`mcp__ElevenLabs__…`), authorized once on the claude.ai account — there is
no API key in a `.env`, a file, the environment, a report, or git, and no
`curl` fallback. The canonical availability check, the first-run setup
flow, the connector's known coverage gaps, and the hard rules live in
[docs/authentication.md](authentication.md); every skill and agent follows
that file, and it supersedes the retired `docs/secrets.md` and any older
key/secret-manager/`.env` instruction anywhere. Client folders are pure
workspaces (standard layout: `clients/<client-slug>/` inside the repo
clone, gitignored wholesale because reports and ledgers carry client PII).

## House rule: fast by default

Every agent the pipeline builds targets sub-second response latency and a natural
speaking pace. The levers, fast defaults, and symptom-routing table live in
[docs/latency-playbook.md](latency-playbook.md) — the architect enforces the
checklist at hand-off (Phase 5), the analyzer runs the latency scan on audits,
the reviewer triages "it's slow" feedback with it, and each configurator carries
its own slice inline.

## Read-only / cross-cutting agents

| Status | Agent | Role |
|--------|-------|------|
| ✅ Built | `elevenlabs-agent-analyzer` | Read-only audit of one agent → feature-inventory report |
| ✅ Built | `elevenlabs-requirements-extractor` | Read client↔architect transcript → requirements report |
| ✅ Built | `elevenlabs-conversation-reviewer` | Read specific ElevenLabs call(s) — resolves "my last call"/"recent calls" via the conversations list, or explicit conversation ids — + human feedback → failure report tagged to the offending feature area |
| ✅ Built | `elevenlabs-feedback-triage` | Read bulk client feedback (Microsoft Forms spreadsheets CSV/XLSX, client emails, call/meeting transcripts) → discrete atomic pain points, each tagged to agent + feature area + severity + evidence quote + any referenced conversation id |

## Write configurators

| # | Status | Agent | Feature areas it owns |
|---|--------|-------|-----------------------|
| — | ✅ Built | `elevenlabs-dictionary-agent` | Pronunciation dictionaries (alias/phoneme, multi-branch) |
| 1 | ✅ Built | `elevenlabs-persona-configurator` | Identity (name, `first_message`, `language`) + system prompt |
| 2 | ✅ Built | `elevenlabs-llm-tuning-configurator` | `llm`, temperature, max_tokens, backup LLM, reasoning |
| 3 | ✅ Built | `elevenlabs-voice-tts-configurator` | `voice_id`, stability/speed, expressive_mode, model_id *(pairs with dictionary-agent)* |
| 4 | ✅ Built | `elevenlabs-knowledge-configurator` | KB docs + `usage_mode` + `rag.enabled` |
| 5 | ✅ Built | `elevenlabs-tools-escalation-configurator` | System tools + custom/server tools + MCP + transfers |
| 6 | ✅ Built | `elevenlabs-conversation-flow-configurator` | Workflows + branch logic + dynamic variables |
| 7 | ✅ Built | `elevenlabs-capture-delivery-configurator` | Data-collection fields/scopes + post-call webhook + analysis (topic/sentiment) |
| 8 | ✅ Built | `elevenlabs-quality-safety-configurator` | Evaluation criteria + guardrails/compliance + privacy/retention |
| 9 | ✅ Built | `elevenlabs-runtime-qa-configurator` | Turn/ASR/VAD timing + max_duration + monitoring/alerting + testing/simulation + phone numbers |
| 10 | ✅ Built | `elevenlabs-procedures-configurator` | Procedures (`procedures` — named step-by-step task definitions: verification, booking, message-taking sequences) *(pairs with conversation-flow: flow owns when/where the call goes, this owns how a task's steps run)* |

**Note on #9 (`elevenlabs-runtime-qa-configurator`):** deliberately a grab-bag. If runtime-timing and
QA/testing each grow heavy, split into two agents — otherwise keep merged.

## Maintenance & feedback loop (new)

Post-deployment maintenance reuses the write side entirely — **the 10 configurators own every
fix.** What's new is the *read/diagnose* side (turning a call or a feedback dump into "which
setting is wrong") and a testing loop. No new write machinery.

Two workflows, both driven by the new `elevenlabs-engineer` skill:

- **A — Single-conversation bug fix:** you reference a call (usually conversationally — "my last
  call", "recent calls" — sometimes an explicit conversation id) and give feedback. The
  `conversation-reviewer` fetches the call detail and correlates it against your feedback →
  failure report → the owning configurator stages the fix on the Sandbox branch →
  `test-runner` re-simulates the affected caller profile to confirm.
- **B — Bulk feedback triage:** you drop in bulk feedback (Forms spreadsheet, client email,
  transcript). `feedback-triage` splits it into atomic pain points. The engineer then works
  **one pain point at a time**, staging each as its own discrete, individually-summarized change
  set on the Sandbox branch, checking in with you between each. **No git PRs** — ElevenLabs has
  only Main/Sandbox branches, so isolation is per-pain-point sequencing + summaries, and you
  merge Sandbox → Main manually (same gate as the architect).

| Status | Agent | Role |
|--------|-------|------|
| ✅ Built | `elevenlabs-test-runner` | Turns the requirements report's `## Caller profiles` into a per-profile simulation test suite (each profile's expected handling → checkable criteria, plus an off-profile fallback case), runs it against a staged branch, and reports a pass/fail matrix with each failure mapped to its owning configurator — closing the build → stage → **test** → merge loop for the architect (Phase 4.5) and the fix → **confirm** loop for the engineer. Gated execution (drafting specs is free; creating tests / launching simulations requires an explicit run instruction; never touches live config). |

## House rule: standard persona traits live in `docs/house-persona.md`

The persona standard every agent starts from — naming, tone, universal
do-not-say, greeting shape, prompt skeleton, language defaults — lives in
[docs/house-persona.md](house-persona.md), not in any skill or agent body.
The `elevenlabs-persona-configurator` reads it before **every** draft (new
builds and fixes alike), applies the `Status: active` sections as the
baseline, layers the client brief on top, and flags — never silently
accepts — a brief that contradicts an active house trait. Sections still
`Status: unset` are inert. The file is a house default under the
cross-client-lessons guardrail: the pipeline may propose changes to it,
only Brett approves them, and Brett edits it directly whenever he likes.

## House rule: caller profiles drive routing, per-call checks, and tests

Terminology: a **caller profile** is a *type of caller* the client expects (new
patient, invoice-chaser, supplier…); **persona** always means the agent's own
identity — never mix the two. When a client meeting lists caller profiles, the
`requirements-extractor` captures them as a first-class `## Caller profiles`
report section (profile · how recognized · expected handling on every call ·
evidence), and the architect fans that section out three ways:

1. **Routing** — recognition → branch logic (`conversation-flow-configurator`).
2. **Per-call checks** — expected handling → evaluation criteria assessed on
   every real conversation (`quality-safety-configurator`).
3. **Pre-merge tests** — one simulation per profile, run against the staged
   branch before hand-off (`elevenlabs-test-runner`); the engineer re-runs the
   affected profile after each staged fix.

**Not new agents:** the feedback → root-cause *diagnosis* folds into the reviewer/triage outputs
(they already tag feature area) rather than a standalone mapper; and because fixes are
Sandbox-only (not git PRs), no config-snapshot/export agent is needed.

## House rule: the feedback ledger is the pipeline's memory

Feedback persists across runs in ONE append-only file per agent, living in the
client folder (never this repo — it carries evidence quotes):

```
<client-folder>/feedback-ledger-<agent-slug>.md
```

One `## <date> — Workflow A|B` section per engineer run; one row per issue with a
ledger-wide sequential id (`FB-001`, …): issue · feature area → configurator ·
severity · evidence quote (≤15 words) · conversation id · fix staged · test
result · **status** (`Staged` / `Promoted` / `Reopened` / `Parked` / `Queued`).
Status is the only cell a later run may edit in a prior row.

Ownership and flow — no new agent needed, the automation is baked into the
existing skills' phases:

- **`elevenlabs-engineer` writes it.** Reads it at run start, passes its path to
  the diagnostic subagent, appends a row after every worked issue (Phase 4), and
  closes out statuses at hand-off (Phase 5). `Queued` rows make interrupted
  Workflow B batches resumable.
- **`conversation-reviewer` / `feedback-triage` read it.** Each takes the ledger
  path as an optional input and flags matches: a `Staged` match usually means
  "the fix exists, it's just unmerged"; a `Promoted` match is a regression, so
  the next fix attempt must differ from the recorded one.
- **`elevenlabs-architect` reads it.** Before improving an existing agent, prior
  `Reopened`/repeat rows become constraints in the configurator dispatch briefs
  so a rebuild doesn't reintroduce a fixed complaint.

## House rule: cross-client learning is two-tier, and Brett gates tier two

Per-agent ledgers feed a repo-level file,
[docs/cross-client-lessons.md](cross-client-lessons.md), with a hard wall
between its tiers:

- **Candidate observations** (tier 1, automatic): the engineer distills any
  *generalizable* root cause — a house default, template value, or config
  pattern that would bite other clients — into a PII-free candidate row
  (evidence cited as client-slug + ledger FB-id only; the repo never holds
  quotes, conversation ids, or customer data). Candidates are signals: they
  change NOTHING about how agents are built or fixed.
- **Approved house lessons** (tier 2, Brett-gated): when the same
  feature-area pattern shows up at 2+ distinct clients (or one severe issue
  is clearly caused by a house default), the skill raises a written
  proposal — pattern, evidence, exact change, risk — through a **lesson
  pull request**: a `lesson/<slug>` branch carrying the proposed change,
  opened as a PR to `main` whose body is the proposal. **Brett's PR
  approval and merge is the approval** — the only channel, for everyone,
  Brett included; a chat "yes" never substitutes for the PR, it just means
  Brett merges immediately. Approved lessons become binding house defaults the architect
  folds into every relevant dispatch brief; rejected proposals (closed PRs)
  are recorded so they aren't re-proposed without new evidence. No skill or
  agent ever edits the Approved section, `latency-playbook.md`,
  template/configurator defaults, or skill instructions on its own
  initiative — no answer means no. The gate is mechanically enforced by
  `.github/CODEOWNERS` (Brett owns everything) plus branch protection on
  `main` requiring code-owner review — a one-time GitHub setting.

## Orchestrating skills

| Status | Component | Role |
|--------|-----------|------|
| ✅ Built | `elevenlabs-architect` (skill) | Interviews the user feature by feature, dispatches the analyzer + extractor to gather state, then hands each feature to its configurator |
| ✅ Built | `elevenlabs-engineer` (skill) | Feedback-driven maintenance: Workflow A (fix a bug from a referenced conversation via `conversation-reviewer`) and Workflow B (triage bulk feedback into pain points via `feedback-triage`, fix one at a time). Reuses the configurators + the sandbox-first / one-at-a-time / never-merge guardrails, mirroring the architect's Phase 3–4 branch discipline inline. |

## Open items / follow-ups

- [x] **Verified 2026-08-09 against a live client agent.** Branch create is `POST /v1/convai/agents/{agent_id}/branches` with `{name, description, parent_version_id, parent_branch_id}` (`parent_version_id` required, taken from the parent branch's `version_id`); the branches list needs `?include_archived=true`; a GET/PATCH without `?branch_id=` defaults to Main. The hedge in both skills' Phase 3 has been replaced with the pinned mechanics, also recorded in `docs/workflow-patterns.md`. The procedures write path was pinned the same week (branch-scoped draft → compile — see `elevenlabs-procedures-configurator.md`).

## Build order (suggested)

1. `elevenlabs-persona-configurator` — smallest, highest-frequency; validates the write-configurator pattern.
2. `elevenlabs-voice-tts-configurator` — pairs with the working dictionary-agent.
3. `elevenlabs-knowledge-configurator` — house rule (business facts live in the KB doc) makes this high-value.
4. `elevenlabs-tools-escalation-configurator`, `elevenlabs-capture-delivery-configurator` — the complex, high-leverage ones.
5. Remaining configurators.
6. `elevenlabs-architect` skill — once enough configurators exist to orchestrate.
7. `elevenlabs-conversation-reviewer` — unlocks Workflow A; smallest maintenance piece, validates the read-a-call pattern.
8. `elevenlabs-feedback-triage` — unlocks Workflow B's decomposition.
9. `elevenlabs-engineer` skill — once both maintenance read agents exist.
10. `elevenlabs-test-runner` (optional) — add when the reproduce → fix → confirm loop is worth automating.
