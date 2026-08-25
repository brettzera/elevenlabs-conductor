# elevenlabs-skills

A [Claude Code](https://claude.ai/code) workspace for building and maintaining
[ElevenLabs Conversational AI](https://elevenlabs.io/conversational-ai) voice
agents for PHMG clients. It packages the whole pipeline — requirements
gathering, agent configuration, post-deployment maintenance — as two
orchestrating skills backed by a fleet of focused subagents.

## How it works

Open this repo in Claude Code and the skills and subagents load automatically.
Two skills drive everything:

- **`elevenlabs-architect`** (`.claude/skills/elevenlabs-architect/`) — builds
  or improves an agent end-to-end. It extracts requirements from a client
  meeting transcript (or audits an existing agent), interviews the user
  feature by feature, then dispatches the write configurators to stage every
  change on a **Sandbox branch** for human review.
- **`elevenlabs-engineer`** (`.claude/skills/elevenlabs-engineer/`) — the
  post-deployment counterpart. It turns human feedback — a single bad call or
  a bulk feedback dump (Forms export, client email, meeting transcript) — into
  diagnosed, staged fixes, one issue at a time, and records every issue in a
  per-agent **feedback ledger** so nothing gets rediscovered from scratch.

Both skills orchestrate rather than configure: the heavy lifting is done by
the subagents in `.claude/agents/`.

## The subagents

**Read-only (diagnose, never write):**

| Agent | Purpose |
| --- | --- |
| `elevenlabs-agent-analyzer` | Full feature inventory of an existing agent's config |
| `elevenlabs-requirements-extractor` | Meeting transcript → configuration-requirements report |
| `elevenlabs-conversation-reviewer` | Diagnoses a specific call against user feedback |
| `elevenlabs-feedback-triage` | Bulk feedback → de-duplicated, routed pain-point list |

**Write configurators (each owns one feature area; drafts freely, PATCHes a
live agent only when explicitly authorized):**

| Agent | Owns |
| --- | --- |
| `elevenlabs-persona-configurator` | Name, first message, language, system prompt |
| `elevenlabs-knowledge-configurator` | Knowledge base docs, RAG settings |
| `elevenlabs-conversation-flow-configurator` | Workflows/branches, dynamic variables |
| `elevenlabs-procedures-configurator` | Procedures (step-by-step task definitions) |
| `elevenlabs-tools-escalation-configurator` | System/custom tools, transfers, MCP wiring |
| `elevenlabs-voice-tts-configurator` | Voice selection and TTS tuning |
| `elevenlabs-llm-tuning-configurator` | LLM choice, temperature, backup LLM |
| `elevenlabs-capture-delivery-configurator` | Data collection, post-call webhooks, analysis |
| `elevenlabs-quality-safety-configurator` | Evaluation criteria, guardrails, privacy/retention |
| `elevenlabs-runtime-qa-configurator` | Turn/ASR/VAD timing, monitoring, phone numbers |
| `elevenlabs-dictionary-agent` | Pronunciation dictionaries (drafts rules for the UI; attaches locators via the connector) |
| `elevenlabs-calcom-setup` | Cal.com scheduling: verifies the Cal.com side, hands Brett the UI checklist for the per-client connection + calcom_* tool set, verifies the result (never touches existing agents/tools) |
| `elevenlabs-test-runner` | Caller-profile test suites and simulations |

## House rules (the short version)

1. **Sandbox-first.** Changes to an existing agent are staged on a Sandbox
   branch that is not taking live traffic. Main is never PATCHed directly and
   Sandbox is never merged by automation — a human promotes changes in the
   ElevenLabs UI. (Brand-new agents build on Main once, then follow the same
   discipline.)
2. **One agent / one issue at a time.** Builds and fixes run strictly
   sequentially, with a human check-in between each.
3. **No API key, anywhere.** ElevenLabs access runs through the
   **ElevenLabs connector** MCP tools (`mcp__ElevenLabs__*`), authorized once
   on the claude.ai account per
   [docs/authentication.md](docs/authentication.md) — sessions never see a
   credential at all, so there is nothing to leak, echo, or commit. Read-only
   subagents carry read-only tool rosters, so analysis literally cannot
   write.
4. **Evidence-driven.** Configurators only run for features the requirements
   or diagnostic reports actually call for; no upselling unused features.
5. **Brett-gated defaults.** House defaults change only through a reviewed
   lesson PR — see [docs/cross-client-lessons.md](docs/cross-client-lessons.md)
   and [`.github/CODEOWNERS`](.github/CODEOWNERS).
6. **Three-surface architecture (HL-003).** On workflow agents the prompt
   holds persona + universal rules and defers, verbatim, to the workflow
   ("Refer to the workflow."); nodes route and name their procedures;
   procedures carry the granular questioning — see
   [docs/workflow-patterns.md](docs/workflow-patterns.md) § Surface ownership.

## The routing hook

The skills only help if they actually get invoked, so routing is enforced on
two layers — neither requires telling Claude anything:

1. **`CLAUDE.md`** (repo root) loads automatically in every session and
   states the standing rule: all ElevenLabs work goes through the skills and
   subagents — never inline connector-tool calls, never raw `curl` — even
   when the prompt never says "ElevenLabs".
2. **`hooks/elevenlabs-skill-guard.py`** is a `UserPromptSubmit` hook that
   re-injects that rule on exactly the prompts where it matters: any
   ElevenLabs resource id (`agent_…`, `conv_…`, `agtbrch_…`, `agtvrsn_…`,
   `agtprc_…`, `tool_…`, `test_…`, `phnum_…`, `icxn_…`), any ElevenLabs
   keyword, or house vocabulary that implies ElevenLabs work (feedback
   ledger, voice agent, caller profile, sandbox branch, pronunciation
   dictionary, …). It stays silent — and free — on every unrelated prompt.

The hook ships pre-wired in this repo's
[`.claude/settings.json`](.claude/settings.json), so it loads automatically
whenever the repo is opened in a Claude Code cloud session — no per-machine
setup. Verify it from inside a session with:

```bash
echo '{"prompt":"look at agent_0000example0000example0000"}' \
  | python3 hooks/elevenlabs-skill-guard.py
```

That should print a JSON blob; an unrelated prompt should print nothing.

**Why it exists.** On 2026-08-08 a full layer-dedup pass on a client
agent (CL-A) was done entirely by hand — correct config work, but it skipped the
client's feedback ledger and de-duplicated away a rule that ledger row FB-011
had placed deliberately, as a structural fix after three logged
false-confirmation failures. The API calls were never the hard part; the
surrounding discipline is. A per-client `CLAUDE.md` and an operator memory are
useful reinforcements, but only the hook fires regardless of working directory.

## Cloud-only operation

This repo runs **exclusively in Claude Code cloud sessions**
(claude.ai/code) — there is no local-machine or zip-download mode. The
cloud environment provides everything a run needs:

- **ElevenLabs access** — the ElevenLabs connector is connected once on
  the claude.ai account (Settings → Connectors) and its MCP tools
  (`mcp__ElevenLabs__*`) attach to every session automatically; see
  [docs/authentication.md](docs/authentication.md). The repo's
  `.claude/settings.json` pre-allows the read-only tools so audits and
  diagnoses run without permission prompts; writes still prompt.
- **The hook** — wired via the repo's `.claude/settings.json`, active in
  every session automatically.
- **Lesson PRs** — every session has git and GitHub access, so the
  house-default approval channel (lesson PRs for Brett's review) runs
  directly from any session.

One consequence to remember: session containers are **ephemeral**. Repo
changes worth keeping (doc fixes, lessons) must be committed and pushed
before the session ends — a file left uncommitted in the container is gone
when the container is reclaimed. Client-workspace artifacts (`clients/` —
ledgers, reports) are git-ignored for PII reasons and therefore do NOT
survive the session on their own: before ending a session whose ledger or
reports matter, have Claude send you the files (or paste the ledger delta
somewhere durable) so the next session can be re-seeded with them.

## Repository layout

```
.claude/
  skills/    elevenlabs-architect, elevenlabs-engineer (orchestrators)
  agents/    17 subagents (read-only analyzers + write configurators)
hooks/
  elevenlabs-skill-guard.py      UserPromptSubmit hook — routes any ElevenLabs
                                 id/keyword back through the skills (see The routing hook)
docs/
  authentication.md              Connector-based auth policy (no API key) + Cal.com env-var secrets
  house-persona.md               Baseline persona traits for every agent
  latency-playbook.md            Fast-by-default latency & pacing reference
  cross-client-lessons.md        Candidate observations + approved house lessons
  workflow-patterns.md           Topic-web pattern for multi-topic agents + pinned workflow API schema
  time-of-day-routing.md         Office-status webhook runbook: n8n + ElevenLabs steps, verification, 424 troubleshooting
  architect-subagent-roadmap.md  Subagent roster and workflow design
.github/CODEOWNERS               All changes require Brett's review
```

Client workspaces live in `clients/<client-slug>/` inside the repo clone,
one folder per client/agent (per [docs/authentication.md](docs/authentication.md)). All
per-client artifacts — requirements and feature-inventory reports, failure
reports, feedback ledgers, test results, exported agent configs — go in that
client's folder, never loose elsewhere. The whole `clients/` tree is
git-ignored because those artifacts can carry client PII — which, combined
with ephemeral session containers, means they do NOT persist across cloud
sessions on their own; see the note under Cloud-only operation.
