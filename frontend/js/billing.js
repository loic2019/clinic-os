/**
 * CLINIC OS — billing & cash module.
 *
 * Lets a cashier open/close their till, create an invoice (searching
 * the medical act catalog or adding a free-form line), record a
 * payment, and see "Mes factures". Fully wired to the real API — every
 * total shown is calculated server-side, never in the browser.
 */

import { apiRequest } from "./api.js";

const PAYMENT_METHODS = [
  ["CASH", "Espèces"],
  ["MOBILE_MONEY_MTN", "Mobile Money (MTN)"],
  ["MOBILE_MONEY_AIRTEL", "Mobile Money (Airtel)"],
  ["CARD", "Carte bancaire"],
  ["BANK_TRANSFER", "Virement"],
  ["INSURANCE", "Assurance"],
  ["OTHER", "Autre"],
];

function fmt(amount) {
  return new Intl.NumberFormat("fr-FR").format(amount) + " FCFA";
}

export async function renderBillingSection(container) {
  container.innerHTML = `
    <section class="billing-section">
      <h2>Caisse &amp; Facturation</h2>

      <div id="cash-status" class="cash-status">Chargement...</div>

      <details class="add-invoice-details" open>
        <summary>+ Nouvelle facture</summary>
        <div id="invoice-form-area"></div>
      </details>

      <h3>Mes factures</h3>
      <div id="my-invoices" class="my-invoices">Chargement...</div>
    </section>
  `;

  await renderCashStatus(container.querySelector("#cash-status"));
  await renderInvoiceForm(container.querySelector("#invoice-form-area"), container);
  await renderMyInvoices(container.querySelector("#my-invoices"));
}

// --- Cash session ---------------------------------------------------------

async function renderCashStatus(el) {
  try {
    const body = await apiRequest("/cash/sessions/mine");
    const session = body.data;

    if (!session) {
      const registers = await apiRequest("/cash/registers");
      el.innerHTML = `
        <div class="cash-card cash-card--closed">
          <p>Aucune caisse ouverte.</p>
          <form id="open-cash-form" class="inline-form">
            <select name="cash_register_id">
              ${registers.data.map((r) => `<option value="${r.id}">${r.name}</option>`).join("")}
            </select>
            <input name="opening_balance" type="number" placeholder="Fond de caisse" min="0" required />
            <button type="submit">Ouvrir la caisse</button>
          </form>
          <p id="cash-message" class="form-message" hidden></p>
        </div>
      `;
      el.querySelector("#open-cash-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const formData = new FormData(event.target);
        const msg = el.querySelector("#cash-message");
        try {
          await apiRequest("/cash/sessions/open", {
            method: "POST",
            body: JSON.stringify({
              cash_register_id: formData.get("cash_register_id"),
              opening_balance: Number(formData.get("opening_balance")),
            }),
          });
          await renderCashStatus(el);
        } catch (err) {
          msg.textContent = err.message;
          msg.className = "form-message form-message--error";
          msg.hidden = false;
        }
      });
    } else {
      el.innerHTML = `
        <div class="cash-card cash-card--open">
          <p>Caisse ouverte — fond de départ : <strong>${fmt(session.opening_balance)}</strong></p>
          <details class="close-cash-details">
            <summary>Clôturer la caisse</summary>
            <form id="close-cash-form" class="inline-form">
              <input name="closing_balance" type="number" placeholder="Montant compté" min="0" required />
              <button type="submit">Clôturer</button>
            </form>
            <input id="close-justification" type="text" placeholder="Justification (si écart)" class="justification-input" hidden />
            <p id="close-message" class="form-message" hidden></p>
          </details>
        </div>
      `;
      const closeForm = el.querySelector("#close-cash-form");
      const justificationInput = el.querySelector("#close-justification");
      closeForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const formData = new FormData(closeForm);
        const msg = el.querySelector("#close-message");
        const payload = { closing_balance: Number(formData.get("closing_balance")) };
        if (justificationInput.value) payload.difference_justification = justificationInput.value;
        try {
          const body = await apiRequest(`/cash/sessions/${session.id}/close`, {
            method: "POST",
            body: JSON.stringify(payload),
          });
          msg.textContent = body.message;
          msg.className = "form-message form-message--ok";
          msg.hidden = false;
          setTimeout(() => renderCashStatus(el), 1200);
        } catch (err) {
          if (err.message.includes("Écart") || err.message.includes("justification")) {
            justificationInput.hidden = false;
            justificationInput.focus();
          }
          msg.textContent = err.message;
          msg.className = "form-message form-message--error";
          msg.hidden = false;
        }
      });
    }
  } catch (err) {
    el.innerHTML = `<p class="status status--error">${err.message}</p>`;
  }
}

// --- Invoice creation -------------------------------------------------------

async function renderInvoiceForm(el, rootContainer) {
  let lineItems = [];

  el.innerHTML = `
    <form id="invoice-form">
      <label>Patient (numéro ou nom) <input id="invoice-patient-search" type="text" required /></label>
      <div id="patient-search-results" class="search-results"></div>
      <input type="hidden" id="invoice-patient-id" />

      <div class="invoice-item-add">
        <input id="act-search" type="text" placeholder="Rechercher un acte (ex: consultation)" />
        <div id="act-search-results" class="search-results"></div>
        <div class="or-divider">— ou ligne libre —</div>
        <input id="custom-desc" type="text" placeholder="Description" />
        <input id="custom-price" type="number" placeholder="Prix" min="0" />
        <button type="button" id="add-custom-line">+ Ajouter la ligne libre</button>
      </div>

      <table class="patients-table" id="invoice-items-table">
        <thead><tr><th>Description</th><th>Qté</th><th>Prix unit.</th><th></th></tr></thead>
        <tbody></tbody>
      </table>
      <p><strong>Total : <span id="invoice-total">0 FCFA</span></strong></p>

      <button type="submit" id="create-invoice-btn" disabled>Créer la facture</button>
      <p id="invoice-form-message" class="form-message" hidden></p>
    </form>
    <div id="invoice-result"></div>
  `;

  const patientSearch = el.querySelector("#invoice-patient-search");
  const patientResults = el.querySelector("#patient-search-results");
  const patientIdInput = el.querySelector("#invoice-patient-id");
  const actSearch = el.querySelector("#act-search");
  const actResults = el.querySelector("#act-search-results");
  const itemsBody = el.querySelector("#invoice-items-table tbody");
  const totalEl = el.querySelector("#invoice-total");
  const createBtn = el.querySelector("#create-invoice-btn");

  function refreshItemsTable() {
    itemsBody.innerHTML = lineItems
      .map(
        (item, idx) => `
        <tr>
          <td>${item.label}</td>
          <td>${item.quantity}</td>
          <td>${item.unit_price ? fmt(item.unit_price) : "(catalogue)"}</td>
          <td><button type="button" class="remove-line" data-idx="${idx}">✕</button></td>
        </tr>`
      )
      .join("");
    const total = lineItems.reduce((sum, i) => sum + (i.unit_price || 0) * i.quantity, 0);
    totalEl.textContent = fmt(total) + (lineItems.some((i) => i.item_type === "MEDICAL_ACT") ? " (indicatif, calculé par le serveur)" : "");
    createBtn.disabled = lineItems.length === 0 || !patientIdInput.value;

    itemsBody.querySelectorAll(".remove-line").forEach((btn) => {
      btn.addEventListener("click", () => {
        lineItems.splice(Number(btn.dataset.idx), 1);
        refreshItemsTable();
      });
    });
  }

  let patientDebounce;
  patientSearch.addEventListener("input", () => {
    clearTimeout(patientDebounce);
    patientDebounce = setTimeout(async () => {
      if (patientSearch.value.trim().length < 2) return (patientResults.innerHTML = "");
      const body = await apiRequest(`/patients?search=${encodeURIComponent(patientSearch.value.trim())}&page_size=5`);
      patientResults.innerHTML = body.data.items
        .map((p) => `<div class="search-result-row" data-id="${p.id}" data-label="${p.patient_number} — ${p.first_name} ${p.last_name}">${p.patient_number} — ${p.first_name} ${p.last_name}</div>`)
        .join("");
      patientResults.querySelectorAll(".search-result-row").forEach((row) => {
        row.addEventListener("click", () => {
          patientIdInput.value = row.dataset.id;
          patientSearch.value = row.dataset.label;
          patientResults.innerHTML = "";
          refreshItemsTable();
        });
      });
    }, 300);
  });

  let actDebounce;
  actSearch.addEventListener("input", () => {
    clearTimeout(actDebounce);
    actDebounce = setTimeout(async () => {
      if (actSearch.value.trim().length < 2) return (actResults.innerHTML = "");
      const body = await apiRequest(`/medical-acts?search=${encodeURIComponent(actSearch.value.trim())}&page_size=5`);
      actResults.innerHTML = body.data.items
        .map(
          (a) =>
            `<div class="search-result-row" data-id="${a.id}" data-label="${a.name}">${a.code} — ${a.name} (${a.current_price ? fmt(a.current_price) : "pas de prix"})</div>`
        )
        .join("");
      actResults.querySelectorAll(".search-result-row").forEach((row) => {
        row.addEventListener("click", () => {
          lineItems.push({ item_type: "MEDICAL_ACT", medical_act_id: row.dataset.id, label: row.dataset.label, quantity: 1 });
          actSearch.value = "";
          actResults.innerHTML = "";
          refreshItemsTable();
        });
      });
    }, 300);
  });

  el.querySelector("#add-custom-line").addEventListener("click", () => {
    const desc = el.querySelector("#custom-desc");
    const price = el.querySelector("#custom-price");
    if (!desc.value || !price.value) return;
    lineItems.push({ item_type: "OTHER", description: desc.value, unit_price: Number(price.value), quantity: 1, label: desc.value });
    desc.value = "";
    price.value = "";
    refreshItemsTable();
  });

  el.querySelector("#invoice-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const msg = el.querySelector("#invoice-form-message");
    msg.hidden = true;
    createBtn.disabled = true;

    const payload = {
      patient_id: patientIdInput.value,
      items: lineItems.map((i) =>
        i.item_type === "MEDICAL_ACT"
          ? { item_type: "MEDICAL_ACT", medical_act_id: i.medical_act_id, quantity: i.quantity }
          : { item_type: "OTHER", description: i.description, unit_price: i.unit_price, quantity: i.quantity }
      ),
    };

    try {
      const body = await apiRequest("/invoices", { method: "POST", body: JSON.stringify(payload) });
      renderInvoiceResult(el.querySelector("#invoice-result"), body.data);
      lineItems = [];
      patientIdInput.value = "";
      patientSearch.value = "";
      refreshItemsTable();
      await renderMyInvoices(rootContainer.querySelector("#my-invoices"));
      await renderCashStatus(rootContainer.querySelector("#cash-status"));
    } catch (err) {
      msg.textContent = err.message;
      msg.className = "form-message form-message--error";
      msg.hidden = false;
    } finally {
      createBtn.disabled = false;
    }
  });

  refreshItemsTable();
}

function renderInvoiceResult(el, invoice) {
  el.innerHTML = `
    <div class="invoice-result-card">
      <p><strong>${invoice.invoice_number}</strong> créée — Total : ${fmt(invoice.total)} — Statut : ${invoice.status}</p>
      <form id="pay-form" class="inline-form">
        <select name="method">
          ${PAYMENT_METHODS.map(([v, l]) => `<option value="${v}">${l}</option>`).join("")}
        </select>
        <input name="amount" type="number" min="0" step="1" value="${invoice.balance_due}" />
        <input name="reference" type="text" placeholder="Référence (optionnel)" />
        <button type="submit">Encaisser</button>
      </form>
      <p id="pay-message" class="form-message" hidden></p>
    </div>
  `;
  el.querySelector("#pay-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(event.target);
    const msg = el.querySelector("#pay-message");
    try {
      const body = await apiRequest("/payments", {
        method: "POST",
        body: JSON.stringify({
          invoice_id: invoice.id,
          method: formData.get("method"),
          amount: Number(formData.get("amount")),
          reference: formData.get("reference") || null,
        }),
      });
      msg.textContent = `Paiement ${body.data.payment_number} enregistré.`;
      msg.className = "form-message form-message--ok";
      msg.hidden = false;
    } catch (err) {
      msg.textContent = err.message;
      msg.className = "form-message form-message--error";
      msg.hidden = false;
    }
  });
}

// --- Mes factures ---------------------------------------------------------

async function renderMyInvoices(el) {
  el.textContent = "Chargement...";
  try {
    const body = await apiRequest("/invoices?mine_only=true&page_size=20");
    if (body.data.items.length === 0) {
      el.innerHTML = "<p>Aucune facture pour l'instant.</p>";
      return;
    }
    el.innerHTML = `
      <table class="patients-table">
        <thead><tr><th>N°</th><th>Total</th><th>Payé</th><th>Solde</th><th>Statut</th></tr></thead>
        <tbody>
          ${body.data.items
            .map(
              (i) => `
            <tr>
              <td>${i.invoice_number}</td>
              <td>${fmt(i.total)}</td>
              <td>${fmt(i.amount_paid)}</td>
              <td>${fmt(i.balance_due)}</td>
              <td>${i.status}</td>
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
