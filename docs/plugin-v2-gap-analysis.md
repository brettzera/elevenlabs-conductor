# elevenlabs-conductor — gap analysis for the phmg-elevenlabs plugin (v2)

Scan date: 2026-09-08. Source: `brettzera/elevenlabs-conductor` at commit
`a5c6369` (41 files, ~3 950 lines). Method: every file read; connector tool
schemas read live from the session; ElevenLabs docs and 2026 changelog
digested (`docs/reference/elevenlabs-docs-digest.md`).

> Delivered by the v2 plugin build (repo `elevenlabs-plugin-v2`, branch
> `claude/elevenlabs-agent-plugin-r63ryl`). This copy lives next to the repo it
> scans; the canonical file is `docs/conductor-gap-analysis.md` in the plugin.
> Brett requested the scan; nothing else in this repo was changed.

Verdict in one line: the conductor's *discipline* (Sandbox-first, one agent
at a time, read-only vs write rosters, client memory in the client folder,
evidence-only reports) is sound and is carried forward whole; what it lacks
is **packaging** (it only works as a cwd repo in a cloud session),
**mechanical enforcement** (every safety rule is prose), **boilerplate**
(no templates, no validators, no CI), a **design contract** between
requirements and configuration, and **currency** with the ElevenLabs API
(node-level tools, say nodes, expression edges, procedure tags, test types).

## A. Missing scripts and boilerplate

| # | Gap in the conductor | Evidence | v2 |
|---|---|---|---|
| A1 | **Not a plugin.** Layout is project-scoped `.claude/` + root `CLAUDE.md`; nothing loads unless the repo is the cwd. No `.claude-plugin/plugin.json`, no marketplace, no version. | `README.md` § Cloud-only operation | `.claude-plugin/plugin.json` + `marketplace.json` (self-hosting, `source: "./"`), versioned, installable from GitLab, auto-updating. |
| A2 | **Hook is not cross-platform.** `python3 "$CLAUDE_PROJECT_DIR/hooks/…"` — bash-style variable, Python dependency; nothing for Windows. | `.claude/settings.json` hooks block | Three plain-Node hooks under `hooks/hooks.json` with `${CLAUDE_PLUGIN_ROOT}`; run under Git Bash or PowerShell; LF enforced by `.gitattributes`. |
| A3 | **No mechanical enforcement.** "Never merge", "branch_id on every write", "no curl", "no key" exist only as prose in five places. | `CLAUDE.md`, both skills, every agent | `hooks/elevenlabs-write-guard.js` (PreToolUse): denies curl to the API / key handling / `agents_merge_branch` / hard deletes; asks on Main writes (unless `MAIN-BUILD`), Main test runs, phone reassignment, transfer bodies, and the `procedures` map. `settings.json` deny list as a second fence. |
| A4 | **No session-level rules outside the repo.** `CLAUDE.md` is the rule; the hook only reinforces. In any other cwd the rules vanish. | `README.md` § The routing hook | `hooks/standing-rules.md` injected by the router on the first ElevenLabs prompt of every session (and by SessionStart where the platform honours it). |
| A5 | **No templates.** The ledger format, client `CLAUDE.md` contents, report shapes, and repo-change note are described in prose only; every run re-derives them. | engineer skill § The feedback ledger; architect Golden rule 8 | `templates/client-folder/` (CLAUDE.md, feedback ledger, repo-change proposals) and `templates/agent/` (prompt, workflow JSON, procedures, criteria, guardrails, tests, data collection). |
| A6 | **No validator, no tests, no CI.** `hooks/` has one file; no `scripts/`; the retired `scripts/elevenlabs-commit-procedures.sh` was deleted without a replacement; no `.github/workflows`. | tree listing; create-agent `references/api.md` §5 | `scripts/validate-plugin.js`, `scripts/test-hooks.js` (33 checks), `scripts/doctor.js`, `.gitlab-ci.yml`. |
| A7 | **No self-check for operators.** Nothing tells a new machine whether the connector is attached, the hook fires, or where the client root is. | — | `elevenlabs-doctor` skill + `scripts/doctor.js`. |
| A8 | **`.gitignore` references `.env.example` that does not exist**; no `.editorconfig`; no `.gitattributes` (CRLF on Windows would break the hook). | `.gitignore` | Added `.gitattributes`, `.editorconfig`; `.env.example` intentionally absent (no secrets exist) and the ignore rule kept as belt-and-braces. |
| A9 | **House persona is mostly unfilled boilerplate.** 5 of 7 sections are `Status: unset` (identity, tone, do-not-say, greeting, language). | `docs/house-persona.md` | Carried over unchanged (Brett-gated) — flagged here for Brett to fill; the prompt skeleton no longer depends on them. |
| A10 | **Legacy code with no build.** `api/office-status.js` (single-client hard-coded webhook) has no `package.json`, no deploy config, and the n8n path superseded it. | `api/office-status.js` header | Not shipped; the n8n runbook is the only path; the n8n schedule skill carried over. |
| A11 | **Repo export/import skills** re-implement what a package manager does (zip + sha256 manifest) to move the repo between machines. | `elevenlabs-repo-export`, `elevenlabs-repo-import` | Replaced by the GitLab marketplace + `autoUpdate`. Not carried. |
| A12 | **No client-folder resolution for non-cloud use.** `clients/` must sit inside the repo clone; ephemeral containers lose it unless files are pasted out. | `docs/authentication.md` § Client workspaces | `ELEVENLABS_CLIENTS_ROOT` → `<cwd>/clients/` → cwd-with-`CLAUDE.md` → ask; documented in `docs/client-workspaces.md`; never inside the plugin cache. |

## B. Missing pipeline pieces

| # | Gap | Evidence | v2 |
|---|---|---|---|
| B1 | **No design contract.** Requirements go straight to eleven configurators, each re-reading the report and deciding its own slice; the "caller profiles fan out to three owners" rule is the only cross-cutting glue. Drift between prompt, nodes, procedures, criteria, and tests is inevitable. | architect Phase 4 | `elevenlabs-agent-designer` produces one approved **Agent Design Spec** (`references/design-spec-template.md`); every configurator implements its numbered section; the test-runner tests against it. |
| B2 | **No branch specialist.** Branch prep (list with `include_archived`, `parent_version_id`, live-traffic check) and the procedure-commit no-op are repeated inline in both skills. | architect/engineer Phase 3 | `elevenlabs-branch-manager` owns Sandbox prep, new-agent create (`MAIN-BUILD`), and the commit no-op. |
| B3 | **Two entry skills, one classifier missing.** Architect vs engineer is chosen by the human/hook wording; "add a feature to an existing agent" falls between them (the architect's manual mode). | `CLAUDE.md` routing | One `elevenlabs-conductor` with five intents (build / feature / debug / feedback / audit) and per-intent playbooks; the router hook pre-classifies. |
| B4 | **Configurator order undefined.** "Sequentially, never in parallel" but no order, although the workflow needs procedure names and tool ids that other steps produce. | architect Phase 4 | Fixed order: knowledge → tools → procedures → workflow → prompt → quality-safety → capture → llm → voice → dictionary → runtime; ids flow forward in the brief. |
| B5 | **Roster drift.** The architect says "the 12 subagents you orchestrate"; the README lists 17; the roadmap says 15 built. | architect SKILL.md line 9; README; roadmap | Single roster table in the conductor; validator checks roster ↔ `agents/` files. |
| B6 | **No architecture-compliance audit.** The analyzer inventories features but does not map an existing agent onto the house shape. | analyzer § What to inventory | Analyzer gains `## Architecture compliance` + migration delta (architecture skill §10). |
| B7 | **Reviewer cannot name the node.** Diagnosis stops at "feature area → configurator". | reviewer § What to produce | Uses `agent_metadata.workflow_node_id`, `tool_results` workflow steps, and `triggered_guardrails` per turn to name node + procedure + edge. |

## C. Stale or wrong against the current ElevenLabs API

| # | Conductor statement | Current reality (schema / docs, Sept 2026) | v2 |
|---|---|---|---|
| C1 | Workflow node types pinned as `start`, `end`, `phone_number`, plus "agent nodes"; no node-level tools; "tools are agent-wide". | Node types: `start`, `override_agent` (subagent; `additional_prompt`, **`additional_tool_ids`**, `additional_knowledge_base`, full `conversation_config` override, `entry_behavior`), `tool` (dispatch), `phone_number`, `standalone_agent`, `end`, and a `say` node (changelog 2026-03). | Architecture skill §4; schema pins §3; workflow template. Node-level tools are the house default. |
| C2 | "LLM edge conditions ignore time and even bare boolean dynamic variables" — routing on hours is impossible in the graph. | `expression` edge conditions with a deterministic AST (`dynamic_variable`, `eq_operator`, …) exist alongside `llm`, `result`, `unconditional`. | Hours routing = expression conditions (workflow-graph.md § Hours-based routing); time-of-day doc updated. |
| C3 | "A dedicated closing node failed in both available forms" — sign-off must live in each leaf's prompt. | The `say` node is the product's answer (fixed text, then an edge to End). | Goodbye say node (with a pinned-fallback until its container field is confirmed live); clean-close simulation is mandatory before hand-off. |
| C4 | `require_acceptance` exists on the transfer tool's `transfers[]`. | No such field anywhere in the schema; `transfer_type: blind|conference|sip_refer` only. | Removed; tools configurator documents `blind` as the no-acceptance form. |
| C5 | Procedures: `content` carries `---name/trigger---` front matter; referenced from nodes only by name. | API fields `name`/`trigger` are flat; free-form content supports `[tool id]`, `[kb id]`, `[procedure id]`, `[system_tool id]` tags; `deterministic` (structured) type; `start_procedure`/`end_procedure` system tools; the `procedures` map on update **replaces** the set. | Procedure template with tags; front-matter mirror rule; guard asks on the `procedures` map; structured type documented, not adopted. |
| C6 | Guardrails: "only `end_call`/`retry` exist". | Still true, plus `execution_mode`, `model`, `history_message_count`, `evaluate_full_response_only`, retry max 3, `{{trigger_reason}}`/`{{agent_message}}`; **procedure-version `guardrails`** field (shape undocumented). | Three-layer placement (prompt / agent-wide / procedure `## Guardrails`); schema pins §7. |
| C7 | Evaluation: criteria array only. | `scoring_mode` binary / numeric, `scope`, `analysis_items` by reference with system sentiment/frustration; limit 30. | Quality-safety configurator reads which model the agent uses; criteria traceable to profiles. |
| C8 | Tests: "define a test (simulated caller + success criteria)". | Three test types (`llm`, `tool` with `workflow_node_transition`, `simulation` with `success_conditions[]`, `tool_mock_config`); `repeat_count`; `agent_config_override`. | Test-runner rebuilt around them; per-profile simulations + node-transition tests. |
| C9 | LLM: "hosted Qwen id unverified; `qwen3-30b-a3b` tier". | Enum: `qwen3-4b`, `qwen3-30b-a3b`, `qwen36-35b-a3b`, `qwen35-397b-a17b`; `reasoning_effort`, `thinking_budget`, **`prompt.timezone`** (gives the agent a clock), `ignore_default_personality`. | Latency defaults table; `timezone` set on every agent. |
| C10 | TTS: `optimize_streaming_latency` "confirm presence live". | Deprecated no-op. `eleven_turbo_*` deprecated. `text_normalisation_type`, `expressive_mode` default true (auto-off on non-v3). | Never drafted; `expressive_mode: false` explicit. |
| C11 | `platform_settings` extras absent. | `trust_context` (`low` for customer-facing), `call_limits`, `alerting`, `summary_language`, `data_collection_scopes`, `conversation_history_redaction.entities`. | Schema pins §8; quality-safety sets `trust_context: low`. |
| C12 | Branch prefix `agtbrch_` only. | Docs use both `agtbrch_` and `agtbranch_`; `agtprcv_` for procedure versions; KB ids have no prefix. | Router matches both; pins §2. |

## D. Things the conductor got right (kept verbatim in spirit)

- Sandbox-first with `include_archived` + `parent_version_id` + live-traffic check (LIVE 2026-08-09).
- Read-only rosters as a fence; drafts-freely/apply-only-when-authorised on every writer.
- Business facts in the KB, not the prompt; lean prompt; fast-by-default latency posture.
- Three-surface text architecture and the carried-info rule.
- Evidence-only reports with ≤15-word quotes; ledger with FB-ids and the five statuses.
- The office-status webhook runbook (n8n) and the schedule-string skill.
- Connector-only auth; `context` line discipline; first-run setup flow.

## E. For Brett to decide (not changed by v2)

1. Fill the `Status: unset` sections of `docs/house-persona.md` (identity, tone, do-not-say, greeting, language) — the prompt skeleton leaves them as placeholders.
2. Confirm the hosted-Qwen model id on a live agent and pin it in `references/latency-defaults.md`.
3. Create one Goodbye `say` node in the UI on any Sandbox and paste its JSON into `docs/reference/connector-schema-pins.md` §3 so the fallback can be retired.
4. Decide whether to keep `elevenlabs-repo-export/import` anywhere (v2 drops them in favour of the GitLab marketplace).
5. Decide the GitLab group/project path and update `plugin.json`/`marketplace.json` `homepage`/`repository` and the README install URL.
