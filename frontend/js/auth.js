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
      <h1>CLINIC OS</h1>
      <p>Bienvenue, <strong>${user.full_name}</strong> (${user.username})</p>
      <p>Rôles : ${user.roles.join(", ") || "—"}</p>
      <details>
        <summary>Permissions (${user.permissions.length})</summary>
        <ul>${user.permissions.map((p) => `<li>${p}</li>`).join("")}</ul>
      </details>
      <button id="logout-button">Se déconnecter</button>
      <p class="phase-note">
        Le tableau de bord complet (sidebar, KPIs, tous les modules) arrive à partir
        de la Phase 9. Le module Patients ci-dessous est déjà pleinement fonctionnel :
        recherche, création, archivage passent réellement par l'API et PostgreSQL.
      </p>
      <div id="patients-container"></div>
    </div>
  `;

  container.querySelector("#logout-button").addEventListener("click", async () => {
    await logout();
    window.location.reload();
  });

  if (user.permissions.includes("patients.read")) {
    await renderPatientsSection(container.querySelector("#patients-container"));
  }
}
