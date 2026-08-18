/**
 * CLINIC OS — accounting module.
 *
 * A revenue/expense summary (real numbers from the automatic
 * double-entry ledger — see accounting_service.py) plus a form to log
 * expenses, which themselves generate their own balanced entry.
 */

import { apiRequest } from "./api.js";

function fmt(amount) {
  return new Intl.NumberFormat("fr-FR").format(amount) + " FCFA";
}

export async function renderAccountingSection(container) {
  container.innerHTML = `
    <section class="accounting-section">
      <h2>Comptabilité</h2>

      <div id="accounting-summary" class="kpi-grid">Chargement...</div>

      <details class="add-expense-details">
        <summary>+ Nouvelle dépense</summary>
        <form id="expense-form" class="inline-form-vertical">
          <label>Catégorie <input name="category" placeholder="Ex: Loyer, Fournitures" required /></label>
          <label>Description <input name="description" required /></label>
          <label>Montant <input name="amount" type="number" min="0" required /></label>
          <button type="submit">Enregistrer la dépense</button>
          <p id="expense-message" class="form-message" hidden></p>
        </form>
      </details>

      <h3>Écritures récentes</h3>
      <div id="recent-entries">Chargement...</div>
    </section>
  `;

  await renderSummary(container.querySelector("#accounting-summary"));
  await renderRecentEntries(container.querySelector("#recent-entries"));

  container.querySelector("#expense-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    const msg = container.querySelector("#expense-message");
    const submitBtn = form.querySelector("button[type=submit]");
    submitBtn.disabled = true;

    const formData = new FormData(form);
    try {
      const body = await apiRequest("/accounting/expenses", {
        method: "POST",
        body: JSON.stringify({
          category: formData.get("category"),
          description: formData.get("description"),
          amount: Number(formData.get("amount")),
        }),
      });
      msg.textContent = `Dépense ${body.data.expense_number} enregistrée.`;
      msg.className = "form-message form-message--ok";
      msg.hidden = false;
      form.reset();
      await renderSummary(container.querySelector("#accounting-summary"));
      await renderRecentEntries(container.querySelector("#recent-entries"));
    } catch (err) {
      msg.textContent = err.message;
      msg.className = "form-message form-message--error";
      msg.hidden = false;
    } finally {
      submitBtn.disabled = false;
    }
  });
}

async function renderSummary(el) {
  try {
    const body = await apiRequest("/accounting/summary");
    const s = body.data;
    el.innerHTML = `
      <div class="kpi-card"><div class="kpi-value">${fmt(s.total_revenue)}</div><div class="kpi-label">Recettes (30j)</div></div>
      <div class="kpi-card"><div class="kpi-value">${fmt(s.total_expense)}</div><div class="kpi-label">Dépenses (30j)</div></div>
      <div class="kpi-card"><div class="kpi-value">${fmt(s.net_result)}</div><div class="kpi-label">Résultat net</div></div>
      <div class="kpi-card"><div class="kpi-value">${fmt(s.cash_balance)}</div><div class="kpi-label">Solde caisse (30j)</div></div>
    `;
  } catch (err) {
    el.innerHTML = `<p class="status status--error">${err.message}</p>`;
  }
}

async function renderRecentEntries(el) {
  try {
    const body = await apiRequest("/accounting/entries?page_size=10");
    if (body.data.items.length === 0) {
      el.innerHTML = "<p>Aucune écriture pour l'instant.</p>";
      return;
    }
    el.innerHTML = `
      <table class="patients-table">
        <thead><tr><th>N°</th><th>Date</th><th>Description</th><th>Débit</th><th>Crédit</th></tr></thead>
        <tbody>
          ${body.data.items
            .map(
              (e) => `
            <tr>
              <td>${e.entry_number}</td>
              <td>${e.entry_date}</td>
              <td>${e.description}</td>
              <td>${fmt(e.total_debit)}</td>
              <td>${fmt(e.total_credit)}</td>
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
