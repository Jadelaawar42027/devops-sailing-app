// Planner page: pick a passage, show the GO/NO-GO timeline and current conditions.
import { api, el, formatTime, showMessage } from "./api.js";

const $ = (id) => document.getElementById(id);
const select = $("passage-select");
const message = $("message");
let passages = [];

const DAY_FMT = new Intl.DateTimeFormat("en-GB", {
  weekday: "short",
  day: "numeric",
  timeZone: "UTC",
});
const DIRS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
const compass = (deg) =>
  deg === null || deg === undefined ? "" : ` from ${DIRS[Math.round(deg / 45) % 8]}`;
const value = (v, unit, digits = 1) =>
  v === null || v === undefined ? "no data" : `${v.toFixed(digits)} ${unit}`;

async function init() {
  try {
    passages = await api.listPassages();
  } catch (error) {
    showMessage(message, error.message, "error");
    select.replaceChildren(el("option", { value: "" }, "Could not load passages"));
    return;
  }
  select.replaceChildren(
    el("option", { value: "" }, passages.length ? "Choose a passage" : "No passages yet"),
  );
  for (const p of passages) select.append(el("option", { value: p.id }, p.name));
  if (!passages.length) {
    showMessage(message, "Add a boat and a passage first, then come back here.", "info");
    return;
  }
  const wanted = new URLSearchParams(location.search).get("passage") || passages[0].id;
  select.value = String(wanted);
  if (!select.value) select.value = String(passages[0].id);
  load();
}

async function load() {
  const id = Number(select.value);
  const passage = passages.find((p) => p.id === id);
  if (!passage) return;
  history.replaceState(null, "", `?passage=${id}`);
  showMessage(message, "");
  $("summary").textContent = "Checking the forecast…";
  $("timeline").replaceChildren();
  $("legend").hidden = true;
  $("table-details").hidden = true;
  $("detail").replaceChildren(el("p", { class: "muted" }, "Select an hour on the timeline."));
  loadConditions(passage);
  try {
    renderWindows(await api.windows(id));
  } catch (error) {
    // 503 "degraded": the forecast service is down. Everything else keeps working.
    $("summary").textContent = "";
    showMessage(message, error.message, "error");
  }
}

function renderWindows(data) {
  const { summary, windows } = data;
  if (data.forecast.stale) {
    showMessage(
      message,
      "The forecast service could not refresh; showing the last saved forecast.",
      "info",
    );
  }
  $("summary").replaceChildren(
    el("strong", {}, `${summary.go} of ${summary.windows}`),
    ` departures are GO. ${data.distance_nm} nm at ${data.speed_kn} kn takes about ${data.duration_h} h. `,
    summary.first_go
      ? `First GO: ${formatTime(summary.first_go)}.`
      : (summary.note ?? "No GO window in the forecast."),
  );
  if (!windows.length) return;

  // Group by UTC day; each day is a row of 24 cells, empty where there is no window.
  const days = new Map();
  for (const w of windows) {
    const d = new Date(w.departure);
    const key = d.toISOString().slice(0, 10);
    if (!days.has(key)) days.set(key, new Array(24).fill(null));
    days.get(key)[d.getUTCHours()] = w;
  }
  const timeline = $("timeline");
  timeline.append(
    el(
      "div",
      { class: "hour-scale", "aria-hidden": "true" },
      el("span"),
      el("div", {}, ...["00", "06", "12", "18", "23"].map((h) => el("span", {}, h))),
    ),
  );
  for (const [key, hours] of days) {
    const cells = hours.map((w, hour) => {
      if (!w) return el("span", { class: "hour" });
      const label = `${formatTime(w.departure)}: ${w.go ? "GO" : "NO-GO"}`;
      return el("button", {
        type: "button",
        class: `hour ${w.go ? "go" : "nogo"}`,
        "aria-label": label,
        "aria-pressed": "false",
        title: label,
        "data-hour": hour,
        onclick: (event) => select_(event.currentTarget, w),
      });
    });
    const label = DAY_FMT.format(new Date(`${key}T00:00:00Z`));
    timeline.append(
      el(
        "div",
        { class: "day" },
        el("span", { class: "day-label" }, label),
        el("div", { class: "hours" }, cells),
      ),
    );
  }
  $("legend").hidden = false;

  $("windows-table").replaceChildren(
    ...windows.map((w) =>
      el(
        "tr",
        {},
        el("td", {}, formatTime(w.departure)),
        el("td", {}, formatTime(w.arrival)),
        el(
          "td",
          {},
          el("span", { class: `verdict ${w.go ? "go" : "nogo"}` }, w.go ? "GO" : "NO-GO"),
        ),
        el("td", {}, w.reason),
      ),
    ),
  );
  $("table-details").hidden = false;

  const first = timeline.querySelector("button.hour.go") || timeline.querySelector("button.hour");
  if (first) first.click();
}

function select_(button, w) {
  for (const b of document.querySelectorAll(".hour[aria-pressed='true']"))
    b.setAttribute("aria-pressed", "false");
  button.setAttribute("aria-pressed", "true");
  $("detail").replaceChildren(
    el("span", { class: `verdict ${w.go ? "go" : "nogo"}` }, w.go ? "GO" : "NO-GO"),
    w.failures.length
      ? el("ul", { class: "failures" }, ...w.failures.map((f) => el("li", {}, f.message)))
      : el("p", { class: "reason" }, w.reason),
    el(
      "dl",
      {},
      el("dt", {}, "Leave"),
      el("dd", {}, formatTime(w.departure)),
      el("dt", {}, "Arrive"),
      el("dd", {}, formatTime(w.arrival)),
      el("dt", {}, "Peak wind"),
      el("dd", {}, value(w.peak.wind_kn, "kn")),
      el("dt", {}, "Peak gusts"),
      el("dd", {}, value(w.peak.gust_kn, "kn")),
      el("dt", {}, "Peak waves"),
      el("dd", {}, value(w.peak.wave_m, "m", 2)),
    ),
  );
}

async function loadConditions(passage) {
  const box = $("conditions");
  box.replaceChildren(el("p", { class: "muted" }, "Loading…"));
  try {
    const data = await api.current(passage.start_lat, passage.start_lon);
    const c = data.current;
    box.replaceChildren(
      el("p", { class: "big-number" }, `${value(c.wind_kn, "kn")}${compass(c.wind_dir_deg)}`),
      el(
        "dl",
        {},
        el("dt", {}, "Gusts"),
        el("dd", {}, value(c.gust_kn, "kn")),
        el("dt", {}, "Waves"),
        el("dd", {}, `${value(c.wave_m, "m", 2)}${compass(c.wave_dir_deg)}`),
        el("dt", {}, "Wave period"),
        el("dd", {}, value(c.wave_period_s, "s")),
        el("dt", {}, "Observed"),
        el("dd", {}, formatTime(c.time)),
      ),
      el(
        "p",
        { class: "muted" },
        data.stale
          ? "Last saved values: the forecast source is not answering."
          : "Source: Open-Meteo.",
      ),
    );
  } catch (error) {
    box.replaceChildren(el("p", {}, `Current conditions unavailable. ${error.message}`));
  }
}

select.addEventListener("change", load);
$("refresh").addEventListener("click", load);
init();
