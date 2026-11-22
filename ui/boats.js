import { api, el } from "./api.js";
import { setupCrud } from "./crud.js";

const fmt = (value, unit) => (value === null || value === undefined ? "—" : `${value} ${unit}`);

const page = setupCrud({
  noun: "boat",
  load: api.listBoats,
  create: api.createBoat,
  update: api.updateBoat,
  remove: api.deleteBoat,
  renderRow: (boat) => [
    el("td", {}, boat.name),
    el("td", { class: "num" }, fmt(boat.max_wind_kn, "kn")),
    el("td", { class: "num" }, fmt(boat.max_gust_kn, "kn")),
    el("td", { class: "num" }, fmt(boat.max_wave_m, "m")),
  ],
});
page.refresh();
