/**
 * CLINIC OS — inventory module.
 *
 * Shows stock alerts (low stock / expiring soon / expired) and the
 * item catalog with quantities, fully wired to the real API.
 */

import { apiRequest } from "./api.js";

export async function renderInventorySection(container) {
  container.innerHTML = `
    <section class="inventory-section">
      <h2>Stocks</h2>

      <div id="inventory-alerts" class="inventory-alerts">Chargement...</div>

      <details class="add-item-details">
        <summary>+ Nouvel article</summary>
        <form id="add-item-form" class="inline-form-vertical">
          <label>Code <input name="code" required /></label>
          <label>Nom <input name="name" required /></label>
          <label>Catégorie
            <select name="category">
              <option value="MEDICATION">Médicament</option>
              <option value="CONSUMABLE">Consommable</option>
              <option value="LAB_SUPPLY">Fourniture labo</option>
              <option value="MEDICAL_EQUIPMENT">Matériel médical</option>
              <option value="OFFICE_SUPPLY">Fourniture bureau</option>
              <option value="CLEANING">Entretien</option>
            </select>
          </label>
          <label>Unité <input name="unit" placeholder="boîte, unité, flacon..." required /></label>
          <label>Seuil d'alerte <input name="reorder_threshold" type="number" min="0" value="10" /></label>
          <button type="submit">Créer l'article</button>
          <p id="item-message" class="form-message" hidden></p>
        </form>
      </details>

      <h3>Catalogue</h3>
      <div id="inventory-list">Chargement...</div>
    </section>
  `;

  await renderAlerts(container.querySelector("#inventory-alerts"));
  await renderList(container.querySelector("#inventory-list"));

  container.querySelector("#add-item-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    const msg = container.querySelector("#item-message");
    const formData = new FormData(form);
    try {
      const body = await apiRequest("/inventory/items", {
        method: "POST",
        body: JSON.stringify({
          code: formData.get("code"),
          name: formData.get("name"),
          category: formData.get("category"),
          unit: formData.get("unit"),
          reorder_threshold: Number(formData.get("reorder_threshold")),
        }),
      });
      msg.textContent = `Article ${body.data.code} créé.`;
      msg.className = "form-message form-message--ok";
      msg.hidden = false;
      form.reset();
      await renderList(container.querySelector("#inventory-list"));
    } catch (err) {
      msg.textContent = err.message;
      msg.className = "form-message form-message--error";
      msg.hidden = false;
    }
  });
}

async function renderAlerts(el) {
  try {
    const body = await apiRequest("/inventory/alerts");
    const { low_stock, expiring_soon, expired } = body.data;

    if (low_stock.length === 0 && expiring_soon.length === 0 && expired.length === 0) {
      el.innerHTML = `<p class="status status--ok">Aucune alerte — stocks au vert.</p>`;
      return;
    }

    el.innerHTML = `
      ${expired.length > 0 ? `<p class="alert-row alert-row--danger">🔴 ${expired.length} lot(s) expiré(s)</p>` : ""}
      ${expiring_soon.length > 0 ? `<p class="alert-row alert-row--warning">⚠ ${expiring_soon.length} lot(s) bientôt périmé(s)</p>` : ""}
      ${low_stock.length > 0 ? `<p class="alert-row alert-row--warning">⚠ ${low_stock.length} article(s) en stock faible : ${low_stock.map((a) => a.name).join(", ")}</p>` : ""}
    `;
  } catch (err) {
    el.innerHTML = `<p class="status status--error">${err.message}</p>`;
  }
}

async function renderList(el) {
  try {
    const body = await apiRequest("/inventory/items?page_size=50");
    if (body.data.items.length === 0) {
      el.innerHTML = "<p>Aucun article pour l'instant.</p>";
      return;
    }
    el.innerHTML = `
      <table class="patients-table">
        <thead><tr><th>Code</th><th>Nom</th><th>Catégorie</th><th>Stock</th><th>Seuil</th></tr></thead>
        <tbody>
          ${body.data.items
            .map(
              (i) => `
            <tr class="${i.is_low_stock ? "row-alert" : ""}">
              <td>${i.code}</td>
              <td>${i.name}</td>
              <td>${i.category}</td>
              <td>${i.quantity_on_hand} ${i.unit}</td>
              <td>${i.reorder_threshold}</td>
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
