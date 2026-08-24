# Authentication — ElevenLabs access comes from the connector, not a key

This repo runs **exclusively in Claude Code cloud sessions** (claude.ai/code).
All ElevenLabs access goes through the **ElevenLabs connector** — the MCP
integration connected once on the claude.ai account (Settings → Connectors →
ElevenLabs), authorized against the PHMG ElevenLabs workspace. Every session
started from that account gets the connector's tools attached automatically
as `mcp__ElevenLabs__…` (e.g. `agents_get`, `agents_update`,
`agents_list_conversations`).

**There is no ElevenLabs API key in this pipeline. Anywhere.** Not in the
repo, not in a `.env`, not in the cloud environment's variables, not in
chat. The connector holds the workspace authorization server-side; sessions
never see a credential at all — which is the point of this design: nothing
to echo, nothing to leak into a transcript, nothing to commit by accident.

## The canonical check

Before the first ElevenLabs action of a run, confirm the connector is live:

1. The `mcp__ElevenLabs__…` tools are attached to the session (they appear
   in the tool listing; a subagent's own `tools:` roster names the ones it
   carries).
2. One cheap read-only call succeeds — `agents_list` with `page_size: 1`
   (or the target-agent `agents_get` the run needs anyway).

That's the whole check. There is no environment variable to test and no
header to construct.

### If the tools are missing or a call is rejected as unauthorized

The connector is not connected (or its authorization was revoked). STOP and
report the failed precondition — a subagent reports to its parent; an
orchestrating skill runs the first-run setup flow below. **Never work around
it**: no `curl` against `api.elevenlabs.io` (an unauthenticated call fails,
and "fixing" that would mean introducing a key — forbidden), no asking for a
key to be pasted into chat, a file, or an environment variable.

## Hard rules (every skill and agent)

- **The connector tools are the only ElevenLabs surface.** Never hand-roll
  HTTP against the ConvAI API, and never install or configure an alternative
  ElevenLabs client.
- **No API key exists — keep it that way.** Never read, request, store, or
  write an ElevenLabs key. The old `ELEVENLABS_API_KEY` environment-variable
  convention is retired: if that variable ever appears in an environment, or
  a `.env` containing an ElevenLabs key turns up in any client folder, flag
  it to Brett for removal — do not read it, use it, or delete it yourself.
- **`context` discipline.** Every connector tool takes a required `context`
  string (why the call is being made). Write one line describing the task —
  "feature-inventory audit of <client>'s agent" — and never put secrets,
  client PII, or transcript quotes in it.
- **Scope comes from behavior, not from auth.** The connector can reach
  every agent in the workspace, so the write-scoping rules (only the agent
  id you were given; only a Sandbox branch that is not taking live traffic)
  are what keep writes contained — see the roadmap's guardrail section.
  Treat them as absolute. Tool rosters add a second fence: read-only
  subagents carry only read/list tools, so they *cannot* write even if
  instructed to.
- **No fallback.** If a tool call fails as unauthorized: a **subagent**
  STOPs and reports exactly which precondition failed (subagents never talk
  to the human); an **orchestrating skill** (architect/engineer) runs the
  first-run setup flow below with the human. Either way, never fall back to
  `curl`, a `.env`, or a pasted key.
- This file supersedes the retired `docs/secrets.md` and any older
  secret-manager, environment-variable, or `.env` instruction found
  anywhere, including in older exports of the skills and subagents.

## First-run setup (interactive — orchestrating skills only)

On an account that has never connected ElevenLabs, the Phase 0 check fails.
When that happens, the architect/engineer skill does NOT just abort — it
walks the human through setup in chat, then resumes the original run:

1. **Tell the human what to do, in their own browser:** open claude.ai →
   Settings → Connectors, add/connect the **ElevenLabs** connector, and
   complete the authorization against the PHMG ElevenLabs workspace. No key
   is typed anywhere in this flow — the authorization happens on
   ElevenLabs' own consent screen.
2. **Note the session boundary:** connector tools are attached when a
   session starts, so a connector added mid-session may not appear in the
   current container. If the tools are still missing after the human
   confirms they connected it, tell them to start a fresh session and
   re-run the original request there.
3. **Verify end-to-end:** confirm the tools are attached, then run the
   read-only `agents_list` with `page_size: 1`. On success, state that
   first-run setup is complete and continue the run that triggered it; on
   failure (the call still comes back unauthorized — e.g. the connector was
   authorized against the wrong ElevenLabs workspace), report which step
   still fails and stop.

## What the connector does NOT cover (known gaps)

A few surfaces of the old key-based pipeline have no connector tool. They
are done by a human in the ElevenLabs UI, from a checklist the relevant
agent prepares — never worked around:

- **Pronunciation dictionaries** (create/edit rules) — `elevenlabs-dictionary-agent`
  drafts the exact rule list; Brett creates/edits the dictionary in the UI
  (Voices → Pronunciation dictionaries) and reports back the id +
  version_id; attaching the locator to an agent IS connector-doable
  (`agents_update`).
- **Workspace-level settings** (the workspace post-call webhook
  destination) — agents flag "destination unverifiable via connector" and
  name exactly what to check/set in the UI.
- **API-integration connections** (e.g. the per-client Cal.com connection) —
  `elevenlabs-calcom-setup` verifies the Cal.com side, hands Brett the UI
  checklist for the connection + six calcom_* tools, then verifies the
  result read-only.

## Other secrets (Cal.com and future integrations)

Non-ElevenLabs integration keys still follow the environment-variable
convention: a named variable on the cloud environment
(claude.ai/code → environment settings → Environment variables), e.g.
`CALCOM_API_KEY_<CLIENT_SLUG>` for a client's Cal.com key. The variable
**name** is not a secret — it is passed to subagents in their brief; the
**value** is read from the environment by variable reference only, presence
tested with `[ -n "$VAR" ]`, and never echoed, logged, written to disk, or
pasted into chat. Never diagnose a missing variable by dumping the
environment (`env`/`printenv`).

## Client workspaces

Client folders hold **no secrets** — only working artifacts (requirements
and diagnostic reports, drafts, the per-agent feedback ledger). Standard
layout: `clients/<client-slug>/` inside the repo clone, which is
gitignored wholesale because those artifacts carry client PII that must
never be committed.
