# Workflow patterns — the topic web for multi-topic agents

House default, approved by Brett 2026-08-08 after the reference client's (CL-A)
intent-routing overhaul.

> **Calling-surface note (2026-08-24):** the API mechanics pinned in this
> doc were verified against the raw ConvAI endpoints; the pipeline now calls
> the same API through the ElevenLabs connector MCP tools, so read
> `GET`/`PATCH …?branch_id=` as `agents_get`/`agents_update` with the
> `branch_id` parameter (same Main-by-default trap, same rejection
> behaviors). Auth is the connector — no API key (`docs/authentication.md`). When a client wants an agent that performs
**several distinct actions** (report an issue, book a meeting, reach a
human, …), wire the workflow as a **topic web**, not a hub-and-spoke with
backward edges. Reference implementation: the CL-A build, Main
(`agent_5501kx7g6fhmeky83hsgebetmv2d`) — 7 nodes, 11 edges.

## The pattern

```
start → Triage ──→ Topic A ⇄ Topic B          (direct leaf↔leaf edges)
              ──→ Topic A ──→ Escalation      (one hop from EVERY leaf)
              ──→ Topic B ──→ Escalation
              ──→ Escalation ──→ [phone_number node]   (graph-owned transfer)
              ──→ [end node] ←── Topic A / Topic B     (graph-owned wrap-up)
```

1. **Triage is the entry router only.** One agent node after `start` whose
   edges classify the caller's first-stated intent. It never sees the
   caller again — no backward edges returning to it for re-routing.
2. **Every topic leaf connects directly to every other leaf the caller
   could plausibly need next.** A caller who finishes an issue report and
   says "can you also book me a meeting" moves in ONE hop, with the intent
   utterance intact. Routing backward through triage costs a conversational
   turn and risks the caller having to repeat themselves (transitions are
   evaluated per user turn — chaining two hops off one utterance is not
   guaranteed).
3. **Escalation is one hop from everywhere, ungated.** Leaf → escalation
   edges fire on an explicit "get me a person" at ANY point — never require
   the current task to be finished first. The caller asking for a human is
   by definition losing patience; that path must be the shortest.
4. **Task → task edges are completion-gated.** Leaf → leaf edges fire only
   when the current task is done (e.g. "summary read back and confirmed" /
   "booking action complete") AND the caller states the new intent. This
   stops mid-task topic drift while keeping multi-request calls fluid.
5. **The graph, not the LLM, executes the exits.** Terminal actions get
   dedicated nodes so they cannot be claimed-but-not-performed (the FB-005
   failure class):
   - **Wrap-up:** an `end`-type node with completion-gated edges from
     triage (wrong number / "never mind") and every task leaf ("nothing
     else needed"). Keep the `end_call` system tool enabled as a fallback
     initially; consider tightening after live/sim evidence.
     **The closing must be spoken by a node that already renders a turn.**
     An `end`-type node carries no prompt (schema pins below), so an edge
     pointing straight at it fires `end_call` in the SAME step as the
     caller's last utterance — the line goes dead with no sign-off, even
     when the global prompt has a perfectly good closing section that is
     simply never reachable. Callers experience this as being hung up on
     mid-conversation. Two clients have now hit it (CL-C FB-002, CL-D
     FB-001), the second on 4/4 calls in a test batch across every
     wrap-up route, so treat "leaf edge → bare end node" as a defect on
     sight, not an edge case. The fix that belongs here is rule 7's:
     the sign-off rides the SOURCE agent node's prompt, which is already
     rendering a turn. Inserting a **dedicated closing node** between the
     leaves and the terminal node is the tempting alternative — it states
     the trigger once instead of once per leaf — but CL-C recorded it
     failing in both available forms (an unconditional outbound edge
     generated no turn at all; a trivially-true LLM-conditioned one
     generated a turn but filled it from elsewhere in the graph and made
     the exit non-deterministic). A completion-worded LLM condition on
     that edge is a third variant, currently staged but unproven at
     CL-D — do not adopt it as a pattern until simulation evidence exists.
   - **Transfer:** a `phone_number`-type node downstream of the escalation
     agent node, entered via an edge gated on the intake being complete
     (e.g. "name AND account both collected — items gathered earlier in
     the call count; do not re-ask" — an instance of the carried-info
     rule, § Surface ownership rule 6). The escalation agent node does the
     gating conversation; the graph node does the handoff. Keep the
     `transfer_to_number` system tool enabled as a fallback initially.
6. **Edge-condition house style:** own-words phrasing, concrete example
   utterances (including short unambiguous FIRST-turn statements), and
   explicit "does not apply if…" exclusions naming the sibling intents, so
   parallel edges partition cleanly instead of overlapping.
7. **Prompt language must match the graph.** Node prompts say the
   conversation "moves straight to" the other paths / the transfer step /
   the wrap-up — never "return to the main menu", never "use the transfer
   tool". Sign-off and handoff wording lives in the SOURCE agent node's
   prompt (terminal node types can't carry any — see schema pins below).

## Surface ownership — the three-layer text architecture (HL-003)

House default (approved by Brett 2026-08-09) for **every agent that has a
workflow**. Each instruction lives on exactly one of three surfaces:

| Surface | Owns | Never carries |
|---|---|---|
| **Global prompt** | Persona · universal speech/capture rules · universal hard rules · closing · the workflow pointer | Path-specific logic, question lists, tool mechanics |
| **Workflow node** | One-line path framing · path boundaries ("nothing outside the procedure is asked here") · topic-wide tool contracts · **"Run the procedure: <name>"** | Granular question ordering, restated universal rules |
| **Procedure** | The ordered granular questioning — "Ask for the following one at a time, in order", one ask per numbered step, bare-action steps | Routing, tool contracts, restated global/node rules |

(Amended 2026-08-20, Brett-approved: the global prompt's persona paragraph
carries one environment sentence — medium + caller state — and its universal
speech rules include the TTS-output formatting baseline; both specified in
`docs/house-persona.md` § System-prompt skeleton / § TTS-output formatting.)

Rules of the architecture:

1. **The prompt defers to the workflow, verbatim.** The pointer section's
   first sentence is exactly "Refer to the workflow." House reference wording
   (from the proven implementation):

   > \# How this call is structured
   > Refer to the workflow. It moves the call between steps. Each step's
   > instructions tell you which procedure to run; the procedure gives you
   > the exact questions to ask, in order. Never run another step's
   > questions, and never act for a step the workflow has not reached.

2. **Single-sourcing.** An instruction exists on one surface only; restating
   a global rule in a node, or a node contract in a procedure, is the
   prompt-bloat failure this rule kills. The ONE sanctioned exception is
   deliberate defence-in-depth backed by a feedback-ledger row (the FB-011
   lesson) — cited, never silent.
3. **Anti-hallucination tool contracts live at the node** that owns the
   tool ("nothing is booked until `<tool>` returned success — never say
   it before"), stated once at full strength.
4. **Procedure triggers are step-anchored** — "Use this procedure when the
   conversation has reached the <X> step and …", with explicit
   does-not-apply exclusions naming the other steps. Procedures are
   agent-global and WILL misfire from the wrong node otherwise (observed
   live on the reference agent).
5. **Every path that collects anything names a procedure** — even a
   two-item transfer intake gets one, so the architecture stays uniform.
6. **Collected once, never re-asked (HL-005).** Any item the caller has
   already provided in this call is never asked for again by a later step,
   path, or procedure — the agent repeats what it has and asks the caller
   to confirm it is still correct ("I have your name as Jane Smith — is
   that right?"), then continues. The rule lives ONCE, in the global
   prompt (it is a universal capture rule — see the house-persona
   skeleton); procedures still list the item as a numbered step (the step
   is satisfied by confirm-instead-of-ask, so never draft a step that
   forces an unconditional re-ask), and intake gates count items gathered
   earlier in the call — the transfer-intake gate in the topic-web
   pattern above is an instance of this rule.
7. **Sizing yardstick** (reference build, 3 topic paths + transfer):
   global prompt ≈3.8k chars · all node text ≈6.3k · procedures ≈8k. A
   workflow agent whose global prompt exceeds ~5k chars almost certainly
   holds text a node or procedure should own — treat that as the
   analyzer's prompt-bloat red flag.

Reference implementation: CL-A, branch "Sandbox -
Workflow-led prompt strip" (`agtbrch_3401kzj7kdv0fcpv0n02ajgt8db8`).

## When the web applies — and when it doesn't

- **2–4 topic leaves: full web is the default.** With one terminal
  transfer leaf the mesh is only a handful of extra edges.
- **~5+ leaves:** the mesh grows quadratically and the duplicated intent
  conditions become a real maintenance tax (a wording tweak must land on
  every edge carrying that intent). Consider a hybrid: web the
  high-traffic pairs, keep rare cross-traffic on a re-triage path — and
  say so in the draft.
- **One action only:** a workflow may be overkill; weigh prompt-only logic
  per the flow configurator's existing guidance.

## Pinned live-API schema (confirmed against production, 2026-08-08)

- **One edge object per unordered node pair.** A second edge between the
  same two nodes is rejected (422 "Duplicate edge") regardless of
  direction. Bidirectional leaf↔leaf routing = ONE edge with a
  `forward_condition` and a `backward_condition`. The editor renders such
  a pair as a single connector.
- **`edge_order`** on each node must list its outgoing edges — including
  edges where the node is the backward-direction source.
- **Minimal node types carry no label and no prompt:** `start`, `end`
  (`{type, position, edge_order}`; server adds `return_when_nested: true`),
  and `phone_number` (`{type, position, edge_order, custom_sip_headers,
  transfer_destination: {type: "phone", phone_number}, transfer_type:
  blind|conference|sip_refer, uui, post_dial_digits}`; server adds
  `require_acceptance: false`). The type constant for the transfer node is
  **`phone_number`**, not "transfer". `require_acceptance` exists only on
  the `transfer_to_number` system tool's `transfers[]`, not on the node —
  `transfer_type: "blind"` is the node-side equivalent of blind +
  no-acceptance.
- **PATCH rejects a prompt carrying BOTH inline `tools` and `tool_ids`**
  (422 `both_tools_and_tool_ids_provided`) — but GET returns both, so a
  round-tripped `conversation_config` is unsendable. Send `{"workflow":…}`
  alone; send prompt-text edits as a minimal deep-merge body
  `{"conversation_config":{"agent":{"prompt":{"prompt":"…"}}}}`.
- **Branch mechanics** (confirmed live 2026-08-09): `GET …/branches`
  hides archived branches — add `?include_archived=true`. Create:
  `POST /v1/convai/agents/{agent_id}/branches` with `{name, description,
  parent_version_id, parent_branch_id}` — `parent_version_id` is required
  (from the parent branch's `version_id`; omitting it 422s); returns
  `{created_branch_id, created_version_id}`. Target a branch with
  `?branch_id=` on the agent GET/PATCH — **omitted, both default to
  Main**, so a sandbox-intended PATCH silently edits the live branch.
- **Archived branches reject PATCH** (`publish_to_archived_branch`).
  Merging a sandbox into Main auto-archives it — re-check
  `GET …/branches` before writing if any time has passed.
- **Editor-tab hazard:** a save from a stale ElevenLabs UI workflow-editor
  tab silently reverts config the tab predates (observed live: prompt
  edits reverted, edges kept). After any UI session on a branch, re-verify
  via GET; tell Brett to refresh open editor tabs before staging changes.
