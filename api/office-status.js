// Office-status webhook for ElevenLabs ConvAI conversation initiation.
//
// LEGACY single-schedule implementation — the current multi-client path is
// the n8n Data-Table workflow documented in docs/time-of-day-routing.md.
// Kept only because a deployed copy of this endpoint may still be serving
// an agent; new clients get an n8n Data Table row instead.
//
// Computes whether the office is open RIGHT NOW in the configured timezone
// and returns the result as dynamic variables in the
// conversation_initiation_client_data shape. All date/time arithmetic
// happens here in deterministic code — never in the agent's LLM: live
// probes showed LLM-evaluated edge conditions ignore time and even bare
// boolean variables (see docs/time-of-day-routing.md).
//
// How the ElevenLabs agent must be configured to consume this response —
// the contract is identical for this endpoint and the n8n webhook (full
// spec: docs/time-of-day-routing.md §2; stage on Sandbox, promote
// manually):
//   1. Conversation-initiation webhook: agent settings → "Fetch
//      conversation initiation data from webhook" → the webhook's
//      production URL (for n8n that is the /webhook/ path, never
//      /webhook-test/), NO custom request headers, and the
//      enable_conversation_initiation_client_data_from_webhook toggle ON.
//   2. Dynamic-variable placeholders declared on the agent, with fail-safe
//      defaults that assume CLOSED: is_open_hours "false", is_after_hours
//      "true", is_holiday_date "false", holiday_name "", office_local_time
//      "unavailable" — plus, on the n8n path, office_greeting (a
//      time-neutral greeting) and next_business_day ("the next business
//      day"). Defaults render only if the webhook fails, so never put a
//      daypart like "Good evening" in one.
//   3. First message: on the n8n path, exactly {{office_greeting}} — the
//      open/closed greeting choice is the webhook's job, made before the
//      call connects; the agent never picks a greeting.
//   4. Prompt: a "# Time and office status (webhook-provided —
//      authoritative)" section naming these variables as the sole source
//      of truth for date/time/open-status. Closed-hours behavior (message
//      taking, routing) hangs off {{is_open_hours}} in
//      prompt/procedure/node free-text — NEVER in LLM edge conditions,
//      which ignore these variables.
//
// Schedule truth: open Monday–Friday, OPEN_HOUR–CLOSE_HOUR in TIMEZONE,
// except dates in CLOSURE_DATES. Fail-safe: any error → closed
// (is_after_hours "true").
//
// No secrets, no storage. Safe to expose publicly.

const TIMEZONE = "America/Boise";
const OPEN_HOUR = 9; // 09:00:00 inclusive
const CLOSE_HOUR = 19; // 19:00:00 exclusive (open through 18:59:59)

// Full-day closures through 2028 (standard US holidays). Keep in sync with
// the served client's actual closure list, which lives in that client's
// folder — never hand-compute new dates (use the
// elevenlabs-n8n-office-schedule skill).
const CLOSURE_DATES = {
  "2026-09-07": "Labor Day",
  "2026-10-12": "Columbus Day",
  "2026-11-11": "Veterans Day",
  "2026-11-26": "Thanksgiving Day",
  "2026-12-25": "Christmas Day",
  "2027-01-01": "New Year's Day",
  "2027-01-18": "Martin Luther King Jr. Day",
  "2027-02-15": "Presidents' Day",
  "2027-05-31": "Memorial Day",
  "2027-06-18": "Juneteenth (observed)",
  "2027-07-05": "Independence Day (observed)",
  "2027-09-06": "Labor Day",
  "2027-10-11": "Columbus Day",
  "2027-11-11": "Veterans Day",
  "2027-11-25": "Thanksgiving Day",
  "2027-12-24": "Christmas Day (observed)",
  "2027-12-31": "New Year's Day (observed for Jan 1 2028)",
  "2028-01-17": "Martin Luther King Jr. Day",
  "2028-02-21": "Presidents' Day",
  "2028-05-29": "Memorial Day",
  "2028-06-19": "Juneteenth",
  "2028-07-04": "Independence Day",
  "2028-09-04": "Labor Day",
  "2028-10-09": "Columbus Day",
  "2028-11-10": "Veterans Day (observed)",
  "2028-11-23": "Thanksgiving Day",
  "2028-12-25": "Christmas Day",
};

function officeStatus(now) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: TIMEZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    weekday: "long",
    hour12: false,
  }).formatToParts(now);

  const get = (type) => parts.find((p) => p.type === type)?.value;
  const dateKey = `${get("year")}-${get("month")}-${get("day")}`;
  const weekday = get("weekday");
  // Intl can render midnight as "24" with hour12: false — normalize.
  const hour = Number(get("hour")) % 24;

  const holidayName = CLOSURE_DATES[dateKey] ?? "";
  const isHoliday = holidayName !== "";
  const isWeekday = !["Saturday", "Sunday"].includes(weekday);
  const inHours = hour >= OPEN_HOUR && hour < CLOSE_HOUR;
  const isOpen = isWeekday && inHours && !isHoliday;

  return {
    is_after_hours: isOpen ? "false" : "true",
    is_open_hours: isOpen ? "true" : "false",
    is_holiday_date: isHoliday ? "true" : "false",
    holiday_name: holidayName,
    office_local_time: `${dateKey} ${get("hour")}:${get("minute")} (${weekday}) ${TIMEZONE}`,
  };
}

module.exports = (req, res) => {
  let dynamicVariables;
  try {
    dynamicVariables = officeStatus(new Date());
  } catch (err) {
    // Fail-safe: any computation error reports CLOSED, never open.
    dynamicVariables = {
      is_after_hours: "true",
      is_open_hours: "false",
      is_holiday_date: "false",
      holiday_name: "",
      office_local_time: "unavailable",
    };
  }

  res.setHeader("Cache-Control", "no-store");
  res.status(200).json({
    type: "conversation_initiation_client_data",
    dynamic_variables: dynamicVariables,
  });
};
