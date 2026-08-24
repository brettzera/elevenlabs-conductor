// Office-status webhook for ElevenLabs ConvAI conversation initiation.
//
// Computes whether the Litster Frost office is open RIGHT NOW in
// America/Boise and returns the result as dynamic variables in the
// conversation_initiation_client_data shape. All date/time arithmetic
// happens here in deterministic code — never in the agent's LLM (see
// clients/litster-frost/hours-gate-fix-report.md and candidates C-023/C-024
// in docs/cross-client-lessons.md for why).
//
// Schedule truth (must match the agent prompt's "# Time and office status"
// section — update BOTH places, or shrink the prompt section once this
// endpoint is authoritative):
//   Open: Monday–Friday, 09:00:00–18:59:59 America/Boise,
//         except dates in CLOSURE_DATES.
//   Fail-safe: any error → closed (is_after_hours "true").
//
// No secrets, no storage. Safe to expose publicly.

const TIMEZONE = "America/Boise";
const OPEN_HOUR = 9; // 09:00:00 inclusive
const CLOSE_HOUR = 19; // 19:00:00 exclusive (open through 18:59:59)

// Verbatim from the agent prompt's closure list (via the extraction in
// clients/litster-frost/hours-gate-fix-report.md, Phase A section).
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
