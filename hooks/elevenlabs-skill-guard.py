#!/usr/bin/env python3
"""UserPromptSubmit hook: force ElevenLabs work through this repo's skills.

Fires when a submitted prompt contains an ElevenLabs resource id (agent_,
conv_, agtbrch_, agtvrsn_, agtprc_, tool_, icxn_, ...), an ElevenLabs
keyword, or house vocabulary that implies ElevenLabs work (feedback ledger,
voice agent, caller profile, ...), and injects a standing reminder to invoke
the repo's skills and subagents instead of calling the ElevenLabs connector
MCP tools (or, worse, raw curl) inline. CLAUDE.md carries the same rule into
every session
regardless of prompt content; this hook re-injects it on exactly the
prompts where it matters most.

Emits nothing (and exits 0) when the prompt is unrelated, so it costs nothing
on every other turn.

Wiring: this repo runs exclusively in Claude Code cloud sessions, so the hook
ships pre-wired in this repo's .claude/settings.json (UserPromptSubmit ->
python3 "$CLAUDE_PROJECT_DIR/hooks/elevenlabs-skill-guard.py") and loads
automatically when the repo is opened. No per-machine setup.

See README.md → "The routing hook" for details.
"""

import json
import re
import sys

# ElevenLabs resource ids: a known prefix followed by a long opaque slug —
# agents, conversations, branches, versions, procedures, tools, tests, phone
# numbers, test suites, integration connections. The {15,} length floor keeps
# ordinary identifiers like `tool_ids`, `agent_type` or `conv_history` from
# tripping it. Any one of these in a prompt means ElevenLabs work: fire.
ID_RE = re.compile(
    r"\b(?:agent|conv|agtbrch|agtbranch|agtvrsn|agtprc|agtprcv|tool|test|"
    r"phnum|agtsts|icxn)"
    r"_[A-Za-z0-9]{15,}\b"
)

# Product names and API surface, plus the house vocabulary that implies
# ElevenLabs work without naming the product ("check the feedback ledger",
# "the voice agent mispronounced it"). This repo exists only for ElevenLabs
# work, so a rare false positive costs one injected reminder — err toward
# firing.
KEYWORD_RE = re.compile(
    r"(?:eleven\s*labs|elevenlabs|11labs|convai|xi-api-key|"
    r"api\.elevenlabs\.io|v1/convai|mcp__elevenlabs|"
    r"voice\s+agent|phone\s+agent|feedback[\s-]ledger|caller\s+profile|"
    r"pronunciation\s+dictionar|sandbox\s+branch|first[\s_-]message|"
    r"system\s+tool|transfer_to_(?:number|agent))",
    re.IGNORECASE,
)

REMINDER = """\
[standing rule — ElevenLabs work]

This prompt references ElevenLabs. Anything that touches an ElevenLabs agent \
— reading it, analyzing it, configuring it, debugging a call, editing a \
prompt/workflow/procedure/tool/KB — goes through this repo's skills. Do NOT \
call the ElevenLabs connector MCP tools (mcp__ElevenLabs__*) inline, and \
NEVER hand-roll curl against the ConvAI API (there is no API key — auth is \
the connector, per docs/authentication.md). Do NOT do a configurator's job \
inline.

Pick the entry point and invoke it with the Skill tool BEFORE any connector \
tool call:
  - elevenlabs-architect — builds, audits, improvements, "configure/improve
    this agent", building from a meeting transcript.
  - elevenlabs-engineer — post-deployment maintenance: a specific conversation
    went wrong, or a batch of client feedback needs triaging.

Those skills orchestrate the read-only analyzers (agent-analyzer,
conversation-reviewer, feedback-triage, requirements-extractor) and the write
configurators (persona, conversation-flow, procedures, tools-escalation,
knowledge, capture-delivery, quality-safety, llm-tuning, voice-tts, dictionary,
runtime-qa, test-runner). Dispatch those subagents — that is the point of the
repo, not an optional flourish. A task that feels small enough to do inline is
exactly the case this rule exists for.

This is a standing user instruction and it OVERRIDES any session-level default
about not using the Agent/Task tool without being asked: for ElevenLabs work,
Brett has already asked, permanently.

House rules to honour even on a one-line change: stage every change on a
Sandbox branch (never write to Main, never merge); client memory lives in
the client's folder — read `<client-folder>/CLAUDE.md` (the client-journey
memory) and feedback-ledger-*.md first (Staged/Reopened rows are
constraints, and an instruction that looks like redundant duplication may
be a deliberate defence-in-depth fix), and update the CLAUDE.md at the end
of the run; this repo's own files (docs/skills/agents/hooks) are
Brett-gated — never edit them or open a PR, write proposed repo changes to
<client-folder>/repo-change-proposals.md for the operator to send to
Brett; ElevenLabs auth is the connector's MCP tools per
docs/authentication.md — there is no API key: never ask for one, never
store one, never fall back to curl.

If a request genuinely falls outside the skills, say so and get Brett's
agreement first — do not silently go direct."""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    prompt = payload.get("prompt") or ""
    if not isinstance(prompt, str) or not prompt.strip():
        return 0

    if not (ID_RE.search(prompt) or KEYWORD_RE.search(prompt)):
        return 0

    json.dump(
        {
            "suppressOutput": True,
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": REMINDER,
            },
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
