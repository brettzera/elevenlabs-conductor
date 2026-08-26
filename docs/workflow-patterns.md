# Workflow patterns — the topic web for multi-topic agents

House default, approved by Brett 2026-08-08 after a live client's
intent-routing overhaul.

> **Calling-surface note (2026-08-24):** the API mechanics pinned in this
> doc were verified against the raw ConvAI endpoints; the pipeline now calls
> the same API through the ElevenLabs connector MCP tools, so read
> `GET`/`PATCH …?branch_id=` as `agents_get`/`agents_update` with the
> `branch_id` parameter (same Main-by-default trap, same rejection
> behaviors). Auth is the connector — no API key (`docs/authentication.md`). When a client wants an agent that performs
**several distinct actions** (report an issue, book a meeting, reach a
human, …), wire the workflow as a **topic web**, not a hub-and-spoke with
backward edges. The proven reference implementation is a live production
build (7 nodes, 11 edges); its ids live in that client's folder, not here.

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
4. **Task → task edges are completion-gated — against the procedure.**
   Leaf → leaf edges fire only when the current path's procedure is done
   AND the caller has THEN, in their own turn, stated the new intent.
   Phrase the gate against the procedure, not re-described content: "the
   <X> intake on this path is complete — <observable signal> — and the
   caller has THEN …", with a "does not apply before the <X> intake is
   substantially complete" exclusion (§ Edges follow procedure endings).
   This stops mid-task topic drift while keeping multi-request calls
   fluid.
5. **The graph, not the LLM, executes the exits.** Terminal actions get
   dedicated nodes so they cannot be claimed-but-not-performed (a
   claimed-but-never-executed exit was a logged live failure class):
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
     mid-conversation. Two separate client builds have hit it (one on 4/4
     calls in a test batch across every wrap-up route), so treat "leaf
     edge → bare end node" as a defect on sight, not an edge case. The
     fix that belongs here is rule 7's: the sign-off rides the SOURCE
     agent node's prompt, which is already rendering a turn. Inserting a
     **dedicated closing node** between the leaves and the terminal node
     is the tempting alternative — it states the trigger once instead of
     once per leaf — but live builds recorded it failing in both
     available forms (an unconditional outbound edge generated no turn at
     all; a trivially-true LLM-conditioned one generated a turn but
     filled it from elsewhere in the graph and made the exit
     non-deterministic). A completion-worded LLM condition on that edge
     is the third variant — **adopted as house style by Brett 2026-08-26**
     from the Litster Frost v2 build, with the condition keyed to the
     PROCEDURE's ending plus one observable signal, never to vague
     content (§ Edges follow procedure endings).
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

## Surface ownership — the three-layer text architecture

House default (approved by Brett 2026-08-09) for **every agent that has a
workflow**. Each instruction lives on exactly one of three surfaces:

| Surface | Owns | Never carries |
|---|---|---|
| **Global prompt** | Persona · universal speech/capture rules · universal hard rules · closing · the workflow pointer | Path-specific logic, question lists, tool mechanics |
| **Workflow node** | The three-clause invocation (§ The subagent-node template): **"Call start_procedure first. Run the procedure: <name>. Nothing outside the procedure is asked here."** · topic-wide tool contracts, only where the node owns a tool | Path-framing essays (the node LABEL names the path), granular question ordering, business facts, restated universal rules |
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
   deliberate defence-in-depth backed by a feedback-ledger row in the
   client's folder — cited, never silent.
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
6. **Collected once, never re-asked (the carried-info rule).** Any item the caller has
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

The proven reference implementation is a live production branch; its ids
live in that client's folder, not here.

## The subagent-node template (Brett, 2026-08-26)

House default for every procedure-owning subagent node, taken verbatim
from the Litster Frost v2 build (its `node_injury` / "New injury intake"
pairing; the full extraction lives in that client's folder). The node's
ENTIRE instruction text is three clauses:

> Call start_procedure first. Run the procedure: <exact procedure name>.
> Nothing outside the procedure is asked here.

That's 16 words on the exemplar. Rules:

1. **Word budget.** The three-clause form is the target (~12–20 words).
   Anything past ~40 words means the node is carrying content another
   surface owns — relocate it (questioning → procedure, universals →
   global prompt, facts → KB). The ONLY sanctioned addition is a
   topic-wide tool contract on a node that owns a tool, stated once at
   full strength (Surface-ownership rule 3).
2. **Deterministic by construction, not by emphasis.** The determinism
   comes from the closed loop, not from adding words: the node names the
   procedure by its exact registered name, and the procedure's `trigger`
   is anchored back to that one node ("Use this procedure when the
   conversation has reached the <X> step (<node_id>). Does not apply to
   any other step."). The scope-closer ("Nothing outside the procedure is
   asked here.") removes the model's only alternative to starting the
   procedure. Never restate, paraphrase, or duplicate any procedure step
   at the node — every extra sentence is a competing instruction that
   makes the procedure LESS certain to run.
3. **Path framing lives in the node label**, not the prompt text — the
   label ("New injury / accident intake") is what edges and triggers
   reference; the prompt spends no words on it.
4. **Node config stays inherited.** Leave the node's `conversation_config`
   fields `null` (inherit branch defaults) except a deliberate, named
   override (e.g. a per-node LLM pin); no node-level `tool_ids` /
   `additional_knowledge_base` unless the node genuinely owns them.

## Edges follow procedure endings (Brett, 2026-08-26)

Edge conditions off a procedure-owning node are phrased against the
PROCEDURE's ending — never against re-described conversational content.
Three tiers, from the same exemplar:

1. **Exit edge (path done → closing/wrap-up):** keyed explicitly to the
   procedure plus ONE observable signal from its final steps —
   > The <name> procedure is complete — contact details captured — and
   > the caller has confirmed the details are correct.
   The signal must be something the procedure's own closing steps
   produce (read-back confirmed, message taken), so drafting the
   procedure's ending and this condition is ONE coordinated act — the
   procedures configurator names the completion signal; the flow
   configurator keys the edge to it.
2. **Lateral task → task edges:** interrupt-gated on the procedure —
   "the <X> intake on this path is complete/substantially complete — and
   the caller has THEN, in their own turn, raised <new topic>", with an
   explicit "does not apply before the <X> intake is substantially
   complete" exclusion. The procedure is protected from mid-flow
   abandonment.
3. **The privileged content-immediate edge:** exactly one class of edge
   may ignore an unfinished procedure — the escalation/named-person
   route — and it must SAY so: "This applies immediately, whether or not
   the <X> intake is finished." Any other content-immediate edge off a
   procedure-owning node is a defect.

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
