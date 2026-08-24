# ElevenLabs ConvAI — Create-Agent Reference (connector MCP edition)

House reference for creating a brand-new ConvAI agent: the connector tool
list, the build-fresh baseline field values, and the verified
knowledge-base-attachment shape. Originally authored 2026-08-10 from
ElevenLabs' own docs plus live read-only GETs against one existing PHMG
client agent; converted 2026-08-24 to the **ElevenLabs connector MCP tools**
(`mcp__ElevenLabs__…`) — the tools wrap the same ConvAI API, so the live
verifications below still describe the platform's behavior; what changed is
the calling surface and the auth. Anything not explicitly marked
**VERIFIED LIVE** below must be confirmed with a read-only tool call before a
configurator drafts against it (house unverified-schema rule — see §6).

Auth: the ElevenLabs connector, authorized on the claude.ai account per
`docs/authentication.md`. There is **no API key** — never `curl`
`api.elevenlabs.io`, never read or write an `ELEVENLABS_API_KEY`. Every
connector tool takes a required `context` string: one line describing the
task, never secrets or client PII.

## 1. Tool list

| # | Connector tool | One-line note | Verification |
|---|---|---|---|
| 1 | `agents_create` | Create an agent. Compact fields: `name`, `first_message`, `language`, `prompt`, `voice_id`; anything else goes in `body` (the raw create-agent API body, whose sole required field is `conversation_config` — every sub-field below has a documented default). | Tool schema confirms the compact-field + `body` split; response shape **UNVERIFIED via connector — confirm on the first real create before relying on it**. |
| 2 | `agents_get` | Read one agent's full config. Optional `branch_id` reads a specific branch; omitted = Main. Optional `version_id` reads a pinned version. | Underlying GET **VERIFIED LIVE** 2026-08-10 against `agent_2601ksq9frzye6b85fq3k94pdgfy` (CL-B) — full key shape confirmed (§2–§3). |
| 3 | `agents_update` | Update an agent. Compact fields (`name`, `first_message`, `language`, `prompt`, `voice_id`) for the common cases; `body` mirrors the raw update shape (partial/deep-merge). `branch_id` targets a branch — **omitted defaults to Main**, so any write meant for Sandbox must carry it explicitly. `version_description` labels the minted version. | Tool schema confirms params; merge semantics match the house-pinned branch mechanics (confirmed live 2026-08-09). |
| 4 | `agents_list` | List agents. Params: `page_size` (default 30, max 100), `search`, `archived`, `created_by_user_id` (`@me`), `sort_by`, `sort_direction`, `cursor`. | Underlying GET **VERIFIED LIVE** 2026-08-10 — `{agents, next_cursor, has_more}`. |
| 5 | `agents_create_kb_text` | Create a KB doc from raw text. `body`: required `text`; optional `name`, `parent_folder_id`. | Docs/schema-verified; not exercised in the read-only pass. |
| 6 | `agents_create_kb_url` | Create a KB doc from a URL. `body`: required `url`; optional `name` etc. | Docs/schema-verified; not exercised. |
| 7 | `agents_list_knowledge_base` | List KB docs (workspace-wide). Params: `page_size`, `search` (name prefix), `types` (`file`\|`url`\|`text`\|`folder`), `parent_folder_id`, `sort_by`, `cursor`. | Docs/schema-verified; not exercised. |
| 8 | `agents_get_kb_document` | Get one KB doc's metadata (pass `documentation_id`). | Underlying GET **VERIFIED LIVE** 2026-08-10 — top-level keys confirmed: `id, name, metadata, supported_usages, access_info, folder_parent_id, folder_path, type, extracted_inner_html, content_format, filename, external_sync_info, auto_sync_info, refresh_status, is_frozen`. |
| 9 | `agents_create_branch` | Create a branch. Required in practice: `name`, `description`, `parent_version_id` (**required — omitting it fails**, taken from the parent branch's `version_id`). Returns the created branch + version ids. | House-pinned, verified live by the architect skill's own build (2026-08-09) — cited, not re-derived here. |
| 10 | `agents_list_branches` (`include_archived: true`) | List branches. **The flag is required** — without it, archived branches are hidden, and a merged Sandbox auto-archives (so an archived "Sandbox" silently disappears from the default list). | Underlying GET **VERIFIED LIVE** 2026-08-10 (CL-B) — per-branch fields include `id, name, description, is_archived, current_live_percentage, parent_branch_id, draft_exists, merged_into_branch_id`. The branch's own id field is `id` — it's what goes into the `branch_id` parameter on the other tools. |
| 11 | `agents_update` with `branch_id` | Update a specific branch (same tool as #3, with the parameter). | Same as #3 — the `branch_id` parameter is what makes a write target Sandbox instead of Main. |

Procedures are **not** reachable through the tools above — they are a
separate branch-scoped tool family with their own lifecycle. See §5.

## 2. Build-fresh baseline fields (initial `agents_create` call)

These are the fields a brand-new agent's first `agents_create` should carry,
per the no-clone convention in §4. Field *paths* below are **VERIFIED LIVE**
(confirmed present on a real agent's read, CL-B, 2026-08-10); default
*values* are either the documented API default or the house override — each
labeled. `name`, `first_message`, `language`, and `voice_id` ride in the
tool's compact parameters; everything else goes in `body` under
`conversation_config`.

| Field | Path | Value to use on a fresh build | Source |
|---|---|---|---|
| `name` | top-level `name` (compact param) | The client/agent's display name — no house default, always client-specific. | Verified path. |
| `first_message` | `conversation_config.agent.first_message` (compact param) | Draft per the house greeting shape in `docs/house-persona.md` — that section is currently `Status: unset`, so there is **no fixed house template string** yet; keep it one breath long per the latency playbook. Do not invent a greeting template the persona doc doesn't have. | Path verified live; content convention per `docs/house-persona.md` (unset). |
| `language` | `conversation_config.agent.language` (compact param) | No house default is documented — `docs/house-persona.md` § Language defaults is `Status: unset`. API default is `en` if omitted. | Path verified live; house default unset — API default from docs. |
| `voice_id` | `conversation_config.tts.voice_id` (compact param) | **TBD — no house-default voice pin.** Voice is chosen per client by `elevenlabs-voice-tts-configurator`; do not hardcode a voice id here or treat any client's current `voice_id` as a house default. Note: the compact param omitted, the workspace's standard ConvAI voice applies — still a per-client decision to revisit. | Path verified live. |
| LLM | `conversation_config.agent.prompt.llm` (via `body`) | House primary: **an ElevenLabs-hosted Qwen model, non-thinking/instruct variant** (per `docs/latency-playbook.md`). The `agents_update`/`agents_create` schema's model enum lists the accepted id strings (e.g. `qwen3-30b-a3b` tier), but **deprecation status is invisible there** — per lesson C-008 hosted-Qwen ids go stale, so confirm the current id from a live agent's config before use. Fallback/backup: a flash-class model (e.g. `gemini-2.5-flash`) for `backup_llm_config`. | Path verified live (`agent.prompt.llm` and `agent.prompt.backup_llm_config` both present on CL-B). Exact current Qwen id UNVERIFIED. |
| `temperature` | `conversation_config.agent.prompt.temperature` (via `body`) | House default per latency playbook: keep low for a voice agent's consistency; no single pinned number beyond "reasoning off" — inherit whatever the LLM-tuning configurator sets per its own defaults. API default if omitted: `0`. | Path verified live. |
| `max_tokens` | `conversation_config.agent.prompt.max_tokens` (via `body`) | House default: **~300** (per `docs/latency-playbook.md` — caps response length, the single biggest hidden latency lever). API default if omitted: `-1` (uncapped). | Path verified live. |
| ASR | `conversation_config.asr` (via `body`) | House posture: largely API-standard, not house-customized. **VERIFIED LIVE** on CL-B: `{quality: "high", provider: "scribe_realtime", user_input_audio_format: "pcm_16000", keywords: []}` — these match the documented create defaults, so a fresh build can rely on the API defaults here rather than setting ASR explicitly, unless a client needs custom `keywords`. | Path + values verified live; matches docs defaults. |
| TTS `model_id` | `conversation_config.tts.model_id` (via `body`) | House default: **`eleven_flash_v2_5`** (per `docs/latency-playbook.md` — Flash class for latency; ElevenLabs recommends Flash over Turbo). This **overrides** the raw API's own create default (`eleven_flash_v2`) — the house is deliberately pinning a newer Flash-class model, not accepting the bare API default. | Path verified live. House value from latency playbook. |
| `tts.speed` | `conversation_config.tts.speed` (via `body`) | House default: `1.0` unless the client asked for a pace change (range `0.7`–`1.2`). This is a *pace* lever, not a latency lever — never used to "fix" lag. | Path verified live (a client-tuned value on CL-B is that client's choice, not the house default). |

## 3. Knowledge-base attachment shape — VERIFIED LIVE

The array field that attaches a KB doc to an agent lives at:

```
conversation_config.agent.prompt.knowledge_base   (array)
```

Confirmed live 2026-08-10 (CL-B) — each entry is a flat object with exactly:

```json
{ "type": "file", "name": "<doc display name>", "id": "<kb-document-id>", "usage_mode": "prompt" }
```

- **`type`** — the KB doc's source type. Observed live: `"file"`. Per the
  list tool's `types` filter, the other valid values are `"url"` and
  `"text"` (matching the two create tools, #5/#6 above) and `"folder"` for
  organizational grouping — **not verified live**, only cited from the
  documented filter enum.
- **`name`** — display name, matches the KB doc's own `name` field (confirmed
  by cross-referencing the attached doc via `agents_get_kb_document`, §1 #8).
- **`id`** — the KB document id, usable directly with `agents_get_kb_document`.
- **`usage_mode`** — observed live value: `"prompt"` (the doc's content rides
  in the system prompt every turn). The tool schema's enum is
  `"prompt" | "auto"` (`"auto"` = default, model decides) — the schema shows
  no separate RAG usage-mode string; RAG is governed by the `rag` object
  below.

RAG is a **separate** object, not part of the `knowledge_base` array entries:

```
conversation_config.agent.prompt.rag   (object)
```

Confirmed live 2026-08-10 (CL-B) — keys present: `enabled`,
`embedding_model` (e.g. `e5_mistral_7b_instruct`), `optional_rag_enabled`,
`max_vector_distance`, `max_documents_length`, `max_retrieved_rag_chunks_count`,
`num_candidates`, `query_rewrite_prompt_override`, `knowledge_base_tool_info`.
Per `docs/latency-playbook.md`: RAG adds ~250–300ms/turn but keeps the prompt
small — small KB → prompt mode (`usage_mode: "prompt"`/`"auto"`), large KB →
RAG on. Never both a large `"always"`/`"prompt"`-mode doc *and* RAG off.

## 4. Why no MASTER TEMPLATE

**Decided by Brett, 2026-08-10.** New agents are built directly from the
documented defaults in §2 of this file rather than cloned from an existing
agent in the account. Rationale: no single agent in the account has ever been
designated the canonical build baseline, so cloning "whatever's there" would
silently inherit one client's drift (their voice choice, their prompt
content, their tool roster) into every new build. The agents actually named
**"MASTER TEMPLATE"** in the account are **BDM demo agents** — sales/demo
material built to look good in a pitch, not a maintained house baseline —
and must never be used as a clone source or cited as if they were the house
template. (The connector's `agents_duplicate` tool exists, but per this
convention it is never the path for a new client build.)

**Conflict resolved 2026-08-20 (Brett-approved):** `elevenlabs-architect`'s
`SKILL.md` previously still said *"clone the MASTER TEMPLATE"* in its Golden
rule 3 and its Guardrails recap, predating this convention. Both lines now
state the build-fresh rule (HL-004) and match Phase 3 and this file.

## 5. Procedures — branch-scoped tool family — VERIFIED LIVE

All semantics confirmed live 2026-08-15 during an agent-copy build (a new
agent created from an existing agent's branch config; client detail in that
client's folder, not here). Two traps motivated documenting this section:

- **`agents_create` silently drops a `procedures` field in `body`** —
  success, agent created, zero procedures, no error or warning. A
  config-level agent copy therefore ships a workflow whose nodes invoke
  procedures that do not exist on the new agent. An `agents_update` carrying
  `{"procedures": ...}` does not create them either (success, no effect).
- The agent-level `agents_get`'s top-level `procedures` field is a
  **metadata-only dict** keyed by `procedure_id` — each value carries
  `procedure_id`, `version_id`, `name`, `type` (e.g. `free_form`), `trigger`,
  and the `referenced_*` arrays, but never the step `content`.

The real tool family (all take `agent_id` + `branch_id`):

| # | Connector tool | One-line note |
|---|---|---|
| P1 | `agents_list_procedures` | List the branch's procedures; each entry carries a `has_draft` flag. The only working list surface — the agent-level `procedures` field is metadata-only. |
| P2 | `agents_get_procedure` | Full committed body incl. `content` (markdown with `---\nname/trigger\n---` front matter) and `guardrails`. **Fails while the procedure is draft-only** — it only resolves once a version is committed; use P1's `has_draft` (or P6) to see draft-only state. |
| P3 | `agents_create_procedure` | **Create.** Mints a brand-new draft-only stub and returns its `procedure_id` (`agtprc_…`). There is no way to specify the id — a copy always gets fresh ids. |
| P4 | `agents_update_procedure_draft` | Write the draft content — `body: {name, content, type, trigger}`; `name`/`content`/`type` required, `type` is `free_form`, `content` capped at 50k chars. |
| P5 | `agents_compile_procedures` | Compiles all drafts on the branch. **Compile does NOT commit** — after it, P2 still fails and P1 still shows `has_draft: true`. |
| P6 | `agents_get_procedure_draft` | Read a procedure's uncommitted draft content directly — reflects P4's writes immediately. |

**Commit semantics:** compiled drafts go live only when the branch's agent
`version_id` next advances. Any genuine config update on that branch does it;
when no real change is pending, the known move is a **no-op `agents_update`
(with `branch_id`) re-sending the branch's own unchanged `workflow` object**
in `body` to mint the version — set
`version_description: "commit compiled procedures"` so the version history
says why. Until that happens the agent's live procedure set is unchanged
(empty on a fresh copy) even though drafts exist, compiled, on the branch.
This flow replaces the retired `scripts/elevenlabs-commit-procedures.sh`
(which did the same dance via `curl`); its safety checks carry over as house
rules: run it only against a Sandbox branch (or the Main of a brand-new
agent still in its initial build window) — a version advance commits EVERY
compiled draft sitting on the branch — and after the no-op update, read the
branch back and confirm the `workflow` is unchanged before reporting success.

**Copy note:** workflow nodes reference procedures **by name, not by id**
(e.g. "Run the procedure: <name>") — so recreating procedures with identical
names on a new agent resolves the copied workflow with no workflow edit.

## 6. Verify-live reminder

Any field path in this file **not** explicitly marked **VERIFIED LIVE**
above is a docs-only or schema-only claim, not a confirmed live shape.
Before a configurator drafts a create/update body against a field marked
docs-only or UNVERIFIED here — most importantly the exact current hosted-Qwen
model-id string, the `agents_create` response shape, and any enum whose full
value set was cited from documentation — run a read-only tool call first and
update this file's verification tier once confirmed. This mirrors the house
unverified-schema rule already in use elsewhere in this repo (e.g.
`docs/latency-playbook.md`'s note on `optimize_streaming_latency`): never
present an unverified field shape as fact to a write call.
