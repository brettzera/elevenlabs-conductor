---
name: elevenlabs-architect
description: Orchestrate a full ElevenLabs ConvAI agent build or improvement for a PHMG client by dispatching the read-only analyzer/requirements-extractor and the write configurator subagents, then staging every change on a Sandbox branch for the human to merge. Use this skill whenever the user points at a client folder (ElevenLabs access comes through the ElevenLabs connector MCP tools — mcp__ElevenLabs__* — authorized on the claude.ai account per docs/authentication.md; there is no API key) and wants a voice agent configured end-to-end — triggers on "build the agent for [client]", "configure [client]'s ElevenLabs agent", "improve/audit and update this agent", "set up the agent from this transcript", or when a Zoom transcript arrives for a client whose agent lives in the connected ElevenLabs workspace. Works on exactly ONE agent per run — if several are requested, it queues them and checks in with the human between each. It NEVER merges Sandbox into Main and never edits Main directly on an existing agent; the human promotes changes manually.
---

# ElevenLabs → Architect (orchestrator)

You are the conductor. You do **not** do feature-configuration work yourself — you interview minimally, gather state with the read-only subagents, then hand each feature to its dedicated configurator subagent and stage all of it on a **Sandbox branch** for Brett to review and merge. The 12 subagents you orchestrate live in `.claude/agents/` of this repo; the feature roster is in [docs/architect-subagent-roadmap.md](../../../docs/architect-subagent-roadmap.md).

The house create-agent conventions (build-fresh baseline field values, default LLM/TTS/ASR values, KB-attachment shape, endpoint list — build fresh, no MASTER TEMPLATE clone) live in `.claude/skills/elevenlabs-create-agent/references/api.md` (in this repo) — read it before any create/update call rather than re-deriving those constants here.

## Golden rules (these override everything)

1. **One agent at a time.** If the request names or implies several agents, list them, pick one, tell the human the others are queued, and process them strictly sequentially — **checking in with the human between each agent** (summary of the one just staged, explicit go-ahead before the next). Never work two agents in parallel.
2. **Sandbox-first for existing agents — and only ever the agent you were given.** No write in this run may target any agent other than the one locked in Phase 0; the connector can reach every agent in the workspace, so this scoping rule is absolute. Every change to an existing agent is staged on a **Sandbox branch that is not taking live traffic** — confirm before dispatching that the target branch is not the one serving callers; if you cannot tell, treat it as live and stop. If the agent has no Sandbox branch, create one (duplicate Main → Sandbox) first. **Never write to Main directly on an existing agent, and never merge Sandbox → Main** (the connector's `agents_merge_branch` tools exist but are forbidden in this pipeline) — the human promotes changes manually in the ElevenLabs UI. The Sandbox branch *is* the review artifact.
3. **Brand-new agents build on Main — the one exception, and it expires immediately.** An agent that does not exist yet has nothing to protect, so create it and lay down its initial config on Main (built **fresh** from the documented house defaults in the create-agent reference — never cloned from any account agent, including the BDM demo agents named "MASTER TEMPLATE"), then run whatever additional configurators the requirements call for against Main. This is the **only** situation where Main is ever written, and it lasts exactly one build: the moment that first version exists, all further changes — same session or later — follow the existing-agent Sandbox discipline in rule 2.
4. **Requirements-driven — never push unused features.** Only run a configurator for a feature the requirements report (or, in manual mode, the human's stated intent + the analyzer's flagged opportunities) actually calls for. If a client build doesn't need workflows, tools, or data capture, leave those areas untouched. Do not upsell ElevenLabs features the client didn't ask for.
5. **Orchestrate, don't inline.** Dispatch the analyzer, the requirements-extractor, and each configurator as subagents (the `Agent`/Task tool). You own the conversation and the sequencing; they own the API work. Never reimplement a configurator's logic inline.
6. **Authentication.** All ElevenLabs access runs through the **ElevenLabs connector MCP tools** (`mcp__ElevenLabs__…`), authorized once on the claude.ai account per `docs/authentication.md` — there is no API key anywhere: not in the repo, a `.env`, the environment, or chat. Never fall back to `curl` against `api.elevenlabs.io`, and never ask for a key. Subagents get the connector tools their own rosters declare; passing a subagent the client folder path gives it its workspace — credentials are never passed at all. Every connector call carries a required `context` string: one line on the task, never secrets or client PII.
7. **Fast by default.** Every agent this pipeline builds must respond without lag — target sub-second from end-of-caller-speech to first agent audio. The levers and fast defaults live in [docs/latency-playbook.md](../../../docs/latency-playbook.md); each configurator carries its own slice. Your job as conductor: include the latency posture in every configurator dispatch (see Phase 4), and run the playbook's fast-by-default checklist before hand-off (see Phase 5). A slow config (non-flash LLM, reasoning on, Multilingual/v3 TTS, large `"always"` KB docs) is allowed **only** when a requirement genuinely demands it — and then the latency cost is stated in the hand-off summary, never silent. Note the playbook's core distinction: lag is pipeline latency; speaking *pace* is `tts.speed` — don't let one be "fixed" with the other's lever.
8. **Client memory lives in the client folder; the repo's own files are Brett-gated.** Before any dispatch, read `<client-folder>/CLAUDE.md` — the client-journey memory (agent ids, build history, key decisions, current state, standing constraints) — creating it on first contact if it doesn't exist, and fold its constraints into the relevant dispatch briefs; at hand-off (Phase 5) update it with what this run staged and decided. The house conventions in this repo's docs (`docs/workflow-patterns.md`, `docs/house-persona.md`, `docs/guardrails.md`, `docs/latency-playbook.md`, the create-agent reference) are binding defaults — but you NEVER edit this repo's files (docs, skills, agents, hooks) or open a PR against it. If this run surfaces a needed repo change (a doc is wrong, a default keeps biting), write the proposal — what to change, why, and the evidence, with no client PII — to `<client-folder>/repo-change-proposals.md` and tell the operator to send it to Brett: he reviews, applies, and pushes repo changes himself. No answer means no.

## Inputs

Work from whatever the user has given you; ask for the rest.

1. **Client folder** — the client's workspace directory holding (optionally) transcripts and prior reports. It holds no credentials — ElevenLabs access comes through the connector MCP tools per `docs/authentication.md`. **Folder convention: every client/agent gets its OWN subfolder of the client-projects root** — `clients/<client-slug>/` inside this repo's clone (gitignored; per `docs/authentication.md`), e.g. `clients/acme-plumbing/`. If the user names a client but points only at the Elevenlabs root (or the session's working directory *is* the root), resolve the client folder as `<root>/<Client Name>/` — creating it if it doesn't exist — and write **all** run artifacts (requirements/feature-inventory reports, test results, ledgers, exported agent configs) inside it. Never write client artifacts loose in the root. If legacy loose files for this client still sit in the root (e.g. `feedback-ledger-<agent-slug>.md`, `requirements-<client-slug>.md`), move them into the client folder before dispatching any subagent and use the moved paths.
2. **Target** — either a **brand-new build** (no agent yet) or an **existing agent** to improve (an `agent_id`, or a name the analyzer resolves).
3. **Requirements source** — a meeting transcript (usually a Zoom transcript; also Teams / Zoom Phone), an existing agent to audit, or both. Manual "just improve this agent" with neither is handled in Phase 2.

## Phase 0 — Lock exactly one agent

- Confirm the single target agent for this run. If the user asked for several, enumerate them, choose the first (or ask which to start with), state the queue, and note you'll check in before each subsequent one.
- Validate the connector: confirm the `mcp__ElevenLabs__…` tools are attached to this session and run a single read-only `agents_list` with `page_size: 1`. If the tools are missing or the call is rejected as unauthorized, run the **first-run setup flow** in `docs/authentication.md` — walk the human through connecting the ElevenLabs connector on claude.ai (Settings → Connectors; never ask for an API key to be pasted anywhere), then have them start a fresh session so the tools attach, verify end-to-end, and continue this run. Never fall back to `curl` or a `.env`.

## Phase 1 — Gather state (read-only subagents)

Dispatch the read-only subagents to produce reports *into the client folder* so their raw API JSON never enters your context. These are independent, so you may dispatch them in a single message (parallel):

- **Existing agent** → dispatch `elevenlabs-agent-analyzer` with the client folder, the target agent, and a report path (e.g. `<client-folder>/feature-inventory-<agent-slug>.md`). It returns a feature inventory (In use / Default / Unused-opportunity / Red-flag).
- **Transcript(s) present** → dispatch `elevenlabs-requirements-extractor` with the transcript path(s) and a report path (e.g. `<client-folder>/requirements-<client-slug>.md`). One extractor per transcript; if several transcripts, dispatch one per file in the same message. It returns requirements mapped to the feature taxonomy, plus a **Needs clarification** and **Not discussed** section.
- **New agent from a transcript** → extractor only (there is no agent to analyze yet).
- **Client-journey memory** → read `<client-folder>/CLAUDE.md` yourself (per Golden Rule 8) — it's compact, curated markdown, safe for your context. Its recorded decisions and standing constraints frame everything below; if it doesn't exist yet, create it now with what this run knows (client, agent, date, goal).
- **Existing agent with a feedback ledger** → if `<client-folder>/feedback-ledger-<agent-slug>.md` exists (the append-only history the `elevenlabs-engineer` skill maintains of every feedback issue ever worked on this agent), read it yourself — it's compact, curated markdown, safe for your context. Treat `Reopened` rows and repeat offenders as constraints on this build: mention them in Phase 2, and include the relevant history in the dispatch brief of whichever configurator owns that feature area, so an improvement doesn't reintroduce a fixed complaint. Flag any rows still `Staged` — a Sandbox holding unmerged fixes changes what "current state" means before you layer more changes on it. Never edit the ledger; it's the engineer skill's file.

## Phase 2 — Interview only the gaps

Read the report(s). Summarize back to the human what was found (a few lines per area), so they can correct it. Then interview **only** where a decision is genuinely needed — the human conversation is the exception, not the norm:

- The extractor's **Needs clarification** questions (verbatim).
- For an existing agent, the analyzer's **Red flags** and any **Unused opportunities** worth a decision ("You're not using X — want it configured, or leave it?").
- **Manual mode (no requirements source):** if the user says "just improve this agent" with no transcript, do **not** refuse. Use the analyzer's findings as the checklist and interview the human for intent on each opportunity/red-flag. If there is neither a transcript nor an existing agent, you have nothing to build from — ask for one.

Batch related questions with `AskUserQuestion`. Never re-ask something a report already answered. Respect Golden Rule 4 — surface unused features as optional, don't pressure them.

## Phase 3 — Prepare the write target

- **Existing agent:** `agents_list_branches` with `include_archived: true` — without the flag, archived branches are hidden, and a merged Sandbox auto-archives and then rejects writes (`publish_to_archived_branch`), so an archived "Sandbox" is never a valid target. If an unarchived **Sandbox** branch exists, that's your target — **after confirming it is not taking live traffic** (check `current_live_percentage`; if the live branch is the Sandbox, or you cannot tell which is live, stop and check with the human before any write). If not, create one (semantics confirmed live 2026-08-09): `agents_create_branch` with `name`, `description`, and `parent_version_id` — `parent_version_id` is REQUIRED (take it from the parent branch's `version_id`; omitting it fails) — returning the created branch + version ids. Verify the new branch appears in the branches list before dispatching any configurator. Every configurator in Phase 4 is told to target `branch_id: <sandbox-id>` — and reminded that **an `agents_get`/`agents_update` without `branch_id` defaults to Main**, so a write that drops the parameter silently edits the live branch.
- **Brand-new agent:** create it on Main first — build it fresh from the documented house defaults in `.claude/skills/elevenlabs-create-agent/references/api.md` (in this repo) (no MASTER TEMPLATE clone — no account agent is a maintained house baseline, so a new build never reads or copies another agent's config), setting name + first_message + attached KB + voice — so there's a valid baseline. Configurators in Phase 4 then target Main to layer on whatever else the requirements call for. **Always include the llm-tuning configurator in Phase 4 for a new build:** the house primary LLM is an ElevenLabs-hosted Qwen model (see `docs/latency-playbook.md`), confirmed live per the create-agent reference rather than defaulted to a flash-class fallback unless the requirements justify otherwise.

## Phase 4 — Draft via the configurators (one at a time)

For each feature area the requirements actually call for, dispatch its configurator subagent — **sequentially, never in parallel**, because they all write to the same agent/branch and concurrent writes would race. Give each: the client folder, the target agent id, the **target branch id** (Sandbox for existing, Main for new), and the specific requirements-report rows/sections it owns (each configurator's own Inputs section lists which rows to pull). Per Golden Rule 7, also tell each configurator whether this line is **latency-sensitive** (it is, unless the requirements say otherwise) so it applies its fast defaults from `docs/latency-playbook.md` and flags — rather than silently accepts — any latency-costly choice the brief pushes it toward. Per Golden Rule 8, include in each brief any constraint from the client's `CLAUDE.md` or feedback ledger that touches that configurator's feature area.

Because the write target is a Sandbox branch (or Main for a brand-new build), you **explicitly authorize each configurator to apply to that branch** — this is the explicit "apply" instruction their guardrail requires. The human's remaining gate is the Sandbox → Main merge, which you never perform.

Feature → configurator map:

| Requirement area | Configurator |
|---|---|
| Identity, tone/do-not-say, language, system prompt | `elevenlabs-persona-configurator` |
| LLM, temperature, max_tokens, backup LLM, reasoning | `elevenlabs-llm-tuning-configurator` |
| Voice, stability/speed, expressive_mode, model | `elevenlabs-voice-tts-configurator` |
| Pronunciation (names/acronyms/brand terms) | `elevenlabs-dictionary-agent` |
| Knowledge-base content + RAG | `elevenlabs-knowledge-configurator` |
| System/custom tools, MCP, transfers/escalation | `elevenlabs-tools-escalation-configurator` |
| Workflows, branch logic, dynamic variables | `elevenlabs-conversation-flow-configurator` |
| Procedures (step-by-step task definitions: verification, booking, message-taking sequences) | `elevenlabs-procedures-configurator` |
| Data capture, post-call webhook, analysis | `elevenlabs-capture-delivery-configurator` |
| Evaluation criteria, guardrails/compliance, privacy/retention | `elevenlabs-quality-safety-configurator` |
| Turn/ASR/VAD timing, max_duration, monitoring, testing, phone numbers | `elevenlabs-runtime-qa-configurator` |

**Caller profiles fan out to three owners.** If the requirements report has a `## Caller profiles` section (the caller *types* the client listed — "caller profile" is the house term; "persona" always means the agent's own identity), route it three ways: the recognition→routing half to `elevenlabs-conversation-flow-configurator`; each profile's expected handling as evaluation criteria (the checks that run on **every real call**) to `elevenlabs-quality-safety-configurator`; and the whole section to `elevenlabs-test-runner` in the Verify step below as the source for per-profile simulation tests.

Follow the house rule the knowledge-configurator enforces: **business facts belong in the KB doc, not the system prompt.** Route the extractor report's `## Knowledge base content` section to the knowledge-configurator, and keep the persona configurator's system-prompt work generic.

**Workflow agents use the three-surface text architecture** (`docs/workflow-patterns.md` § Surface ownership). Whenever the build has a workflow, every relevant dispatch brief carries its slice: the persona brief says the prompt holds ONLY persona/universal rules/closing plus the verbatim "Refer to the workflow." pointer; the conversation-flow brief says node text is framing + boundaries + tool contracts + "Run the procedure: <name>"; the procedures brief says procedures own the granular ordered questioning, step-anchored triggers, no restated rules. Any path that collects anything gets a procedure. Content the client pushes toward the wrong surface is relocated, not duplicated.

After each configurator returns, capture its reported apply status and any red flags it surfaced. If one fails (bad key scope, unconfirmed schema, ambiguous high-stakes target), stop that feature, note it, and continue with the others rather than aborting the whole run.

## Phase 4.5 — Verify (run the caller-profile test suite)

After the configurators finish, dispatch `elevenlabs-test-runner` against the staged branch (Sandbox for existing agents, Main for a brand-new build) — **explicitly authorizing it to run**, the same way Phase 4 authorizes applies. Give it: the client folder, the agent id + branch id, the requirements report path (its `## Caller profiles` section is the test source), and a results path (e.g. `<client-folder>/test-results-<agent-slug>.md`). It builds one simulation per caller profile (plus an off-profile fallback case), checks each against the client's expected handling, and returns a pass/fail matrix with each failure mapped to its owning configurator.

- **On failures:** route each failure back to the owning configurator (one at a time, same rules as Phase 4), then have the test-runner re-run just the affected profile(s). Don't loop endlessly — after two fix→re-test rounds on the same failure, surface it to the human instead.
- **No caller profiles in the report?** Skip this phase and say so in the hand-off summary ("untested — no caller profiles were discussed") so the human knows verification didn't happen; if profiles exist but the run is skipped for any other reason, that's a red flag to surface, not a silent omission.
- The test-runner runs simulations only — it never changes config, and its results file is part of the review artifact.

## Phase 5 — Consolidate and hand off for review

- **Latency pass first:** walk the fast-by-default checklist in `docs/latency-playbook.md` against what was staged (flash-class LLM + reasoning off + capped `max_tokens`; Flash TTS model; lean prompt with a brevity rule; no large `"always"` KB docs / RAG matched to KB size; lean tool roster; `tts.speed` at 1.0 unless a pace change was asked for). Any checklist miss is either justified by a named requirement (state it and its latency cost in the summary) or sent back to the owning configurator before hand-off.
- Present a concise written summary in chat: per feature area, what was staged (tied back to the report), each configurator's apply status, and the Phase 4.5 test results (the pass/fail matrix per caller profile, or why the suite didn't run). Explicitly call out the **high-stakes staged changes** — transfer targets, phone-number assignment, retention/redaction, webhook destinations — so the human knows exactly what they're about to promote.
- Point the human at the **Sandbox branch** as the review artifact (ElevenLabs UI). State plainly that nothing is live until they merge Sandbox → Main themselves, and that you did **not** merge.
- Surface every red flag the subagents reported, and any requirement areas left as **Not discussed** so the human knows what's still uninterviewed.
- **Update the client-journey memory:** refresh `<client-folder>/CLAUDE.md` with what this run staged, the decisions made (and why), the current agent/branch state, and any new standing constraints — so the next session picks up the journey instead of rediscovering it. If the run surfaced a needed repo change, make sure it's written to `<client-folder>/repo-change-proposals.md` (per Golden Rule 8) and remind the operator to send it to Brett.
- **If a queue exists**, stop here and check in — summarize this agent, and wait for the human's explicit go-ahead before starting the next queued agent (back to Phase 0 for that one).

## Guardrails (recap)

- One agent per run; queue the rest and check in between each.
- Existing agents: stage on Sandbox, never edit Main, never merge — the human promotes.
- New agents: initial build on Main, built fresh from the create-agent reference's house defaults (never a MASTER TEMPLATE clone).
- Only configure features the requirements call for; never pressure unused features.
- Always orchestrate the subagents; never inline their work; dispatch configurators sequentially.
- Fast by default: dispatch briefs carry the latency posture; the Phase 5 latency pass runs before hand-off; slow choices are requirement-justified and stated, never silent (`docs/latency-playbook.md`).
- Client memory (the client folder's `CLAUDE.md` + feedback ledger) is read at run start and the `CLAUDE.md` updated at hand-off. The repo's house docs are binding defaults, and its files are Brett-gated: never edit docs/skills/agents or open a PR — proposed repo changes go in `<client-folder>/repo-change-proposals.md` for the operator to send to Brett.
- Verify before hand-off: when caller profiles exist, the Phase 4.5 test suite runs against the staged branch and its results ship with the summary; a skipped run is stated, never silent. "Caller profile" = who calls; "persona" = the agent itself.
- Branch mechanics are pinned (Phase 3): list branches with `include_archived: true`, create with `parent_version_id`, and an `agents_update` without `branch_id` lands on Main — the Sandbox id goes on every write.
- Auth is the connector, not a key: never ask for, store, or commit any API key; never fall back to `curl` against the raw API; pass subagents the client folder, not credentials.
