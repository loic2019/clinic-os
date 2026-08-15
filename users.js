/**
 * CLINIC OS — user management module.
 *
 * Lets an admin create staff accounts (cashiers, receptionists,
 * nurses, doctors, etc.) directly from the browser instead of via
 * /docs. Fully wired to the real /api/users endpoints (create, list,
 * deactivate) — spec section 28's RBAC still applies: the backend
 * rejects this for anyone without the `users.create` / `users.read`
 * permission, this UI is just a convenience layer on top.
 */

import { apiRequest } from "./api.js";

const ROLE_OPTIONS = [
  "CASHIER",
  "RECEPTIONIST",
  "NURSE",
  "DOCTOR",
  "LAB_TECHNICIAN",
  "PHARMACIST",
  "ACCOUNTANT",
  "HR_MANAGER",
  "DIRECTOR",
  "ADMIN",
  "SUPER_ADMIN",
];

export async function renderUsersSection(container) {
  container.innerHTML = `
    <section class="users-section">
      <h2>Utilisateurs</h2>

      <div id="users-list" class="users-list">Chargement...</div>

      <details class="add-user-details">
        <summary>+ Nouvel utilisateur</summary>
        <form id="add-user-form" class="inline-form-vertical">
          <label>Nom d'utilisateur <input name="username" required minlength="3" /></label>
          <label>Nom complet <input name="full_name" required /></label>
          <label>Email <input name="email" type="email" required /></label>
          <label>Mot de passe <input name="password" type="password" required minlength="8" /></label>
          <label>Rôle
            <select name="role">
              ${ROLE_OPTIONS.map((r) => `<option value="${r}">${r}</option>`).join("")}
            </select>
          </label>
          <button type="submit">Créer l'utilisateur</button>
          <p id="add-user-message" class="form-message" hidden></p>
        </form>
      </details>
    </section>
  `;

  const listEl = container.querySelector("#users-list");
  const addForm = container.querySelector("#add-user-form");
  const addMessage = container.querySelector("#add-user-message");

  async function loadUsers() {
    listEl.textContent = "Chargement...";
    try {
      const body = await apiRequest("/users?page=1&page_size=50");
      renderList(body.data.items);
    } catch (err) {
      listEl.innerHTML = `<p class="status status--error">${err.message}</p>`;
    }
  }

  function renderList(items) {
    if (items.length === 0) {
      listEl.innerHTML = `<p>Aucun utilisateur.</p>`;
      return;
    }
    listEl.innerHTML = `
      <table class="patients-table">
        <thead><tr><th>Utilisateur</th><th>Nom</th><th>Rôles</th><th>Statut</th><th></th></tr></thead>
        <tbody>
          ${items
            .map(
              (u) => `
            <tr data-id="${u.id}">
              <td>${u.username}</td>
              <td>${u.full_name}</td>
              <td>${u.roles.join(", ")}</td>
              <td>${u.is_active ? "Actif" : "Désactivé"}</td>
              <td>${
                u.is_active
                  ? `<button class="deactivate-button" data-id="${u.id}">Désactiver</button>`
                  : ""
              }</td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>
    `;

    listEl.querySelectorAll(".deactivate-button").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm("Désactiver cet utilisateur ?")) return;
        btn.disabled = true;
        try {
          await apiRequest(`/users/${btn.dataset.id}`, { method: "DELETE" });
          await loadUsers();
        } catch (err) {
          alert(err.message);
          btn.disabled = false;
        }
      });
    });
  }

  addForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    addMessage.hidden = true;
    const submitButton = addForm.querySelector("button[type=submit]");
    submitButton.disabled = true;

    const formData = new FormData(addForm);
    const payload = {
      username: formData.get("username"),
      full_name: formData.get("full_name"),
      email: formData.get("email"),
      password: formData.get("password"),
      role_names: [formData.get("role")],
    };

    try {
      const body = await apiRequest("/users", { method: "POST", body: JSON.stringify(payload) });
      addMessage.className = "form-message form-message--ok";
      addMessage.textContent = `Utilisateur ${body.data.username} créé avec le rôle ${body.data.roles.join(", ")}.`;
      addMessage.hidden = false;
      addForm.reset();
      await loadUsers();
    } catch (err) {
      addMessage.className = "form-message form-message--error";
      addMessage.textContent = err.message;
      addMessage.hidden = false;
    } finally {
      submitButton.disabled = false;
    }
  });

  await loadUsers();
}
