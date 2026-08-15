/**
 * CLINIC OS — patients module.
 *
 * Minimal functional patient list + quick-add form, wired to the real
 * API (search, create, archive all work end-to-end). The full patients
 * screen (filters, pagination controls, detail view with contacts/
 * insurances/allergies/history, print/export) is refined visually once
 * the sidebar shell lands in Phase 9 — this proves the plumbing works.
 */

import { apiRequest } from "./api.js";

export async function renderPatientsSection(container) {
  container.innerHTML = `
    <section class="patients-section">
      <h2>Patients</h2>

      <form id="patient-search-form" class="inline-form">
        <input id="patient-search-input" type="text" placeholder="Rechercher (nom, numéro, téléphone)..." />
        <button type="submit">Rechercher</button>
      </form>

      <div id="patients-list" class="patients-list">Chargement...</div>

      <details class="add-patient-details">
        <summary>+ Nouveau patient</summary>
        <form id="add-patient-form" class="inline-form-vertical">
          <label>Prénom <input name="first_name" required /></label>
          <label>Nom <input name="last_name" required /></label>
          <label>Téléphone <input name="phone" /></label>
          <label>Email <input name="email" type="email" /></label>
          <button type="submit">Créer le patient</button>
          <p id="add-patient-message" class="form-message" hidden></p>
        </form>
      </details>
    </section>
  `;

  const listEl = container.querySelector("#patients-list");
  const searchForm = container.querySelector("#patient-search-form");
  const addForm = container.querySelector("#add-patient-form");
  const addMessage = container.querySelector("#add-patient-message");

  async function loadPatients(search = "") {
    listEl.textContent = "Chargement...";
    try {
      const params = new URLSearchParams({ page: "1", page_size: "20" });
      if (search) params.set("search", search);
      const body = await apiRequest(`/patients?${params.toString()}`);
      renderList(body.data.items, body.data.total);
    } catch (err) {
      listEl.innerHTML = `<p class="status status--error">${err.message}</p>`;
    }
  }

  function renderList(items, total) {
    if (items.length === 0) {
      listEl.innerHTML = `<p>Aucun patient trouvé (${total} au total).</p>`;
      return;
    }
    listEl.innerHTML = `
      <p class="patients-count">${total} patient(s)</p>
      <table class="patients-table">
        <thead><tr><th>N°</th><th>Nom</th><th>Téléphone</th><th>Email</th><th></th></tr></thead>
        <tbody>
          ${items
            .map(
              (p) => `
            <tr data-id="${p.id}">
              <td>${p.patient_number}</td>
              <td>${p.first_name} ${p.last_name}</td>
              <td>${p.phone || "—"}</td>
              <td>${p.email || "—"}</td>
              <td><button class="archive-button" data-id="${p.id}">Archiver</button></td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>
    `;

    listEl.querySelectorAll(".archive-button").forEach((btn) => {
      btn.addEventListener("click", async () => {
        btn.disabled = true;
        try {
          await apiRequest(`/patients/${btn.dataset.id}/archive`, { method: "POST" });
          await loadPatients(searchForm.querySelector("#patient-search-input").value.trim());
        } catch (err) {
          alert(err.message);
          btn.disabled = false;
        }
      });
    });
  }

  searchForm.addEventListener("submit", (event) => {
    event.preventDefault();
    loadPatients(searchForm.querySelector("#patient-search-input").value.trim());
  });

  addForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    addMessage.hidden = true;
    const submitButton = addForm.querySelector("button[type=submit]");
    submitButton.disabled = true;

    const formData = new FormData(addForm);
    const payload = Object.fromEntries(formData.entries());
    Object.keys(payload).forEach((key) => {
      if (payload[key] === "") delete payload[key];
    });

    try {
      const body = await apiRequest("/patients", { method: "POST", body: JSON.stringify(payload) });
      addMessage.className = "form-message form-message--ok";
      addMessage.textContent = `Patient ${body.data.patient_number} créé.`;
      addMessage.hidden = false;
      addForm.reset();
      await loadPatients();
    } catch (err) {
      addMessage.className = "form-message form-message--error";
      addMessage.textContent = err.message;
      addMessage.hidden = false;
    } finally {
      submitButton.disabled = false;
    }
  });

  await loadPatients();
}
