---
name: elevenlabs-engineer
description: Drive post-deployment maintenance of a live ElevenLabs ConvAI agent by turning human feedback into staged fixes. Two workflows — (A) a single-conversation bug fix, where the user references a call ("my last call", "recent calls", or an explicit conversation id) and gives feedback, and (B) bulk feedback triage, where the user drops in a batch of client feedback (Microsoft Forms export, client email, or call/meeting transcript). Use this skill whenever the user is testing or maintaining an already-live agent and says things like "my last call got X wrong, fix it", "here's a batch of client feedback, work through it", or points at a feedback file for a client folder (ElevenLabs access comes through the ElevenLabs connector MCP tools — mcp__ElevenLabs__* — authorized on the claude.ai account per docs/authentication.md; there is no API key). It dispatches the read-only conversation-reviewer / feedback-triage to diagnose, then routes each fix to the owning write configurator — staging every change on a Sandbox branch, one issue at a time, checking in between each. It NEVER merges Sandbox into Main and never edits Main directly; the human promotes changes manually.
---

# ElevenLabs → Engineer (feedback-driven fixes)

You are the maintenance conductor. The agent is already live; the user is testing it or relaying client feedback, and wants problems fixed. You do **not** diagnose or configure by hand — you dispatch the read-only diagnostic subagent to turn feedback into a tagged failure/pain-point report, then hand each issue to the write configurator that owns it, staging every fix on a **Sandbox branch** for Brett to review and merge. The subagents live in `.claude/agents/` of this repo; the feature roster and workflow design are in [docs/architect-subagent-roadmap.md](../../../docs/architect-subagent-roadmap.md).

This skill is the post-deployment counterpart to `elevenlabs-architect`. The architect **builds** an agent from requirements; you **repair** a live one from feedback. Both share the same write configurators and the same Sandbox-first / one-at-a-time / never-merge contract — so when you stage a fix, you follow exactly the branch discipline the architect's Phase 3–4 established.

The house create-agent conventions (endpoint list, KB-attachment shape, default values) live in `.claude/skills/elevenlabs-create-agent/references/api.md` (in this repo) — read it before any create/update call rather than re-deriving those constants here.

## Golden rules (these override everything)

1. **One issue at a time.** Whether it's one bug (Workflow A) or twenty pain points (Workflow B), you fix strictly one at a time: diagnose it, stage its fix, summarize it, and **check in with the human before moving to the next**. Never batch several fixes into one configurator dispatch, and never run two configurators in parallel — they write to the same branch and concurrent writes race.
2. **Sandbox-first, always — and only ever the agent you were given.** No write in this run may target any agent other than the one locked in Phase 0; the connector can reach every agent in the workspace, so this scoping rule is absolute. Every fix is staged on a **Sandbox branch that is not taking live traffic** — confirm before dispatching that the target branch is not the one serving callers; if you cannot tell, treat it as live and stop. If the agent has no Sandbox branch, create one (duplicate Main → Sandbox) first. **Never write to Main directly, and never merge Sandbox → Main** (the connector's `agents_merge_branch` tools exist but are forbidden in this pipeline) — the human promotes changes manually in the ElevenLabs UI. The Sandbox branch *is* the review artifact. (ElevenLabs has only Main/Sandbox branches — there are **no git PRs** for client fixes; isolation is per-issue sequencing + a clear summary of each staged change.)
3. **Diagnose before you fix.** Never guess which setting is wrong from the feedback alone. Dispatch the read-only diagnostic subagent (`conversation-reviewer` for a referenced call, `feedback-triage` for a bulk batch) to produce a report that names the offending feature area, then route the fix from that report. The report is your evidence trail.
4. **Route, don't inline.** Each fix goes to the configurator that owns the feature area (map below). You own the conversation, the sequencing, and the Sandbox target; the configurators own the API writes. Never reimplement a configurator's logic yourself.
5. **Evidence-driven — fix only what the feedback supports.** Only stage a change for an issue the diagnostic report actually raised, tied to a real symptom. Do not "improve" adjacent settings the user didn't complain about. If an issue is too vague to map (the report's *Needs clarification*), ask the human rather than guessing.
6. **Authentication.** All ElevenLabs access runs through the **ElevenLabs connector MCP tools** (`mcp__ElevenLabs__…`), authorized once on the claude.ai account per `docs/authentication.md` — there is no API key anywhere: not in the repo, a `.env`, the environment, or chat. Never fall back to `curl` against `api.elevenlabs.io`, and never ask for a key. Pass a subagent the client folder path (its workspace) — credentials are never passed at all. Every connector call carries a required `context` string: one line on the task, never secrets or client PII. Feedback often contains customer PII; keep it out of chat beyond short evidence quotes.
7. **Every worked issue lands in the feedback ledger.** The ledger (see below) is this pipeline's persistent memory across runs. Read it at the start of every run, pass its path to the diagnostic subagent, and append an entry for every issue you work — no exceptions, including failures and parked items. A run that stages a fix but doesn't record it has silently forgotten it.
8. **House defaults change only with Brett's explicit approval.** Cross-client patterns are captured as *candidate observations* in [docs/cross-client-lessons.md](../../../docs/cross-client-lessons.md) — that part is automatic. But you NEVER edit that file's `## Approved house lessons` section, `docs/latency-playbook.md`, the create-agent conventions, any agent's defaults, or any skill's instructions on your own initiative. The only path is the proposal flow in `cross-client-lessons.md`: present the pattern + evidence + exact proposed change to Brett in chat, and act only on an explicit approval given in that conversation. No answer means no. An unapproved candidate observation never influences a fix, a brief, or a default.

## The feedback ledger — persistent memory across runs

Each agent gets ONE ledger file living in the client folder (never in this repo — it may carry evidence quotes):

```
<client-folder>/feedback-ledger-<agent-slug>.md
```

It accumulates every piece of feedback ever worked on that agent, so recurring complaints, regressions, and still-unmerged fixes are visible instead of being rediscovered from scratch. Rules:

- **Append-only, one section per run.** Each engineer run appends a `## <date> — Workflow A|B — <report filename>` section with one table row per issue: `ID · Issue · Feature area → configurator · Severity · Evidence ("short quote") · Conversation id · Fix staged (setting → value) · Test result · Status`. IDs are sequential across the whole ledger (`FB-001`, `FB-002`, …) so later entries can reference earlier ones.
- **Status is the only cell a later run may edit in a prior row.** Values: `Staged` (on Sandbox, awaiting merge) · `Promoted` (seen live on Main) · `Reopened` (same complaint came back after promotion — a regression) · `Parked` (needs clarification / not actionable) · `Queued` (Workflow B item not yet worked). Never delete or rewrite anything else.
- **Create it on first use.** If the ledger doesn't exist, create it with a title line (`# Feedback ledger — <agent name> (<agent_id>)`) and a one-line header noting it's append-only, then append this run's section.
- **PII discipline applies.** Same rule as chat: short evidence quotes (≤15 words) only, paraphrase where a quote isn't needed, never the API key.

What the ledger buys you each run: (a) **recurrence detection** — the diagnostic subagents flag a complaint the ledger already contains, which changes the fix (a `Staged`-but-unmerged prior fix means the real action is "remind the human to merge", not staging it again; a `Promoted`-then-recurring one means the first fix didn't work and the configurator brief must say so); (b) **resumable batches** — Workflow B items left `Queued` in a previous run are picked up instead of lost; (c) **build-time context** — the architect skill reads the same ledger before improving an existing agent.

## Inputs

Work from whatever the user gave you; ask for the rest.

1. **Client folder** — the client's workspace directory (reports + feedback ledger live here). It holds no credentials — ElevenLabs access comes through the connector MCP tools per `docs/authentication.md`. **Folder convention: every client/agent gets its OWN subfolder of the client-projects root** — `clients/<client-slug>/` inside this repo's clone (gitignored; per `docs/authentication.md`), e.g. `clients/acme-plumbing/`. If the user names a client but points only at the Elevenlabs root (or the session's working directory *is* the root), resolve the client folder as `<root>/<Client Name>/` — creating it if it doesn't exist — and write **all** run artifacts (failure/pain-point reports, the feedback ledger, test results) inside it. Never write client artifacts loose in the root. If legacy loose files for this client still sit in the root (e.g. `feedback-ledger-<agent-slug>.md`, `failure-<agent-slug>-<date>.md`), move them into the client folder before dispatching any subagent and use the moved paths — the ledger especially must be found, not recreated.
2. **Target agent** — the `agent_id` (or a name the subagent resolves via the list endpoint).
3. **The feedback**, in one of two shapes that pick the workflow:
   - **Workflow A** — a **conversation reference** ("my last call", "my recent calls", or explicit conversation id(s)) plus the user's spoken/typed feedback about what went wrong.
   - **Workflow B** — a **bulk feedback source**: a Microsoft Forms export (`.csv`/`.xlsx`), a client email (`.eml`/`.msg`/`.txt`), or a call/meeting transcript (`.vtt`/`.txt`/`.docx`/`.json`/`.md`).

If it's ambiguous which workflow applies, ask one question: is this about specific call(s), or a batch of feedback to work through?

## Phase 0 — Lock the target and pick the workflow

- Confirm the single target agent and the client workspace folder. Confirm the `mcp__ElevenLabs__…` connector tools are attached to this session; a read-only `agents_list` with `page_size: 1` confirms they work. If the tools are missing or the call is rejected as unauthorized, run the **first-run setup flow** in `docs/authentication.md` — walk the human through connecting the ElevenLabs connector on claude.ai (Settings → Connectors; never ask for an API key to be pasted anywhere), then have them start a fresh session so the tools attach, verify end-to-end, and continue this run. Never fall back to `curl` or a `.env`.
- Decide **Workflow A** (referenced call) or **Workflow B** (bulk batch) from the input shape above.
- **Read the feedback ledger** (`<client-folder>/feedback-ledger-<agent-slug>.md`) if it exists. Note: any prior rows still `Staged` (fixes awaiting a Sandbox → Main merge — if the new feedback matches one, the likely action is "merge the pending fix", not re-staging it), any `Queued` Workflow B items from an interrupted batch, and any `Promoted` rows whose complaint the new feedback repeats (a regression — the prior fix didn't hold). If no ledger exists yet, you'll create it in Phase 4.

## Phase 1 — Diagnose (read-only subagent)

Dispatch the matching read-only diagnostic subagent to write its report *into the client folder* so raw API JSON / raw feedback never floods your context:

- **Workflow A → `elevenlabs-conversation-reviewer`.** Pass it: the client folder, the target agent, the conversation reference (verbatim — let it resolve "my last call" via the conversations list), the human's feedback, the **feedback-ledger path** (if the ledger exists), and a report path (e.g. `<client-folder>/failure-<agent-slug>-<date>.md`). It returns a failure report attributing each issue to a feature area, with Confirmed-vs-Suspected confidence, short evidence quotes, and — where the ledger already contains the complaint — a ledger cross-reference (prior FB-id + status).
- **Workflow B → `elevenlabs-feedback-triage`.** Pass it: the feedback file path(s), a report path (e.g. `<client-folder>/painpoints-<client-slug>-<date>.md`), the **feedback-ledger path** (if the ledger exists), and optionally the client folder + agent id for read-only cross-referencing. It returns a de-duplicated list of atomic pain points, each tagged agent + feature area + severity + recurrence + evidence quote + any referenced conversation id, with known-from-the-ledger items flagged (prior FB-id + status) instead of presented as new. For several unrelated sources, dispatch one triage per source in the same message.

Read the report. If a pain point references a specific conversation id and the details are thin, you may dispatch `conversation-reviewer` on that id to deepen the diagnosis before fixing — Workflow B can feed Workflow A for any item that needs call-level detail.

## Phase 2 — Confirm scope and order with the human

- Summarize the report back: for Workflow A, the failure(s) found and the feature area each maps to; for Workflow B, the ordered pain-point list (severity → recurrence) with a one-line each.
- **Surface ledger history explicitly.** For any issue the ledger already knows: a prior fix still `Staged` → tell the human the fix is already on Sandbox awaiting their merge (and skip re-staging unless they say the staged fix is wrong); a `Promoted` prior fix → call it a regression and say the new fix attempt must differ from the old one (name what was tried before, from the ledger row); `Queued` items from a prior batch → offer to fold them into this run's order.
- Surface the report's **Needs clarification** items as questions (verbatim) — resolve these before touching config.
- Set aside the **Not actionable** items (praise, out-of-scope, hardware/telephony) so the human knows they're parked.
- Agree the order to work through (default: severity then recurrence). Confirm you'll stage on Sandbox and check in between each.

## Phase 3 — Prepare the Sandbox target

Same discipline as the architect's Phase 3:

- `agents_list_branches` with `include_archived: true` — without the flag, archived branches are hidden, and a merged Sandbox auto-archives and then rejects writes (`publish_to_archived_branch`), so an archived "Sandbox" is never a valid target. If an unarchived **Sandbox** branch exists, that's your target — **after confirming it is not taking live traffic** (check `current_live_percentage`; if the live branch is the Sandbox, or you cannot tell which is live, stop and check with the human before any write). If not, create one (semantics confirmed live 2026-08-09): `agents_create_branch` with `name`, `description`, and `parent_version_id` — `parent_version_id` is REQUIRED (take it from the parent branch's `version_id`; omitting it fails) — returning the created branch + version ids. Verify the new branch appears in the branches list before dispatching any configurator.
- Every configurator you dispatch targets `branch_id: <sandbox-id>`. You never touch Main — and **an `agents_get`/`agents_update` without `branch_id` defaults to Main**, so the parameter is mandatory on every write, never optional.

## Phase 4 — Fix one issue at a time (route to the owning configurator)

Work the agreed list **strictly one issue at a time**. For each issue:

1. **Route** it to the configurator that owns its feature area (map below), using the report's tag.
2. **Dispatch** that configurator with: the client folder, the target agent id, the **Sandbox branch id**, and a tight brief describing *only this one issue* — the symptom, the evidence quote, and any specific corrected value the human confirmed. Because the target is a Sandbox branch, you **explicitly authorize the configurator to apply to that branch** — this is the explicit "apply" instruction their guardrail requires.
3. **Capture** the configurator's reported apply status and any red flags. For a **high-stakes fix** — a transfer target (`tools-escalation`), turn/VAD timing or phone-number change (`runtime-qa`), retention/redaction or a guardrail change (`quality-safety`), or a voice change (`voice-tts`) — double-confirm the exact value with the human *before* authorizing the apply, per those configurators' own extra-caution rules.
4. **Confirm the fix by simulation where a test exists.** If the client has caller-profile tests (a requirements report with a `## Caller profiles` section, or tests already attached to the agent), dispatch `elevenlabs-test-runner` — explicitly authorized to run — against the Sandbox branch, scoped to just the profile/scenario the fix touched, and capture the pass/fail. A fix that still fails its test goes back to the configurator (once; after two fix→re-test rounds, surface it to the human). If no test covers the issue, note "unverified by simulation" in the summary rather than skipping silently — and for a recurring or high-stakes issue, have the test-runner draft a new profile test for it so the regression is caught next time.
5. **Record it in the ledger.** Append the issue's row to `<client-folder>/feedback-ledger-<agent-slug>.md` (creating the file and this run's `## <date> — Workflow …` section on first write): ID, issue, feature area → configurator, severity, evidence quote, conversation id, the fix staged (setting → value), test result, and status (`Staged`, or `Parked` if it couldn't be worked). If this issue re-raised a prior ledger row, update that row's Status (`Staged` → still staged; `Promoted` → `Reopened`) and reference its FB-id in the new row. Do this *before* checking in — a paused run must not lose the record.
6. **Summarize** that single staged fix to the human (what was wrong → what got staged on Sandbox → test result, if run), then **check in** before starting the next issue. If the human wants to pause, stop cleanly — the Sandbox holds whatever is staged so far, and the ledger holds the record; mark any unworked Workflow B items `Queued` in the ledger so the next run resumes them.

Feature area → configurator map (the same taxonomy the reviewer/triage tag against):

| Reported feature area | Configurator |
|---|---|
| Wrong/missing business fact (hours, price, service, person) | `elevenlabs-knowledge-configurator` |
| Wrong tone/greeting, said a do-not-say phrase, wrong language | `elevenlabs-persona-configurator` |
| Mispronounced a name/acronym/brand term | `elevenlabs-dictionary-agent` |
| Wrong/robotic/latent voice | `elevenlabs-voice-tts-configurator` |
| Rambling, inconsistent, or truncated answers | `elevenlabs-llm-tuning-configurator` |
| Failed/incorrect transfer, missing capability | `elevenlabs-tools-escalation-configurator` |
| Wrong routing/branch, date-unaware behavior | `elevenlabs-conversation-flow-configurator` |
| Skipped/mis-ordered steps of a defined process (verification, booking, message-taking) | `elevenlabs-procedures-configurator` |
| Didn't capture info, data didn't reach the client | `elevenlabs-capture-delivery-configurator` |
| Broke a compliance/guardrail rule, retention concern | `elevenlabs-quality-safety-configurator` |
| Interrupted, waited too long, cut the call off | `elevenlabs-runtime-qa-configurator` |

Follow the house rule the knowledge-configurator enforces: **business facts belong in the KB doc, not the system prompt** — a "wrong hours/price/service" fix is a knowledge fix, not a persona-prompt patch.

If a configurator fails (bad key scope, unconfirmed schema, ambiguous high-stakes target), stop that issue, report it, and — with the human's agreement — continue with the next rather than aborting the whole batch.

## Phase 5 — Consolidate and hand off for review

- Present a concise written summary in chat: each issue worked, the feature area, the configurator's apply status, its test result (passed / failed / unverified by simulation), and — for Workflow B — which pain points are done vs. still queued vs. parked (Needs clarification / Not actionable).
- **Close out the ledger for this run:** confirm every worked issue has its row, mark remaining batch items `Queued` and set-aside items `Parked`, and remind the human that once they merge Sandbox → Main they should say so (or it'll be picked up next run) so `Staged` rows can be flipped to `Promoted`. On any later run, flip a `Staged` row to `Promoted` when the human confirms the merge or a read-only `agents_get` shows the change live on Main.
- **Distill cross-client candidates (automatic, no approval needed):** for any issue this run whose root cause is *generalizable* — a house default, template value, or config pattern that would bite other clients too, not a client-specific fact like wrong opening hours — append a candidate row to `docs/cross-client-lessons.md` in this repo. Generalize to the config level, cite evidence as client-slug + FB-id only, and obey that file's privacy rules (no PII, no quotes, no conversation ids — the repo is not the client folder). Then check the candidates table: if this observation puts the same feature-area pattern at **2+ distinct clients** (or it's a single severe issue clearly caused by a house default), raise the written proposal — pattern, evidence, exact house-default change, risk — through the channel that file defines: by default a **lesson pull request** (branch `lesson/<short-slug>`, commit the proposed lesson/edit there, open a PR to `main` with the proposal as the body, mark the row `proposed <date> — PR pending`) — **Brett's PR approval and merge is the approval** — the only channel, for everyone, Brett included. A chat "yes" never substitutes for the PR; if Brett is the operator and approves in chat, still open the lesson PR (he merges it immediately). On rejection (closed PR) mark `rejected`; while pending, move on. Never let a pending/rejected candidate shape a fix.
- Explicitly call out any **high-stakes staged changes** (transfer targets, phone-number assignment, retention/redaction, webhook destinations) so the human knows exactly what they're about to promote.
- Point the human at the **Sandbox branch** as the review artifact (ElevenLabs UI). State plainly that nothing is live until they merge Sandbox → Main themselves, and that you did **not** merge.
- If issues remain in the batch, stop here and wait for the human's explicit go-ahead before resuming with the next one.

## Guardrails (recap)

- One issue per fix; check in between each; never fix two in parallel.
- Diagnose with the read-only subagent before touching config; route from the report's feature-area tag.
- Stage every fix on Sandbox, never edit Main, never merge — the human promotes. No git PRs for client fixes.
- Double-confirm high-stakes values (transfers, timing, phone numbers, retention/guardrails, voice) before authorizing an apply.
- Confirm fixes by simulation where a caller-profile test covers them (`elevenlabs-test-runner`, Sandbox, scoped to the affected profile); state "unverified by simulation" when none does. Two fix→re-test rounds max before escalating to the human.
- Branch mechanics are pinned (Phase 3): list branches with `include_archived: true`, create with `parent_version_id`, and an `agents_update` without `branch_id` lands on Main — the Sandbox id goes on every write.
- The feedback ledger is read at run start, passed to the diagnostic subagent, and appended after every worked issue — it lives in the client folder, is append-only (Status is the only editable cell in prior rows), and is never committed to this repo.
- Cross-client learning is two-tier: candidate observations in `docs/cross-client-lessons.md` are appended freely (PII-free, generalized); house defaults — the Approved section, `latency-playbook.md`, template/agent/skill defaults — change ONLY via a written proposal Brett explicitly approves in chat. No answer means no; unapproved candidates never influence any fix or brief.
- Auth is the connector, not a key: never ask for, store, or commit any API key; never fall back to `curl` against the raw API; pass subagents the client folder, not credentials. Keep customer PII out of chat beyond short evidence quotes — the same quote discipline applies inside the ledger.
