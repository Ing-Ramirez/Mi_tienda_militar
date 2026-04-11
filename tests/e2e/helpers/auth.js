"use strict";
/**
 * helpers/auth.js — Utilidades de autenticación para tests E2E
 * =============================================================
 *
 * Credenciales vía variables de entorno:
 *   TEST_USER_EMAIL     email del usuario de prueba
 *   TEST_USER_PASSWORD  contraseña
 *   TEST_BASE_URL       URL base (default: http://localhost)
 *
 * Si las variables no están definidas, los tests que requieren auth
 * hacen skip automáticamente.
 */

const { expect } = require("@playwright/test");

const BASE_URL = process.env.BASE_URL || "http://localhost";
const API      = `${BASE_URL}/api/v1`;

// ── Credenciales ──────────────────────────────────────────────────────────────

const TEST_CREDENTIALS = {
  email:    process.env.TEST_USER_EMAIL    || "",
  password: process.env.TEST_USER_PASSWORD || "",
};

/**
 * Retorna true si hay credenciales de prueba configuradas.
 */
function hasTestCredentials() {
  return !!(TEST_CREDENTIALS.email && TEST_CREDENTIALS.password);
}

// ── Login via API (más rápido que UI login) ───────────────────────────────────

/**
 * Inicia sesión vía API REST y almacena el access token en localStorage.
 * El refresh token queda en cookie HttpOnly (gestionado por el browser).
 *
 * @param {import('@playwright/test').Page} page
 * @returns {Promise<{accessToken: string, user: object}>}
 */
async function loginApi(page) {
  if (!hasTestCredentials()) {
    throw new Error(
      "❌ Credenciales no configuradas.\n" +
      "   Define TEST_USER_EMAIL y TEST_USER_PASSWORD en el entorno."
    );
  }

  const response = await page.request.post(`${API}/auth/login/`, {
    data: {
      email:    TEST_CREDENTIALS.email,
      password: TEST_CREDENTIALS.password,
    },
    headers: { "Content-Type": "application/json" },
  });

  if (!response.ok()) {
    const body = await response.text();
    throw new Error(`❌ Login fallido (${response.status()}): ${body.slice(0, 200)}`);
  }

  const data = await response.json();
  const accessToken = data.access;

  if (!accessToken) {
    throw new Error("❌ Login exitoso pero no se recibió access token.");
  }

  // Inyectar token en localStorage para que el SPA lo use
  await page.evaluate((token) => {
    localStorage.setItem("fp_access_token", token);
  }, accessToken);

  return { accessToken, user: data.user || {} };
}

// ── Login via UI ──────────────────────────────────────────────────────────────

/**
 * Inicia sesión a través de la UI del SPA.
 * Más lento que loginApi pero valida el flujo completo.
 *
 * @param {import('@playwright/test').Page} page
 */
async function loginUi(page) {
  if (!hasTestCredentials()) {
    throw new Error("Credenciales no configuradas.");
  }

  // Abrir modal de auth (botón en el header)
  await page.click('[data-action="openAuthModal"]');
  await page.waitForSelector("#auth-modal", { state: "visible" });

  // Rellenar formulario de login
  await page.fill('[id="auth-email"]', TEST_CREDENTIALS.email);
  await page.fill('[id="auth-password"]', TEST_CREDENTIALS.password);
  await page.click('[data-action="submitLogin"]');

  // Esperar cierre del modal (indica login exitoso)
  await page.waitForSelector("#auth-modal", { state: "hidden", timeout: 10_000 });
}

// ── Logout ────────────────────────────────────────────────────────────────────

/**
 * Cierra sesión limpiando localStorage y llamando al endpoint de logout.
 *
 * @param {import('@playwright/test').Page} page
 */
async function logout(page) {
  // Intentar logout via API
  try {
    await page.request.post(`${API}/auth/logout/`);
  } catch {
    // Silencioso — puede que ya no haya sesión
  }

  // Limpiar storage local
  await page.evaluate(() => {
    localStorage.removeItem("fp_access_token");
    localStorage.clear();
  });
}

// ── Skip helper ───────────────────────────────────────────────────────────────

/**
 * Marca un test como "skipped" si no hay credenciales de prueba.
 * Usar al inicio de tests que requieren autenticación.
 *
 * @param {import('@playwright/test').TestInfo} testInfo
 * @param {string} [reason]
 */
function skipIfNoCredentials(testInfo, reason = "") {
  if (!hasTestCredentials()) {
    testInfo.skip(
      true,
      reason ||
        "Test requiere credenciales. Configura TEST_USER_EMAIL y TEST_USER_PASSWORD."
    );
  }
}

module.exports = {
  loginApi,
  loginUi,
  logout,
  hasTestCredentials,
  skipIfNoCredentials,
  TEST_CREDENTIALS,
};
