/**
 * CLINIC OS — API client.
 *
 * Thin wrapper around fetch(). Every frontend module (patients.js,
 * billing.js, etc., added in later phases) imports `apiRequest` instead
 * of calling fetch directly, so auth headers, base URL, and error
 * envelope handling live in exactly one place.
 */

const API_BASE_URL = window.location.origin.includes("5500")
  ? "http://127.0.0.1:8000/api" // local static server (e.g. Live Server) talking to a separate API process
  : "/api"; // served by / proxied through the same origin as the API

const ACCESS_TOKEN_KEY = "clinic_os_access_token";
const REFRESH_TOKEN_KEY = "clinic_os_refresh_token";

export function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setTokens({ access_token, refresh_token }) {
  localStorage.setItem(ACCESS_TOKEN_KEY, access_token);
  localStorage.setItem(REFRESH_TOKEN_KEY, refresh_token);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

/**
 * @param {string} path e.g. "/health"
 * @param {RequestInit} options
 * @param {{skipAuthRetry?: boolean}} [config]
 */
export async function apiRequest(path, options = {}, config = {}) {
  const token = getAccessToken();

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  const body = await response.json().catch(() => null);

  // Access token expired: try exactly one silent refresh, then retry the call.
  if (response.status === 401 && !config.skipAuthRetry && getRefreshToken()) {
    const refreshed = await tryRefreshTokens();
    if (refreshed) {
      return apiRequest(path, options, { skipAuthRetry: true });
    }
    clearTokens();
  }

  if (!response.ok || (body && body.success === false)) {
    const message = body?.error?.message || `Request failed (${response.status})`;
    throw new Error(message);
  }

  return body;
}

async function tryRefreshTokens() {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: getRefreshToken() }),
    });
    if (!response.ok) return false;
    const body = await response.json();
    setTokens(body.data);
    return true;
  } catch {
    return false;
  }
}

export async function checkHealth() {
  return apiRequest("/health");
}

export async function login(username, password) {
  const body = await apiRequest(
    "/auth/login",
    { method: "POST", body: JSON.stringify({ username, password }) },
    { skipAuthRetry: true }
  );
  setTokens(body.data);
  return body.data;
}

export async function logout() {
  try {
    await apiRequest("/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token: getRefreshToken() }),
    });
  } finally {
    clearTokens();
  }
}

export async function getCurrentUser() {
  const body = await apiRequest("/auth/me");
  return body.data;
}
