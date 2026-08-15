/**
 * CLINIC OS — Application bootstrap.
 *
 * Phase 1: apply saved theme, check /api/health.
 * Phase 2: route between the login form and a minimal authenticated
 * shell, proving the JWT + RBAC flow works end-to-end from the browser.
 * The real sidebar/dashboard shell (spec sections 8-9) arrives Phase 9+.
 */

import { checkHealth } from "./api.js";
import { isLoggedIn, renderLoginForm, renderAuthenticatedShell } from "./auth.js";

function applySavedTheme() {
  const saved = localStorage.getItem("clinic_os_theme") || "system";
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const effective = saved === "system" ? (prefersDark ? "dark" : "light") : saved;
  document.documentElement.setAttribute("data-theme", effective);
}

async function renderApp() {
  const app = document.getElementById("app");

  if (await isLoggedIn()) {
    await renderAuthenticatedShell(app);
  } else {
    renderLoginForm(app, renderApp);
  }
}

async function bootstrap() {
  applySavedTheme();

  try {
    await checkHealth();
  } catch {
    document.getElementById("app").innerHTML =
      '<div class="boot-screen"><div class="boot-card"><h1>CLINIC OS</h1>' +
      '<p class="status status--error">Impossible de contacter l\'API. Vérifiez que le backend est démarré.</p></div></div>';
    return;
  }

  await renderApp();
}

document.addEventListener("DOMContentLoaded", bootstrap);

