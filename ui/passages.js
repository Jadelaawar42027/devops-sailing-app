import { api, el, showMessage } from "./api.js";
import { setupCrud } from "./crud.js";

const boatSelect = document.getElementById("boat_id");
const boatNames = new Map();
const coord = (lat, lon) => `${lat.toFixed(2)}, ${lon.toFixed(2)}`;

async function loadBoats() {
  const boats = await api.listBoats();
  boatSelect.replaceChildren();
  boatNames.clear();
  if (boats.length === 0) {
    boatSelect.append(el("option", { value: "" }, "Add a boat first"));
    showMessage(
      document.getElementById("message"),
      "You need a boat before you can add a passage.",
      "info",
    );
  }
  for (const boat of boats) {
    boatNames.set(boat.id, boat.name);
    boatSelect.append(el("option", { value: boat.id }, boat.name));
  }
}

const page = setupCrud({
  noun: "passage",
  load: api.listPassages,
  create: api.createPassage,
  update: api.updatePassage,
  remove: api.deletePassage,
  renderRow: (p) => [
    el("td", {}, el("a", { href: `index.html?passage=${p.id}` }, p.name)),
    el("td", {}, boatNames.get(p.boat_id) ?? `#${p.boat_id}`),
    el("td", {}, `${coord(p.start_lat, p.start_lon)} → ${coord(p.end_lat, p.end_lon)}`),
    el("td", { class: "num" }, `${p.speed_kn} kn`),
  ],
});

loadBoats()
  .catch((error) => showMessage(document.getElementById("message"), error.message, "error"))
  .finally(page.refresh);
