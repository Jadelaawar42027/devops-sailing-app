// Shared list + form behaviour for the boats and passages pages.
import { el, formFields, showMessage } from "./api.js";

export function setupCrud({ noun, load, create, update, remove, renderRow, beforeSubmit }) {
  const form = document.getElementById("form");
  const rows = document.getElementById("rows");
  const message = document.getElementById("message");
  const formMessage = document.getElementById("form-message");
  const submit = document.getElementById("submit");
  const cancel = document.getElementById("cancel");
  const formTitle = document.getElementById("form-title");
  const columns = rows.closest("table").querySelectorAll("thead th").length;

  function resetForm() {
    form.reset();
    form.elements.id.value = "";
    formTitle.textContent = `Add a ${noun}`;
    submit.textContent = `Save ${noun}`;
    cancel.hidden = true;
    showMessage(formMessage, "");
  }

  function edit(item) {
    for (const [key, value] of Object.entries(item)) {
      if (form.elements[key]) form.elements[key].value = value ?? "";
    }
    formTitle.textContent = `Edit ${item.name}`;
    submit.textContent = "Save changes";
    cancel.hidden = false;
    form.elements.name.focus();
  }

  async function refresh() {
    try {
      const items = await load();
      rows.replaceChildren();
      if (items.length === 0) {
        rows.append(
          el(
            "tr",
            {},
            el(
              "td",
              { colspan: columns, class: "empty-state" },
              `No ${noun}s yet. Add one with the form.`,
            ),
          ),
        );
      }
      for (const item of items) {
        const actions = el(
          "td",
          {},
          el(
            "div",
            { class: "row-actions" },
            el("button", { type: "button", class: "secondary", onclick: () => edit(item) }, "Edit"),
            el(
              "button",
              {
                type: "button",
                class: "danger",
                onclick: () => onDelete(item),
                "aria-label": `Delete ${item.name}`,
              },
              "Delete",
            ),
          ),
        );
        rows.append(el("tr", {}, ...renderRow(item), actions));
      }
    } catch (error) {
      showMessage(message, error.message, "error");
    }
  }

  async function onDelete(item) {
    if (!window.confirm(`Delete ${item.name}?`)) return;
    try {
      await remove(item.id);
      showMessage(message, `Deleted ${item.name}.`, "ok");
      if (form.elements.id.value === String(item.id)) resetForm();
      await refresh();
    } catch (error) {
      showMessage(message, error.message, "error");
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const { id, ...data } = formFields(form);
    if (beforeSubmit) beforeSubmit(data);
    showMessage(formMessage, "");
    submit.disabled = true;
    submit.textContent = "Saving…";
    try {
      const saved = id ? await update(id, data) : await create(data);
      showMessage(message, `Saved ${saved.name}.`, "ok");
      resetForm();
      await refresh();
    } catch (error) {
      // Next to the form, so it is visible on a phone where the banner is off-screen.
      showMessage(
        formMessage,
        `${error.message.replace(/\.?$/, ".")} Fix the form and save again.`,
        "error",
      );
      submit.textContent = form.elements.id.value ? "Save changes" : `Save ${noun}`;
    } finally {
      submit.disabled = false;
    }
  });
  cancel.addEventListener("click", resetForm);

  return { refresh };
}
