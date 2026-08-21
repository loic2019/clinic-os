/**
 * CLINIC OS — auth module.
 *
 * Renders the login form and handles the login/logout flow. The
 * sidebar + dashboard shell (spec sections 8-9) is built starting
 * Phase 9; for now, a successful login just shows the connected user
 * and their roles/permissions so RBAC is visibly working end-to-end.
 */

import { login, logout, getCurrentUser, getAccessToken } from "./api.js";
import { renderPatientsSection } from "./patients.js";
import { renderDashboardSection } from "./dashboard.js";
import { renderUsersSection } from "./users.js";
import { renderBillingSection } from "./billing.js";
import { renderAccountingSection } from "./accounting.js";
import { renderInventorySection } from "./inventory.js";
import { renderSuppliersSection } from "./suppliers.js";

export async function isLoggedIn() {
  if (!getAccessToken()) return false;
  try {
    await getCurrentUser();
    return true;
  } catch {
    return false;
  }
}

export function renderLoginForm(container, onSuccess) {
  container.innerHTML = `
    <form id="login-form" class="login-form">
      <h1>CLINIC OS</h1>
      <p class="login-subtitle">Connexion</p>

      <label for="username">Nom d'utilisateur</label>
      <input id="username" name="username" type="text" autocomplete="username" required />

      <label for="password">Mot de passe</label>
      <input id="password" name="password" type="password" autocomplete="current-password" required />

      <button type="submit">Se connecter</button>
      <p id="login-error" class="login-error" hidden></p>
    </form>
  `;

  const form = container.querySelector("#login-form");
  const errorEl = container.querySelector("#login-error");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorEl.hidden = true;

    const username = form.username.value.trim();
    const password = form.password.value;
    const submitButton = form.querySelector("button[type=submit]");

    submitButton.disabled = true;
    submitButton.textContent = "Connexion...";

    try {
      await login(username, password);
      onSuccess();
    } catch (err) {
      errorEl.textContent = err.message || "Connexion impossible.";
      errorEl.hidden = false;
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = "Se connecter";
    }
  });
}

export async function renderAuthenticatedShell(container) {
  const user = await getCurrentUser();

  container.innerHTML = `
    <div class="authenticated-shell">
      <div class="shell-header">
        <h1>CLINIC OS</h1>
        <div class="shell-user">
          <span>${user.full_name} <span class="shell-role">${user.roles.join(", ") || "—"}</span></span>
          <button id="logout-button">Se déconnecter</button>
        </div>
      </div>

      <div id="dashboard-container"></div>
      <div id="billing-container"></div>
      <div id="accounting-container"></div>
      <div id="inventory-container"></div>
      <div id="suppliers-container"></div>
      <div id="patients-container"></div>
      <div id="users-container"></div>

      <p class="phase-note">
        Le tableau de bord complet (sidebar, KPIs financiers, tous les modules)
        arrive à partir de la Phase 9. Les sections ci-dessus sont déjà
        pleinement fonctionnelles : les chiffres viennent de PostgreSQL en
        temps réel, et la création d'utilisateur passe réellement par l'API.
      </p>
    </div>
  `;

  container.querySelector("#logout-button").addEventListener("click", async () => {
    await logout();
    window.location.reload();
  });

  await renderDashboardSection(container.querySelector("#dashboard-container"), user.permissions);

  if (user.permissions.includes("billing.create") && user.permissions.includes("cash.open")) {
    await renderBillingSection(container.querySelector("#billing-container"));
  }

  if (user.permissions.includes("accounting.read")) {
    await renderAccountingSection(container.querySelector("#accounting-container"));
  }

  if (user.permissions.includes("inventory.read")) {
    await renderInventorySection(container.querySelector("#inventory-container"));
  }

  if (user.permissions.includes("suppliers.read")) {
    await renderSuppliersSection(container.querySelector("#suppliers-container"));
  }

  if (user.permissions.includes("patients.read")) {
    await renderPatientsSection(container.querySelector("#patients-container"));
  }

  if (user.permissions.includes("users.read")) {
    await renderUsersSection(container.querySelector("#users-container"));
  }
}
