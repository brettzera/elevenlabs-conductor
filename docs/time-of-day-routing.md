# Time-of-day routing — the office-status webhook runbook

The verified, end-to-end recipe for making a ConvAI agent greet and behave
differently based on whether the client's office is open **right now** —
proven live on two agents (open greeting during configured hours, closed
greeting outside them) on 2026-08-25.

**Architecture in one line:** an inbound call makes ElevenLabs POST to an
n8n webhook *before the call connects*; n8n looks up the client's schedule,
computes open/closed **in deterministic code**, and returns dynamic
variables (including the finished greeting sentence); ElevenLabs substitutes
them into the agent's first message and prompt.

Why server-side? The agent's LLM must never do date/time arithmetic or
open/closed reasoning — controlled probes on a live build showed
LLM-evaluated edge conditions ignore time and even bare boolean dynamic
variables (among sibling edges, `edge_order` list position decides, in both
directions). The webhook computes;
the agent only renders. (`api/office-status.js` in this repo is the legacy
single-client hardcoded version of the same idea; the n8n Data-Table
workflow below is the current multi-client path.)

---

## 1. n8n side

One workflow serves every client. Shape: **Webhook → Get Schedule → Compute
Status → Respond to Webhook**.

1. **Webhook node** — method `POST`, path `elevenlabs-office-status`,
   authentication `None`, respond **"Using 'Respond to Webhook' node"**
   (never "Immediately" — ElevenLabs must receive the JSON body, not
   `{"message":"Workflow was started"}`).
2. **Get Schedule** — Data Table lookup against `client_office_schedules`,
   matching column `agent_id` against `{{ $json.body.agent_id }}`.
   **Turn ON "Always Output Data".** This is load-bearing: without it, an
   unknown agent_id emits zero items, the Respond node never runs,
   ElevenLabs gets no response, and the call is rejected (424) instead of
   falling back to "closed".
3. **Compute Status** — the v2 Code node (source + format spec in the
   workspace skill `elevenlabs-n8n-office-schedule`, `references/format.md`).
   It computes `dateKey`/`weekday`/`hour` in the client's IANA timezone,
   applies `open_days`/`open_hour`/`close_hour`, then `holiday_dates` and
   `closure_windows`, and returns the
   `{"type":"conversation_initiation_client_data","dynamic_variables":{...}}`
   shape. Fail-safe: any error or missing row → closed.
   Extend the return to compose the greeting per client:
   ```javascript
   office_greeting: isOpen ? row.greeting_open : row.greeting_closed,
   next_business_day: nextBusinessDay, // optional; else the agent default renders
   ```
4. **Data Table `client_office_schedules`** — one row per agent. Columns
   (all strings): `agent_id` (the exact `agent_...` id — paste it, character
   drift here silently kills the lookup), `client_name`, `timezone` (IANA,
   e.g. `America/Boise`), `open_days` (comma-separated weekday names),
   `open_hour`, `close_hour` (24h, close exclusive), `holiday_dates`
   (`YYYY-MM-DD:Name,` comma-separated), `closure_windows`
   (`YYYY-MM-DDTHH:MM..YYYY-MM-DDTHH:MM=Name`), `greeting_open`,
   `greeting_closed` (full sentences in the client's voice; include the AI
   disclosure if the agent's prompt expects the greeting to carry it).
5. **Activate the workflow.** The production URL
   `https://<instance>.app.n8n.cloud/webhook/elevenlabs-office-status` only
   exists while the workflow is Active. The `/webhook-test/...` URL works
   only while "Execute workflow" is armed in the editor — it must never
   appear in an agent config.

## 2. ElevenLabs side (per agent — stage on Sandbox, promote manually)

1. **Conversation-initiation webhook** (Security tab / agent settings →
   "Fetch conversation initiation data from webhook"):
   - URL: the **production** n8n URL (`/webhook/`, not `/webhook-test/`).
   - Request headers: **none**, unless the n8n node expects auth. Header
     *names* must be valid HTTP tokens — a name containing spaces can kill
     the request before it is even sent.
   - Toggle `enable_conversation_initiation_client_data_from_webhook` ON.
2. **Dynamic variable placeholders** — declare all seven, with fail-safe
   defaults that assume CLOSED and a time-neutral greeting:

   | Variable | Default |
   |---|---|
   | `is_open_hours` | `false` |
   | `is_after_hours` | `true` |
   | `is_holiday_date` | `false` |
   | `holiday_name` | *(empty)* |
   | `office_local_time` | `unavailable` |
   | `next_business_day` | `the next business day` |
   | `office_greeting` | time-neutral greeting in the client's voice ("Hello and thank you for calling …") |

   The defaults render only if the webhook fails or omits a value — that is
   the last line of defence, so never put "Good evening" in a default.
3. **First message**: exactly `{{office_greeting}}`. Nothing else — the
   greeting choice (daypart, open vs closed) is n8n's job, made before the
   call connects. The agent never picks a greeting.
4. **Prompt section** — add a `# Time and office status (webhook-provided —
   authoritative)` section listing the variables and stating they are the
   sole source of truth for date/time/open-status; the agent must never
   infer these from context. Adapt to the client's rules (e.g. a client
   that must never name a closure reason keeps `holiday_name` as
   awareness-only). Business logic for closed-hours behavior (message
   taking, routing) hangs off `{{is_open_hours}}` in prompt/procedure/node
   free-text — **never in LLM edge conditions** (see the probe findings in
   the intro: the transition evaluator ignores them).
5. **Phone number assignment** decides which branch's config serves the
   call — test calls follow the number's assigned branch, so point the test
   number at the Sandbox branch while validating.

## 3. Verify (in this order)

1. **curl the production URL** with the real payload shape — one call per
   agent_id you expect to serve:
   ```bash
   curl -X POST https://<instance>.app.n8n.cloud/webhook/elevenlabs-office-status \
     -H "Content-Type: application/json" \
     -d '{"agent_id":"agent_XXXX","called_number":"+1...","caller_id":"+1...","call_sid":"test"}'
   ```
   Healthy = the `conversation_initiation_client_data` JSON with the right
   timezone and greeting. Also curl a *bogus* agent_id — you should get the
   fail-safe closed response, not a hang (that proves Always Output Data).
2. **Phone-call the agent** and confirm the open greeting.
3. **Shrink the hours in the Data Table** so "now" is outside them, call
   again, confirm the closed greeting. Restore the hours.
4. Watch the **n8n Executions tab** during the calls — every call must
   produce an execution.

## 4. Troubleshooting: error 1011 / HTTP 424 `conversation_initiation_webhook_failed`

The call dies at setup (0 seconds, empty transcript, dead air). Work the
tree top-down; "the configs look the same" is not evidence — diff them.

1. **URL is a `/webhook-test/` path** → only answers while the n8n editor
   is listening. Use `/webhook/` and Activate the workflow.
2. **Invalid request header** on the ElevenLabs webhook config (e.g. a name
   with spaces) → request dies client-side. Remove it.
3. **No Data Table row for this agent_id / lookup emits nothing** and
   "Always Output Data" is off → no response → 424. Fix the row *and* turn
   the toggle on.
4. **n8n Respond mode "Immediately"** → ElevenLabs gets the wrong body.
   Respond via the Respond-to-Webhook node.
5. **Check the n8n Executions tab for the failing call's timestamp.**
   Execution failed → open it, fix the red node. Execution succeeded →
   ElevenLabs rejected a good response (timeout or shape) — compare against
   a working agent's response. **No execution at all** → the request never
   arrived; go to 6.
6. **The corrupt-agent-document case** (learned the hard way over several
   days): an agent minted by `POST /agents/create` with a
   full copied config can be invisibly broken for the telephony pipeline —
   every API read looks perfect and byte-identical to a working agent, but
   inbound calls fail 424 with the webhook request never leaving ElevenLabs.
   Fingerprint on the failed conversation records: `agent_name`/`timezone`
   null, `authorization_method` `"public"`, `conversation_initiation_source`
   `"unknown"` (a healthy Twilio agent shows `"signed_url"`/`"twilio"`).
   Definitive isolation test: move a known-working number onto the suspect
   agent — if the same number + same webhook fails only on this agent, the
   document is the problem. **Fix: `POST /agents/{id}/duplicate`** (it
   carries workflow + procedures across, unlike create-with-copied-config),
   configure the duplicate per §2, add its new agent_id to the Data Table,
   re-point the number, retire the corrupt agent. No config write will ever
   fix the original.

## Maintenance

- New client → one Data Table row + the §2 agent config. Generate
  holiday/closure strings with the `elevenlabs-n8n-office-schedule` skill —
  never hand-compute dates.
- The webhook and table are the single source of truth for hours. Do not
  duplicate schedule facts into prompts or KB docs.
- Keep `greeting_open`/`greeting_closed` in the client's voice and aligned
  with the agent's AI-disclosure requirements.
