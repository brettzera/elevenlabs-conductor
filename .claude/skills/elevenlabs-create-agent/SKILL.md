---
name: elevenlabs-create-agent
description: Reference skill holding house conventions for creating a brand-new ElevenLabs ConvAI agent from scratch — the connector MCP tool list, build-fresh baseline field values, and the KB-attachment shape. Not meant for direct human invocation; elevenlabs-architect and elevenlabs-engineer read it before any create/update call. Triggers only as a read target when another skill says "read references/api.md" or "per the create-agent house style."
---

# ElevenLabs → Create Agent (reference skill)

This is a **reference skill, not an interviewable one**. Nothing here talks to
a human or an end caller. `elevenlabs-architect` (Phase 3, brand-new-agent
path) and `elevenlabs-engineer` read `references/api.md` before issuing any
`agents_create`/`agents_update` call against a brand-new agent, instead of
re-deriving tool usage or default values inline each time.

## Purpose

House conventions for building a brand-new ElevenLabs ConvAI agent — the
connector tool list, the baseline field values a fresh `agents_create` should carry,
and the exact knowledge-base attachment shape — collected in one place so
every skill/configurator that ever creates an agent uses the same facts.

## The convention: build fresh, no MASTER TEMPLATE clone

**Decided by Brett, 2026-08-10: new agents are built directly from the
documented house defaults in `references/api.md`, not cloned from an
existing agent in the account.** No single agent in the account has ever
been designated the canonical build baseline. The only agents in the account
named "MASTER TEMPLATE" are BDM demo agents — sales/demo material, not a
house build standard — and must not be used as a clone source or referenced
as if they were one.

This means a brand-new build lays down `name`, `first_message`, `language`,
`llm`, `asr`, and `tts.model_id` from the documented defaults (voice is
always chosen per client — see below), then layers on whatever the
requirements call for via the usual configurators. It does **not** start by
reading or copying another agent's config.

## Where the mechanics live

`references/api.md` has the concrete detail: the full connector tool list
(tool + parameters + required fields), the build-fresh baseline field values,
the verified knowledge-base-attachment field shape, the no-MASTER-TEMPLATE
rationale, the procedures tool family with its commit semantics, and which
fields still need a live read before a configurator drafts against them.
Read it before any create/update call — don't re-derive these constants here
or anywhere else.

## Scope note

This skill documents conventions only. It never calls the ElevenLabs
connector tools itself — the orchestrating skills and configurators that read
it are the ones that create/update agents, and they carry their own read/write guardrails
(Sandbox-first, explicit-apply-only, one-agent-per-run, etc. — see
`elevenlabs-architect`'s and `elevenlabs-engineer`'s own SKILL.md files).
