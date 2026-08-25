# Behavioral guardrails — the three-layer set

House default, approved by Brett 2026-08-08 and proven on a live
sales-guardrails staging (no-timeline-commitments + no-technical-advice,
simulation-tested). Client-specified behavioral guardrails ("the agent must
never say/do X") are staged as a **three-layer set**, never a prompt rule
alone:

1. **Prompt hard rule** (`elevenlabs-persona-configurator`) — a bullet in
   the system prompt's `# Hard rules` section, written **intent-based**
   (cover the information class, e.g. "any technical information", not just
   one phrasing), and with an explicit KB override when the forbidden
   content could be KB-sourced.
2. **Native custom guardrail** (`elevenlabs-quality-safety-configurator`) —
   in `platform_settings.guardrails.custom.config.configs`. Prefer
   `trigger_action: retry` with feedback text that tells the agent to
   acknowledge + redirect so the call continues (only `end_call`/`retry`
   exist). The API 422/400s `retry` under `execution_mode: streaming` —
   `retry` requires `blocking`, which puts that check in the live response
   path: state the latency cost in the hand-off, per
   [latency-playbook.md](latency-playbook.md).
3. **A paired evaluation criterion per guardrail** (same configurator) —
   worded so calls where the topic never arises score *success* (not
   unknown), so any breach is visible per-call in conversation review and
   feeds the improvement loop.

Preserve existing moderation/prompt-injection guardrails and existing
criteria — **append, never replace**.

Like every house doc, this file is Brett-gated: no skill or agent edits it
on its own initiative — a proposed change goes in a repo-change note for
Brett (see the standing rules in the repo root `CLAUDE.md`).
