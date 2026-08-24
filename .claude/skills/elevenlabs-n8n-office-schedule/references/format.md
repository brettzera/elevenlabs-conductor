# client_office_schedules — format spec and v2 Code node

The n8n Data Table behind the "ElevenLabs Office Status Webhook" workflow.
One row per client agent. All columns are strings.

## Columns

| Column | Format | Example |
|---|---|---|
| `agent_id` | ElevenLabs agent id (lookup key) | `agent_9601m01gh938ezhv3kkvwq2kv5at` |
| `client_name` | human label only | `Litster Frost Injury Lawyers` |
| `timezone` | IANA zone | `America/Boise` |
| `open_days` | comma-separated full weekday names | `Monday,Tuesday,Wednesday,Thursday,Friday` |
| `open_hour` | 24h opening hour, number-string, inclusive | `9` (opens 09:00:00) |
| `close_hour` | 24h closing hour, number-string, exclusive | `19` (open through 18:59:59) |
| `holiday_dates` | v1 full-day closures: `YYYY-MM-DD:Name`, comma-separated | `2026-11-26:Thanksgiving Day,2026-12-25:Christmas Day` |
| `closure_windows` | v2 timed closures: `YYYY-MM-DDTHH:MM..YYYY-MM-DDTHH:MM=Name`, comma-separated | `2026-11-25T17:00..2026-11-30T08:00=Thanksgiving closure` |

Formatting rules for both list columns: no space after commas, no trailing
comma, names never contain commas; `holiday_dates` names also never contain
colons; `closure_windows` names never contain `=`.

`closure_windows` semantics: times are the client's **local** time
(the row's `timezone`); start is inclusive, end is **exclusive** — the end
is the moment the office reopens. A window overrides open_days/open_hour
entirely while active. Windows may span any number of days and may overlap
each other and holidays harmlessly (any one match closes).

## Worked example — "closed from Wednesday 5pm to Monday 8am for Thanksgiving" (2026)

Thanksgiving 2026 = Thursday 2026-11-26 (verified). Wednesday before =
2026-11-25; the following Monday = 2026-11-30 (both verified).

```
closure_windows:
2026-11-25T17:00..2026-11-30T08:00=Thanksgiving closure
```

Behavior: Wed until 16:59 open (normal hours), Wed 17:00 closed, Thu–Sun
closed regardless of weekday rules, Mon 07:59 closed by the window — and
Mon 08:00–08:59 STILL closed, now by normal hours (this row's open_hour is
9). **Windows only ever extend closure; they cannot force the office open
outside normal hours.** If a client genuinely reopens earlier than their
normal open_hour after a closure, that is an open_hour/hours question to
raise with Brett, not something a window can express. When the stated
reopen time equals or precedes normal opening, the window's end just needs
to be ≤ the normal open moment — ending it at the reopen time stated by
the client keeps the string self-documenting.

## v2 Code node (handles holiday_dates AND closure_windows)

v1 (shipped in the original build prompt) ignores `closure_windows`
silently. Paste this over the Code node's contents to upgrade — it is a
superset of v1's tested logic and keeps the identical fail-safe and
response shape:

```javascript
// Fail-safe wrapper: ANY error or missing schedule → closed.
function closedResponse(note) {
  return {
    type: "conversation_initiation_client_data",
    dynamic_variables: {
      is_after_hours: "true",
      is_open_hours: "false",
      is_holiday_date: "false",
      holiday_name: "",
      office_local_time: note || "unavailable",
    },
  };
}

try {
  const row = $input.first().json;
  if (!row || !row.timezone) {
    return [{ json: closedResponse("no schedule row for this agent_id") }];
  }

  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: row.timezone,
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit",
    weekday: "long", hour12: false,
  }).formatToParts(new Date());
  const get = (t) => parts.find((p) => p.type === t)?.value;

  const dateKey = `${get("year")}-${get("month")}-${get("day")}`;
  const weekday = get("weekday");
  const hour = Number(get("hour")) % 24; // Intl can emit "24" at midnight
  // Local-time ISO minute string; compares lexicographically.
  const localNow = `${dateKey}T${String(hour).padStart(2, "0")}:${get("minute")}`;

  // v1: full-day holiday closures — "YYYY-MM-DD:Name"
  const holidays = {};
  for (const entry of String(row.holiday_dates || "").split(",")) {
    const [d, ...name] = entry.trim().split(":");
    if (/^\d{4}-\d{2}-\d{2}$/.test(d)) holidays[d] = name.join(":") || "closure";
  }

  // v2: timed closure windows — "YYYY-MM-DDTHH:MM..YYYY-MM-DDTHH:MM=Name"
  const windows = [];
  for (const entry of String(row.closure_windows || "").split(",")) {
    const m = entry.trim().match(
      /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})\.\.(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})=(.+)$/
    );
    if (m && m[1] < m[2]) windows.push({ start: m[1], end: m[2], name: m[3] });
  }

  const activeWindow = windows.find((w) => localNow >= w.start && localNow < w.end);
  const holidayName = activeWindow ? activeWindow.name : (holidays[dateKey] ?? "");
  const isClosure = holidayName !== "";
  const openDays = String(row.open_days || "").split(",").map((d) => d.trim());
  const isOpenDay = openDays.includes(weekday);
  const inHours = hour >= Number(row.open_hour) && hour < Number(row.close_hour);
  const isOpen = isOpenDay && inHours && !isClosure;

  return [{ json: {
    type: "conversation_initiation_client_data",
    dynamic_variables: {
      is_after_hours: isOpen ? "false" : "true",
      is_open_hours: isOpen ? "true" : "false",
      is_holiday_date: isClosure ? "true" : "false",
      holiday_name: holidayName,
      office_local_time: `${localNow} (${weekday}) ${row.timezone}`,
    },
  } }];
} catch (e) {
  return [{ json: closedResponse("error: " + e.message) }];
}
```

## Self-check (run before presenting any generated strings)

Save the generated cell values into a small probe and run it — it
replicates the Code node's evaluation at chosen instants. Pick probes just
inside and outside every new closure boundary (and one ordinary open
moment):

```bash
node -e '
const row = {
  timezone: "America/Boise",
  open_days: "Monday,Tuesday,Wednesday,Thursday,Friday",
  open_hour: "9", close_hour: "19",
  holiday_dates: "PASTE_GENERATED_HOLIDAY_DATES_OR_EMPTY",
  closure_windows: "PASTE_GENERATED_CLOSURE_WINDOWS_OR_EMPTY",
};
// Probe instants in the client LOCAL timezone, "YYYY-MM-DDTHH:MM"
const probes = ["2026-11-25T16:59","2026-11-25T17:00","2026-11-28T12:00","2026-11-30T07:59","2026-11-30T08:00","2026-12-01T12:00"];
const holidays = {};
for (const e of String(row.holiday_dates||"").split(",")) {
  const [d, ...n] = e.trim().split(":");
  if (/^\d{4}-\d{2}-\d{2}$/.test(d)) holidays[d] = n.join(":") || "closure";
}
const windows = [];
for (const e of String(row.closure_windows||"").split(",")) {
  const m = e.trim().match(/^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})\.\.(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})=(.+)$/);
  if (m && m[1] < m[2]) windows.push({start:m[1], end:m[2], name:m[3]});
}
for (const localNow of probes) {
  const dateKey = localNow.slice(0,10);
  const hour = Number(localNow.slice(11,13));
  const weekday = new Date(dateKey+"T12:00:00Z").toLocaleDateString("en-US",{weekday:"long",timeZone:"UTC"});
  const w = windows.find(w => localNow >= w.start && localNow < w.end);
  const holidayName = w ? w.name : (holidays[dateKey] ?? "");
  const openDays = row.open_days.split(",").map(s=>s.trim());
  const isOpen = openDays.includes(weekday) && hour >= +row.open_hour && hour < +row.close_hour && !holidayName;
  console.log(localNow, weekday.padEnd(9), isOpen ? "OPEN" : "CLOSED", holidayName);
}'
```

The probe list above matches the Thanksgiving worked example — adjust the
instants to bracket whatever closures you actually generated. Verified
output for the worked example (with open_hour 9): `Wed 16:59 OPEN`,
`Wed 17:00 CLOSED (window)`, `Sat 12:00 CLOSED (window)`,
`Mon 07:59 CLOSED (window)`, `Mon 08:00 CLOSED (normal hours — opens 9)`,
`Tue 12:00 OPEN`. That Monday 08:00 result is the windows-only-close rule
in action — show the requester this distinction whenever their stated
reopen time is earlier than the client's normal opening.

## Current seed row (Litster Frost, for reference)

- agent_id `agent_9601m01gh938ezhv3kkvwq2kv5at`, timezone `America/Boise`,
  open_days Mon–Fri, open_hour 9, close_hour 19.
- holiday_dates: the 27-date list through 2028 recorded in
  `clients/litster-frost/n8n-build-prompt.md` (note: the agent prompt says
  "25 dates" — count discrepancy flagged to Brett, unresolved).
