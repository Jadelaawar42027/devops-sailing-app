const config = window.APP_CONFIG;
const commitLabel = document.getElementById("commit-sha");

commitLabel.textContent = config.commitSha ?? "Local development";
const boatForm = document.getElementById("boat-form");
const formMessage = document.getElementById("boat-form-message");
const boats = [];
let nextBoatId = 1;
const passageBoat = document.getElementById("passage-boat");
let editingBoat = null;

const formTitle = document.getElementById("boat-form-title");
const submitButton = boatForm.querySelector('button[type="submit"]');
const cancelEdit = document.getElementById("cancel-edit");
const boatsBody = document.getElementById("boats-body");
const boatsStatus = document.getElementById("boats-status");

boatsStatus.textContent = "Practice mode: boats stay in this tab only and disappear on refresh.";

formMessage.textContent = "Enter details to add a practice boat.";
boatForm.querySelector("button").textContent = "Add practice boat";

const numericFields = ["length_ft", "max_wind_kn", "max_gust_kn", "max_wave_m"];

function validateBoatForm() {
  for (const input of boatForm.querySelectorAll("input")) {
    input.setCustomValidity("");
  }

  for (const field of ["name", "boat_type"]) {
    const input = boatForm.elements.namedItem(field);

    if (!input.value.trim()) {
      input.setCustomValidity("Enter a value, not just spaces.");
    }
  }

  for (const field of numericFields) {
    const input = boatForm.elements.namedItem(field);

    if (!Number.isFinite(input.valueAsNumber) || input.valueAsNumber <= 0) {
      input.setCustomValidity("Enter a number greater than zero.");
    }
  }

  const wind = boatForm.elements.namedItem("max_wind_kn");
  const gust = boatForm.elements.namedItem("max_gust_kn");

  if (gust.valueAsNumber < wind.valueAsNumber) {
    gust.setCustomValidity("Maximum gust must be at least maximum wind.");
  }

  return boatForm.reportValidity();
}
function readBoatForm() {
  return {
    name: boatForm.elements.namedItem("name").value.trim(),
    boat_type: boatForm.elements.namedItem("boat_type").value.trim(),
    length_ft: boatForm.elements.namedItem("length_ft").valueAsNumber,
    max_wind_kn: boatForm.elements.namedItem("max_wind_kn").valueAsNumber,
    max_gust_kn: boatForm.elements.namedItem("max_gust_kn").valueAsNumber,
    max_wave_m: boatForm.elements.namedItem("max_wave_m").valueAsNumber,
  };
}

function resetBoatForm() {
  editingBoat = null;
  boatForm.reset();

  for (const input of boatForm.querySelectorAll("input")) {
    input.setCustomValidity("");
  }

  formTitle.textContent = "Add a boat";
  submitButton.textContent = "Add practice boat";
  cancelEdit.hidden = true;
}

function editBoat(boat) {
  resetBoatForm();
  editingBoat = boat;

  for (const field of ["name", "boat_type", ...numericFields]) {
    boatForm.elements.namedItem(field).value = boat[field];
  }

  formTitle.textContent = "Edit practice boat";
  submitButton.textContent = "Save changes";
  cancelEdit.hidden = false;
  formMessage.textContent = "Changes remain temporary in practice mode.";
  boatForm.elements.namedItem("name").focus();
}
function renderPassageBoatOptions() {
  const selectedId = passageBoat.value;

  passageBoat.replaceChildren(
    new Option(boats.length ? "Choose a boat" : "Add a practice boat first", ""),
  );

  for (const boat of boats) {
    passageBoat.add(new Option(boat.name, String(boat.id)));
  }

  passageBoat.disabled = boats.length === 0;
  passageBoat.value = boats.some((boat) => String(boat.id) === selectedId) ? selectedId : "";
}

function renderBoats() {
  renderPassageBoatOptions();
  boatsBody.replaceChildren();

  if (boats.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");

    cell.colSpan = 7;
    cell.textContent = "No practice boats yet.";
    row.append(cell);
    boatsBody.append(row);
    return;
  }

  for (const boat of boats) {
    const row = document.createElement("tr");

    const values = [
      boat.name,
      boat.boat_type,
      boat.length_ft,
      boat.max_wind_kn,
      boat.max_gust_kn,
      boat.max_wave_m,
    ];

    for (const value of values) {
      const cell = document.createElement("td");
      cell.textContent = String(value);
      row.append(cell);
    }

    const actions = document.createElement("td");
    const editButton = document.createElement("button");

    editButton.type = "button";
    editButton.className = "button-secondary";
    editButton.textContent = "Edit";
    editButton.setAttribute("aria-label", `Edit practice boat ${boat.name}`);
    editButton.addEventListener("click", () => editBoat(boat));
    const deleteButton = document.createElement("button");

    deleteButton.type = "button";
    deleteButton.className = "button-secondary";
    deleteButton.textContent = "Delete";
    deleteButton.setAttribute("aria-label", `Delete practice boat ${boat.name}`);

    deleteButton.addEventListener("click", () => {
      if (!window.confirm(`Delete practice boat "${boat.name}"?`)) {
        return;
      }

      const index = boats.indexOf(boat);
      boats.splice(index, 1);

      if (editingBoat === boat) {
        resetBoatForm();
      }
      renderBoats();

      formMessage.textContent = `Deleted practice boat "${boat.name}".`;
    });

    actions.append(editButton, " ", deleteButton);
    row.append(actions);

    boatsBody.append(row);
  }
}

boatForm.addEventListener("input", () => {
  for (const input of boatForm.querySelectorAll("input")) {
    input.setCustomValidity("");
  }

  formMessage.textContent = "";
});

boatForm.addEventListener("submit", (event) => {
  event.preventDefault();

  if (!validateBoatForm()) {
    formMessage.textContent = "Check the highlighted field.";
    return;
  }

  const boat = readBoatForm();
  const wasEditing = editingBoat !== null;

  if (wasEditing) {
    Object.assign(editingBoat, boat);
  } else {
    boats.push({ ...boat, id: nextBoatId });
    nextBoatId += 1;
  }

  renderBoats();
  resetBoatForm();

  formMessage.textContent = `${wasEditing ? "Updated" : "Added"} "${boat.name}" in practice mode.`;
});

cancelEdit.addEventListener("click", () => {
  resetBoatForm();
  formMessage.textContent = "Edit cancelled. The stored boat was not changed.";
});

renderPassageBoatOptions();

const departureResult = document.getElementById("departure-result");

function readDeparture(side) {
  const date = document.getElementById(`departure-${side}-date`);
  const time = document.getElementById(`departure-${side}-time`);

  if (!date.reportValidity() || !time.reportValidity()) {
    return null;
  }

  return new Date(`${date.value}T${time.value.padStart(5, "0")}`);
}

document.getElementById("check-departure").addEventListener("click", () => {
  departureResult.textContent = "";

  const start = readDeparture("start");
  if (start === null) return;

  const end = readDeparture("end");
  if (end === null) return;

  if (end <= start) {
    departureResult.textContent = "Latest departure must be after earliest departure.";
    return;
  }

  departureResult.textContent = `Valid window in UTC: ${start.toISOString()} to ${end.toISOString()}`;
});
