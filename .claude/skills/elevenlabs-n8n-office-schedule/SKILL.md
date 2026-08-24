---
name: elevenlabs-n8n-office-schedule
description: Generate copy-pastable schedule strings for the n8n client_office_schedules Data Table that drives ElevenLabs office-status routing (the hours/holiday webhook). Use whenever Brett needs holiday dates, closure windows, or a full client row formatted for n8n — triggers on "n8n dates", "holiday string", "closure window", "office hours row", "closed from X to Y", "add [holiday] for [client]", or a new client needing time-based routing. Handles full-day closures (YYYY-MM-DD:Name) and time-spanning closures (e.g. "closed Wednesday 5pm through Monday 8am for Thanksgiving"), which use the extended closure_windows format and the v2 Code node.
---

# n8n office-schedule string generator

You produce **exact, copy-pastable cell values** for the n8n Data Table
`client_office_schedules` used by the "ElevenLabs Office Status Webhook"
workflow. The consumer is deterministic code, so a malformed entry is
**silently ignored** (fail-safe design) — precision here is the whole job.

The format spec, worked examples, and the full v2 Code-node source live in
[references/format.md](references/format.md). Read it before generating
anything.

## Hard rules

1. **Never do date arithmetic in your head.** Every date you emit — "the
   Wednesday before Thanksgiving", "Labor Day 2029", "next Monday" — must
   be verified with a real computation before it goes in the output, e.g.:
   `node -e "console.log(new Date('2026-11-25T12:00:00Z').toLocaleDateString('en-US',{weekday:'long',timeZone:'UTC'}))"`
   Emitting an unverified weekday/date is the one unforgivable failure of
   this skill. (LLM date arithmetic being unreliable is the reason this
   whole webhook exists — see C-023/C-024 in docs/cross-client-lessons.md.)
2. **Full-day closures** use the v1 `holiday_dates` format:
   `YYYY-MM-DD:Holiday Name` — comma-separated, no space after commas, no
   trailing comma. Names may contain spaces and parentheses, never commas
   or colons.
3. **Time-spanning closures** ("closed Wed 5pm through Mon 8am") use the
   `closure_windows` column: `YYYY-MM-DDTHH:MM..YYYY-MM-DDTHH:MM=Name` —
   24-hour clock, the client's LOCAL time, start inclusive, end exclusive
   (the end is the reopen moment). Same comma-separation rules. Names may
   never contain commas or `=`.
4. **closure_windows requires the v2 Code node.** If the client's workflow
   might still run v1 (v1 has no `closure_windows` handling and ignores it
   silently), include the full v2 source from references/format.md in your
   output and say plainly: "paste this over the Code node once, or the
   window will be silently ignored."
5. **Ask, don't guess**, when the request is ambiguous: missing year,
   unclear which weekday anchors to the holiday, or a reopen time not
   stated ("closed for Thanksgiving weekend" — reopening Monday at what
   time?). One tight AskUserQuestion covering all gaps at once.
6. **Self-check before presenting:** run the probe script in
   references/format.md §Self-check against your generated strings — it
   evaluates the same logic the Code node runs, at instants just inside
   and outside each new closure — and show the probe results with the
   output. Never present unprobed strings.

## Output shape

A labeled block per Data Table cell, ready to paste:

```
holiday_dates:
2026-09-07:Labor Day,2026-11-26:Thanksgiving Day,...

closure_windows:
2026-11-25T17:00..2026-11-30T08:00=Thanksgiving closure
```

Plus, when a full row is requested: `agent_id`, `client_name`, `timezone`
(IANA), `open_days`, `open_hour`, `close_hour` — same conventions as the
seed row in references/format.md.

## Scope notes

- This skill only *writes strings* (and hands over the v2 code when
  needed). It never calls the ElevenLabs API and never edits n8n — Brett
  pastes. That's why it's a skill, not a subagent: no API access, no
  context isolation needed, and the human paste step is the review gate.
- The agent-side wiring (relay node, is_after_hours variable) is the
  architect/engineer skills' territory — route agent-config changes there.
