/**
 * CLINIC OS — suppliers module.
 *
 * List of suppliers with a quick-add form. Purchase order creation and
 * reception are managed via the API/docs for now (a full ordering UI
 * is a natural fit for the Phase 9 dashboard rebuild).
 */

import { apiRequest } from "./api.js";

export async function renderSuppliersSection(container) {
  container.innerHTML = `
    <section class="suppliers-section">
      <h2>Fournisseurs</h2>

      <div id="suppliers-list">Chargement...</div>

      <details class="add-supplier-details">
        <summary>+ Nouveau fournisseur</summary>
        <form id="add-supplier-form" class="inline-form-vertical">
          <label>Code <input name="code" required /></label>
          <label>Nom <input name="name" required /></label>
          <label>Contact <input name="contact_name" /></label>
          <label>Téléphone <input name="phone" /></label>
          <button type="submit">Créer le fournisseur</button>
          <p id="supplier-message" class="form-message" hidden></p>
        </form>
      </details>
    </section>
  `;

  await renderList(container.querySelector("#suppliers-list"));

  container.querySelector("#add-supplier-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    const msg = container.querySelector("#supplier-message");
    const formData = new FormData(form);
    try {
      const body = await apiRequest("/suppliers", {
        method: "POST",
        body: JSON.stringify({
          code: formData.get("code"),
          name: formData.get("name"),
          contact_name: formData.get("contact_name") || null,
          phone: formData.get("phone") || null,
        }),
      });
      msg.textContent = `Fournisseur ${body.data.name} créé.`;
      msg.className = "form-message form-message--ok";
      msg.hidden = false;
      form.reset();
      await renderList(container.querySelector("#suppliers-list"));
    } catch (err) {
      msg.textContent = err.message;
      msg.className = "form-message form-message--error";
      msg.hidden = false;
    }
  });
}

async function renderList(el) {
  try {
    const body = await apiRequest("/suppliers?page_size=50");
    if (body.data.items.length === 0) {
      el.innerHTML = "<p>Aucun fournisseur pour l'instant.</p>";
      return;
    }
    el.innerHTML = `
      <table class="patients-table">
        <thead><tr><th>Code</th><th>Nom</th><th>Contact</th><th>Téléphone</th></tr></thead>
        <tbody>
          ${body.data.items
            .map(
              (s) => `
            <tr>
              <td>${s.code}</td>
              <td>${s.name}</td>
              <td>${s.contact_name || "—"}</td>
              <td>${s.phone || "—"}</td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>
    `;
  } catch (err) {
    el.innerHTML = `<p class="status status--error">${err.message}</p>`;
  }
}
