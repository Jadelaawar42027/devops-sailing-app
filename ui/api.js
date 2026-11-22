// Small fetch wrapper shared by every page. Never builds HTML from server data (no innerHTML).
const CONFIG = window.APP_CONFIG || {};
const TIMEOUT_MS = 15000;

export class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

function messageFrom(body, status) {
  const detail = body && body.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{loc: [..., "field"], msg: "..."}]
    return detail
      .map((d) => {
        const field = d.loc[d.loc.length - 1];
        const msg = d.msg.replace(/^Value error, /, "");
        return field === "body" ? msg : `${field.replaceAll("_", " ")}: ${msg}`;
      })
      .join(". ");
  }
  return `The server answered with status ${status}.`;
}

async function request(base, path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(base + path, {
      ...options,
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
    });
    const body = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) throw new ApiError(messageFrom(body, response.status), response.status, body);
    return body;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error.name === "AbortError") {
      throw new ApiError("The server did not answer within 15 seconds. Try again.", 0);
    }
    throw new ApiError("Cannot reach the server. Check your connection and try again.", 0);
  } finally {
    clearTimeout(timer);
  }
}

const json = (method, data) => ({ method, body: JSON.stringify(data) });
const apiCall = (path, options) => request(CONFIG.apiUrl, path, options);

export const api = {
  listBoats: () => apiCall("/boats"),
  createBoat: (data) => apiCall("/boats", json("POST", data)),
  updateBoat: (id, data) => apiCall(`/boats/${id}`, json("PUT", data)),
  deleteBoat: (id) => apiCall(`/boats/${id}`, { method: "DELETE" }),
  listPassages: () => apiCall("/passages"),
  getPassage: (id) => apiCall(`/passages/${id}`),
  createPassage: (data) => apiCall("/passages", json("POST", data)),
  updatePassage: (id, data) => apiCall(`/passages/${id}`, json("PUT", data)),
  deletePassage: (id) => apiCall(`/passages/${id}`, { method: "DELETE" }),
  windows: (id) => apiCall(`/passages/${id}/windows`),
  current: (lat, lon) =>
    request(
      CONFIG.forecastUrl,
      `/current?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`,
    ),
};

// Create an element: el("td", { class: "num" }, "12.5")
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  node.append(...children.flat().filter((c) => c !== null && c !== undefined));
  return node;
}

// Show a message in a status box. kind: "info" | "error" | "ok"
export function showMessage(box, text, kind = "info") {
  box.textContent = text;
  box.dataset.kind = kind;
  box.hidden = !text;
}

// All times are shown in UTC, like the forecast. TODO(team): offer local time if users ask.
const DATE_FMT = new Intl.DateTimeFormat("en-GB", {
  weekday: "short",
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "UTC",
});
export const formatTime = (iso) => `${DATE_FMT.format(new Date(iso))} UTC`;

export function formFields(form) {
  const data = {};
  for (const input of form.querySelectorAll("input[name], select[name]")) {
    if (input.type === "number" || input.dataset.type === "number") {
      data[input.name] = input.value === "" ? null : Number(input.value);
    } else {
      data[input.name] = input.value;
    }
  }
  return data;
}
