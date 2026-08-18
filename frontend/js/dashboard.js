/**
 * CLINIC OS — dashboard module.
 *
 * Lightweight KPI summary built from real data (patient count, doctor
 * count, medical act catalog size, appointments today) — no fake
 * numbers. The full KPI dashboard from spec section 9 (recettes,
 * dépenses, caisses, etc.) needs the billing/cash modules first and
 * lands with the complete sidebar shell in Phase 9; this is an honest
 * subset of what's actually implemented so far.
 */

import { apiRequest } from "./api.js";

function todayRange() {
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  const end = new Date();
  end.setHours(23, 59, 59, 999);
  return { date_from: start.toISOString(), date_to: end.toISOString() };
}

async function safeCount(path, params = {}) {
  try {
    const query = new URLSearchParams({ page: "1", page_size: "1", ...params });
    const body = await apiRequest(`${path}?${query.toString()}`);
    return body.data.total;
  } catch {
    return null; // missing permission or module not reachable — just hide it
  }
}

export async function renderDashboardSection(container, permissions) {
  container.innerHTML = `<section class="dashboard-section"><h2>Aperçu</h2><div id="kpi-grid" class="kpi-grid"></div></section>`;
  const grid = container.querySelector("#kpi-grid");

  const cards = [];

  if (permissions.includes("patients.read")) {
    cards.push({ label: "Patients", key: "patients", fetch: () => safeCount("/patients") });
  }
  if (permissions.includes("doctors.read")) {
    cards.push({ label: "Médecins", key: "doctors", fetch: () => safeCount("/doctors") });
  }
  if (permissions.includes("medical_acts.read")) {
    cards.push({ label: "Actes au catalogue", key: "acts", fetch: () => safeCount("/medical-acts") });
  }
  if (permissions.includes("appointments.read")) {
    const { date_from, date_to } = todayRange();
    cards.push({
      label: "Rendez-vous aujourd'hui",
      key: "appointments",
      fetch: () => safeCount("/appointments", { date_from, date_to }),
    });
  }
  if (permissions.includes("consultations.read")) {
    cards.push({ label: "Consultations", key: "consultations", fetch: () => safeCount("/consultations") });
  }
  if (permissions.includes("users.read")) {
    cards.push({ label: "Utilisateurs", key: "users", fetch: () => safeCount("/users") });
  }
  if (permissions.includes("billing.read")) {
    cards.push({ label: "Factures", key: "invoices", fetch: () => safeCount("/invoices") });
  }

  if (cards.length === 0) {
    grid.innerHTML = `<p class="kpi-empty">Aucune donnée disponible pour votre rôle.</p>`;
    return;
  }

  grid.innerHTML = cards
    .map(
      (c) => `
      <div class="kpi-card" data-key="${c.key}">
        <div class="kpi-value">…</div>
        <div class="kpi-label">${c.label}</div>
      </div>`
    )
    .join("");

  await Promise.all(
    cards.map(async (c) => {
      const total = await c.fetch();
      const valueEl = grid.querySelector(`[data-key="${c.key}"] .kpi-value`);
      valueEl.textContent = total === null ? "—" : total;
    })
  );
}
